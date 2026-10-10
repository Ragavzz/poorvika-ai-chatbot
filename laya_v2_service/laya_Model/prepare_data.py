import os
import re
import json
import random
import argparse
from collections import Counter
import torch
from datasets import load_dataset
from transformers import AutoTokenizer
from huggingface_hub import snapshot_download
from laya.agent import _fix_tokenizer_config
from laya.common import build_sequence, render_options, QTYPES

MAX_PER_DATASET = 400    # Cap per auxiliary source
LABEL_SMOOTH = 0.10      # Soften hard one-hot targets to prevent overconfidence
RNG_SEED = 20260930

def clean_text(*parts) -> str:
    """Strip HTML tags, URLs, and email addresses, then normalize whitespace."""
    text = " ".join(str(p) for p in parts if p)
    text = re.sub(r"<[^>]+>|https?://\S+|[\w.+-]+@[\w-]+\.[\w.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:2000]

def load_first_available(*specs):
    for name, kw in specs:
        try:
            ds = load_dataset(name, split="train", **kw)
            print(f"  [+] Loaded {name}: {len(ds)} rows")
            return ds
        except Exception as e:
            print(f"  [-] Could not load {name}: {type(e).__name__}: {str(e)[:100]}")
    return None

def pick_column(cols, candidates):
    return next((c for c in candidates if c in cols), None)

def extract_label_name(ds, col, val):
    f = ds.features[col]
    return f.names[val] if hasattr(f, "names") else str(val)

def smooth_choice_targets(keys, gold_key):
    k = len(keys)
    eps = LABEL_SMOOTH if k > 1 else 0.0
    return {k_i: (1.0 - eps) if k_i == gold_key else eps / max(k - 1, 1) for k_i in keys}

def smooth_ordinal_targets(num_levels, gold_idx):
    probs = [0.0] * num_levels
    if num_levels == 1:
        probs[0] = 1.0
        return probs
    eps = LABEL_SMOOTH
    neighbors = [j for j in (gold_idx - 1, gold_idx + 1) if 0 <= j < num_levels]
    probs[gold_idx] = 1.0 - eps
    for j in neighbors:
        probs[j] += eps / len(neighbors)
    return probs

def make_choice_question(instruction, keys, gold_key):
    keys = list(dict.fromkeys(keys))
    assert gold_key in keys, f"Gold key {gold_key!r} not found in options {keys}"
    return (
        {"type": "choice", "instructions": instruction, "criteria": {k: "" for k in keys}},
        {"probabilities": smooth_choice_targets(keys, gold_key), "label": gold_key}
    )

def make_score_question(instruction, levels, gold_idx):
    levels = list(levels)
    probs = smooth_ordinal_targets(len(levels), gold_idx)
    return (
        {"type": "score", "instructions": instruction, "criteria": levels},
        {"probabilities": {str(i): probs[i] for i in range(len(levels))}, "label": gold_idx, "score": float(gold_idx)}
    )

RANK = {
    "informational": 0, "info": 0, "very low": 0, "very_low": 0, "low": 1, "minor": 1,
    "medium": 2, "moderate": 2, "high": 3, "major": 3, "critical": 4, "severe": 4
}

def extract_sorted_levels(values):
    return sorted({v for v in values if v in RANK}, key=lambda v: (RANK[v], v))

def sample_dataset(ds, rng):
    n = min(MAX_PER_DATASET, len(ds))
    return [ds[i] for i in rng.sample(range(len(ds)), n)]

def build_training_item(state, q, gold_q, tok, cfg, seen, dropped):
    t = q["type"]
    crit = q.get("criteria", {})
    k = len(render_options({"t": t, "crit": crit}))

    if t == "choice":
        names = list(crit)
    elif t == "noul":
        names = ["false", "true"]
    else:
        names = [str(i) for i in range(k)]

    lab = str(gold_q["label"])
    lab = lab.lower() if t == "noul" else str(int(float(lab))) if t == "score" else lab
    target = [float(gold_q["probabilities"].get(n, 0.0)) for n in names]

    if len(names) != k or lab not in names or sum(target) <= 0:
        dropped["bad_label"] += 1
        return None

    target = [v / sum(target) for v in target]
    label = names.index(lab)

    seq, markers = build_sequence(
        tok, state,
        {"t": t, "ins": q["instructions"], "crit": crit},
        cfg["max_len"], cfg["head_max_len"]
    )

    if len(markers) != k:
        dropped["marker_mismatch"] += 1
        return None

    key = (tuple(seq), t)
    if key in seen:
        dropped["duplicate"] += 1
        return None

    seen.add(key)
    return {
        "ids": seq,
        "markers": markers,
        "qtype": QTYPES[t],
        "target": target,
        "label": label
    }

def collect_auxiliary_cases(rng):
    all_cases = []

    # 1. Banking77
    def add_banking():
        ds = load_first_available(
            ("legacy-datasets/banking77", {}),
            ("PolyAI/banking77", {"revision": "refs/convert/parquet"}),
            ("PolyAI/banking77", {})
        )
        if ds is None: return
        names = [n.replace("_", " ") for n in ds.features["label"].names]
        cases = []
        for r in sample_dataset(ds, rng):
            g = names[r["label"]]
            t = clean_text(r["text"])
            if not t or g not in names: continue
            pool = [n for n in names if n != g]
            cand = rng.sample(pool, min(7, len(pool))) + [g]
            rng.shuffle(cand)
            q, a = make_choice_question("Which banking intent does the customer message express?", cand, g)
            cases.append(({"channel": "banking_customer_message", "message": t}, {"banking_intent": q}, {"banking_intent": a}))
        all_cases.append(("banking77", cases))

    # 2. IT Support Tickets
    def add_itsupport():
        ds = load_first_available(("tasksource/it-support-tickets", {}))
        if ds is None: return
        names = [str(n) for n in ds.features["label"].names]
        cases = []
        for r in sample_dataset(ds, rng):
            q, a = make_choice_question("Which IT support category does this ticket belong to?", names, names[r["label"]])
            cases.append(({"channel": "it_support_ticket", "ticket": clean_text(r["text"])},
                          {"it_support_category": q}, {"it_support_category": a}))
        all_cases.append(("it-support-tickets", cases))

    # 3. Customer Support Tickets
    def add_tickets():
        ds = load_first_available(("Tobi-Bueck/customer-support-tickets", {}))
        if ds is None: return
        rows = sample_dataset(ds, rng)
        queues = [k for k, _ in Counter(str(r["queue"]).strip() for r in rows if r.get("queue")).most_common(10)]
        prios = extract_sorted_levels(str(r["priority"]).strip().lower() for r in rows if r.get("priority"))
        cases = []
        for r in rows:
            text = clean_text(r.get("subject"), r.get("body"))
            qs_, gs_ = {}, {}
            if text and str(r.get("queue")).strip() in queues:
                qs_["ticket_queue"], gs_["ticket_queue"] = make_choice_question("Which support queue should this ticket be routed to?", queues, str(r["queue"]).strip())
            p = str(r.get("priority")).strip().lower()
            if text and p in prios and len(prios) >= 2:
                qs_["ticket_priority"], gs_["ticket_priority"] = make_score_question("How urgent is this ticket?", prios, prios.index(p))
            if qs_:
                cases.append(({"channel": "customer_support_ticket", "ticket": text}, qs_, gs_))
        all_cases.append(("customer-support-tickets", cases))

    # 4. Email Intent
    def add_email():
        ds = load_first_available(("elenigkove/Email_Intent_Classification", {}))
        if ds is None: return
        tc = pick_column(ds.column_names, ["Email", "email", "text", "body"])
        lc = pick_column(ds.column_names, ["Intent", "intent", "label"])
        if not tc or not lc: return
        lab = lambda r: r[lc] if isinstance(r[lc], str) else extract_label_name(ds, lc, r[lc])
        rows = sample_dataset(ds, rng)
        labs = sorted({lab(r) for r in ds})
        cases = []
        for r in rows:
            q, a = make_choice_question("What is the intent of this email?", labs, lab(r))
            cases.append(({"channel": "email", "email": clean_text(r[tc])}, {"email_intent": q}, {"email_intent": a}))
        all_cases.append(("email-intent", cases))

    # 5. Security Incidents
    def add_incidents():
        ds = load_first_available(("emmanuelgjr/genai-incidents", {}))
        if ds is None: return
        rows = sample_dataset(ds, rng)
        sev = lambda r: str(r.get("severity")).strip().lower()
        levels = extract_sorted_levels(sev(r) for r in rows)
        if len(levels) < 2: return
        cases = []
        for r in rows:
            text = clean_text(r.get("title"), r.get("description"))
            if text and sev(r) in levels:
                q, a = make_score_question("How severe is this security incident?", levels, levels.index(sev(r)))
                cases.append(({"channel": "security_incident", "incident": text}, {"incident_severity": q}, {"incident_severity": a}))
        all_cases.append(("genai-incidents", cases))

    # 6. Bitext Customer Service
    def add_bitext():
        ds = load_first_available(("bitext/Bitext-customer-support-llm-chatbot-training-dataset", {}))
        if ds is None: return
        tc = pick_column(ds.column_names, ["instruction", "text"])
        lc = pick_column(ds.column_names, ["intent", "category"])
        if not tc or not lc: return
        names = sorted({str(v).replace("_", " ") for v in ds.unique(lc)})
        cases = []
        for r in sample_dataset(ds, rng):
            g = str(r[lc]).replace("_", " ")
            t = clean_text(r[tc])
            if not t or g not in names: continue
            pool = [n for n in names if n != g]
            cand = rng.sample(pool, min(7, len(pool))) + [g]
            rng.shuffle(cand)
            q, a = make_choice_question("Which customer-service intent does this message express?", cand, g)
            cases.append(({"channel": "customer_service_message", "message": t}, {"cs_intent": q}, {"cs_intent": a}))
        all_cases.append(("bitext-customer-service", cases))

    for fn in [add_banking, add_itsupport, add_tickets, add_email, add_incidents, add_bitext]:
        try:
            fn()
        except Exception as e:
            print(f"  [-] Skipped source: {e}")

    return all_cases

def main():
    parser = argparse.ArgumentParser(description="Prepare dataset for Laya fine-tuning")
    parser.add_argument("--model_id", default="convaiinnovations/laya", help="Hugging Face base model ID")
    parser.add_argument("--output_path", default="train_items.pt", help="Path to save serialized items")
    args = parser.parse_args()

    print(f"=== Fetching tokenizer & config from {args.model_id} ===")
    model_dir = snapshot_download(args.model_id)
    _fix_tokenizer_config(model_dir)

    tok = AutoTokenizer.from_pretrained(os.path.join(model_dir, "tokenizer"))
    with open(os.path.join(model_dir, "rl_agent_config.json")) as f:
        cfg = json.load(f)

    # Force expected lengths
    cfg["max_len"] = 1024
    cfg["head_max_len"] = 256

    print("\n=== Loading Primary Dataset: LocalLLaMA/typed-decisions (train) ===")
    ds_train = load_dataset("LocalLLaMA/typed-decisions", "all", split="train")

    seen = set()
    dropped = Counter()
    items = []

    for cid, row in enumerate(ds_train):
        state = json.loads(row["state"])
        questions = json.loads(row["questions"])
        gold = json.loads(row["gold"])
        for qid, q in questions.items():
            if qid in gold:
                it = build_training_item(state, q, gold[qid], tok, cfg, seen, dropped)
                if it:
                    it["src"] = "td"
                    it["cid"] = cid
                    it["qid"] = qid
                    items.append(it)

    n_td = len(items)
    print(f"Primary typed-decisions items: {n_td} | dropped: {dict(dropped)}")

    print("\n=== Loading 6 Auxiliary Datasets ===")
    rng = random.Random(RNG_SEED)
    aux_cases = collect_auxiliary_cases(rng)

    for src_name, cases in aux_cases:
        added = 0
        for state, questions, gold in cases:
            for qid, q in questions.items():
                it = build_training_item(state, q, gold[qid], tok, cfg, seen, dropped)
                if it:
                    it["src"] = src_name
                    it["cid"] = -1
                    it["qid"] = qid
                    items.append(it)
                    added += 1
        print(f"  {src_name}: +{added} items")

    print(f"\nTotal preprocessed sequences: {len(items)} (Primary: {n_td}, Auxiliary: {len(items) - n_td})")
    print("Per-source breakdown:", dict(Counter(it.get("src") for it in items)))

    torch.save(items, args.output_path)
    print(f"Successfully saved combined preprocessed dataset to: {args.output_path}")

if __name__ == "__main__":
    main()
