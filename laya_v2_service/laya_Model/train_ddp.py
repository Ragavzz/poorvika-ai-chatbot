import os
import sys
import time
import json
import random
import math
import argparse
import numpy as np
import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP
from safetensors.torch import load_file, save_file
from transformers import AutoTokenizer
from laya.common import build_model, QTYPES, temp_bucket, clamp_temperature

TEMP_MIN, TEMP_MAX = 0.5, 5.0
MIN_TYPE_N, MIN_BUCKET_N = 10, 30

def collate_train_batch(items, pad_id):
    n = len(items)
    max_len = max(len(it["ids"]) for it in items)
    kmax = max(len(it["markers"]) for it in items)
    
    ids = torch.full((n, max_len), pad_id, dtype=torch.long)
    att = torch.zeros((n, max_len), dtype=torch.long)
    mpos = torch.zeros((n, kmax), dtype=torch.long)
    mmask = torch.zeros((n, kmax), dtype=torch.bool)
    target = torch.zeros((n, kmax), dtype=torch.float32)
    
    for i, it in enumerate(items):
        seq_len = len(it["ids"])
        ids[i, :seq_len] = torch.tensor(it["ids"])
        att[i, :seq_len] = 1
        k = len(it["markers"])
        mpos[i, :k] = torch.tensor(it["markers"])
        mmask[i, :k] = True
        target[i, :len(it["target"])] = torch.tensor(it["target"], dtype=torch.float32)
        
    return {
        "input_ids": ids,
        "attention_mask": att,
        "marker_pos": mpos,
        "marker_mask": mmask,
        "target": target,
        "qtype": torch.tensor([it["qtype"] for it in items]),
        "label": torch.tensor([it["label"] for it in items]),
        "weight": torch.tensor([float(it.get("w", 1.0)) for it in items], dtype=torch.float32)
    }

def softmax_np(z, T=1.0):
    z = np.asarray(z, dtype=np.float64) / T
    e = np.exp(z - z.max())
    return e / e.sum()

def ece_np(confs, corrects, n_bins=15):
    confs, corrects = np.asarray(confs, float), np.asarray(corrects, float)
    if len(confs) == 0:
        return float("nan")
    edges = np.linspace(0, 1, n_bins + 1)
    ece_val = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (confs > lo) & (confs <= hi)
        if m.any():
            ece_val += m.mean() * abs(confs[m].mean() - corrects[m].mean())
    return float(ece_val)

def fit_one_temp(sel, min_n=MIN_TYPE_N):
    """Fit T so top-1 confidence matches top-1 correctness (binary CE), within [0.5, 5.0]."""
    if len(sel) < min_n:
        return 1.0
    best_t, best_l = 1.0, float("inf")
    for T in np.round(np.arange(TEMP_MIN, TEMP_MAX + 1e-9, 0.05), 2):
        loss_val = 0.0
        for z, t in sel:
            p = softmax_np(z, T)
            c = float(np.clip(p.max(), 1e-6, 1.0 - 1e-6))
            y = float(np.argmax(p) == int(np.argmax(t)))
            loss_val -= y * np.log(c) + (1.0 - y) * np.log(1.0 - c)
        if loss_val < best_l:
            best_l, best_t = loss_val, float(T)
    return clamp_temperature(best_t, TEMP_MIN, TEMP_MAX)

def eval_holdout(model, items, tok, device):
    """Evaluate soft-CE and argmax accuracy on held-out items."""
    model.eval()
    nll = acc = n = 0.0
    with torch.no_grad():
        for i in range(0, len(items), 16):
            chunk = items[i:i + 16]
            cb = collate_train_batch(chunk, tok.pad_token_id)
            with torch.autocast("cuda", dtype=torch.float16):
                logits, _ = model(
                    cb["input_ids"].to(device),
                    cb["attention_mask"].to(device),
                    cb["marker_pos"].to(device),
                    cb["marker_mask"].to(device),
                    cb["qtype"].to(device)
                )
            m = cb["marker_mask"].to(device)
            t = cb["target"].to(device)
            lp = torch.log_softmax(logits.float().masked_fill(~m, -1e4), -1)
            nll += (-(t * lp).sum(-1)).sum().item()
            acc += (lp.argmax(-1) == t.argmax(-1)).sum().item()
            n += len(chunk)
    model.train()
    return nll / max(n, 1), acc / max(n, 1)

def main():
    parser = argparse.ArgumentParser(description="DDP Fine-Tuning for Laya Model")
    parser.add_argument("model_dir", nargs="?", default="convaiinnovations/laya", help="Path or HF ID of base model")
    parser.add_argument("output_dir", nargs="?", default="laya_finetuned_typed_decisions", help="Directory to save fine-tuned model")
    parser.add_argument("--data_path", default="train_items.pt", help="Path to preprocessed train items")
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--micro_batch", type=int, default=8)
    parser.add_argument("--grad_accum", type=int, default=4)
    parser.add_argument("--lr_encoder", type=float, default=2.5e-5)
    parser.add_argument("--lr_head", type=float, default=1.0e-4)
    args = parser.parse_args()

    # DDP Initialization
    is_distributed = int(os.environ.get("WORLD_SIZE", "1")) > 1 or "LOCAL_RANK" in os.environ
    if is_distributed:
        backend = "nccl" if torch.cuda.is_available() and sys.platform != "win32" else "gloo"
        dist.init_process_group(backend)
        rank = dist.get_rank()
        world_size = dist.get_world_size()
        local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    else:
        rank = 0
        world_size = 1
        local_rank = 0

    if torch.cuda.is_available():
        torch.cuda.set_device(local_rank)
        device = torch.device("cuda", local_rank)
    else:
        device = torch.device("cpu")

    model_dir = args.model_dir
    output_dir = args.output_dir

    if rank == 0:
        print(f"=== Initializing DDP Run | Rank: {rank}/{world_size} | Device: {device} ===")

    # Load model config and base components
    if os.path.isdir(model_dir):
        config_path = os.path.join(model_dir, "rl_agent_config.json")
        encoder_path = os.path.join(model_dir, "encoder")
        tokenizer_path = os.path.join(model_dir, "tokenizer")
        weights_path = os.path.join(model_dir, "model.safetensors")
    else:
        from huggingface_hub import snapshot_download
        model_dir = snapshot_download(model_dir)
        config_path = os.path.join(model_dir, "rl_agent_config.json")
        encoder_path = os.path.join(model_dir, "encoder")
        tokenizer_path = os.path.join(model_dir, "tokenizer")
        weights_path = os.path.join(model_dir, "model.safetensors")

    with open(config_path) as f:
        cfg = json.load(f)
    cfg["gradient_checkpointing"] = True
    cfg["max_tokens_per_batch"] = 4096
    cfg["max_len"] = 1024
    cfg["head_max_len"] = 256

    tok = AutoTokenizer.from_pretrained(tokenizer_path)
    model = build_model(cfg, encoder_dir=encoder_path)
    weights = load_file(weights_path)
    model.load_state_dict(weights, strict=True)

    if hasattr(model.encoder, "gradient_checkpointing_enable"):
        model.encoder.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.head_checkpointing = True
    model.to(device)
    model.train()

    all_params = [p for p in model.parameters() if p.requires_grad]
    if is_distributed and torch.cuda.is_available():
        ddp_model = DDP(model, device_ids=[local_rank], find_unused_parameters=False)
    else:
        ddp_model = model

    all_items = torch.load(args.data_path, weights_only=False)

    # Reserve holdout slice for calibration
    EXTRA_W = 0.3
    td_cids = sorted({it["cid"] for it in all_items if it.get("src") == "td"})
    random.Random(20260922).shuffle(td_cids)
    hold = set(td_cids[:max(1, int(len(td_cids) * 0.06))]) if td_cids else set()
    is_hold = lambda it: it.get("src") == "td" and it["cid"] in hold
    
    calib_items = [it for it in all_items if is_hold(it)]
    train_items = [it for it in all_items if not is_hold(it)]
    
    for it in train_items:
        it["w"] = 1.0 if it.get("src", "td") == "td" else EXTRA_W

    # Trim to equalize across ranks
    if world_size > 1:
        train_items = train_items[:len(train_items) // world_size * world_size]
        my_items = train_items[rank::world_size]
    else:
        my_items = train_items

    EPOCHS = args.epochs
    MICRO_BATCH = args.micro_batch
    GRAD_ACCUM = args.grad_accum
    LR_ENCODER = args.lr_encoder
    LR_HEAD = args.lr_head
    WARMUP_FRAC = 0.05

    enc_params = [p for n, p in ddp_model.named_parameters() if "encoder." in n]
    head_params = [p for n, p in ddp_model.named_parameters() if "encoder." not in n]

    optimizer = torch.optim.AdamW([
        {"params": enc_params, "lr": LR_ENCODER},
        {"params": head_params, "lr": LR_HEAD}
    ], weight_decay=0.01)

    updates_per_epoch = math.ceil(len(my_items) / (MICRO_BATCH * GRAD_ACCUM))
    total_updates = max(1, updates_per_epoch * EPOCHS)
    warmup_steps = max(1, int(WARMUP_FRAC * total_updates))

    def lr_schedule(step):
        if step < warmup_steps:
            return (step + 1) / warmup_steps
        prog = min(1.0, (step - warmup_steps) / max(1, total_updates - warmup_steps))
        return max(0.02, 0.5 * (1.0 + math.cos(math.pi * prog)))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_schedule)
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

    if rank == 0:
        print(f"Training Start: {len(train_items)} train items ({len(calib_items)} holdout calibration) | {len(my_items)}/rank | {EPOCHS} Epochs")

    t0 = time.time()
    best = {"nll": float("inf"), "epoch": 0, "sd": None}

    for epoch in range(EPOCHS):
        random.seed(42 + epoch + rank)
        random.shuffle(my_items)
        epoch_loss, n_batches = 0.0, 0
        optimizer.zero_grad(set_to_none=True)
        accum_step = 0

        for b_idx in range(0, len(my_items), MICRO_BATCH):
            chunk = my_items[b_idx:b_idx + MICRO_BATCH]
            if not chunk: continue

            batch = collate_train_batch(chunk, tok.pad_token_id)
            with torch.autocast("cuda", dtype=torch.float16, enabled=(device.type == "cuda")):
                logits, _ = ddp_model(
                    batch["input_ids"].to(device),
                    batch["attention_mask"].to(device),
                    batch["marker_pos"].to(device),
                    batch["marker_mask"].to(device),
                    batch["qtype"].to(device)
                )

            logits = logits.float()
            mask = batch["marker_mask"].to(device)
            target = batch["target"].to(device)
            w = batch["weight"].to(device)

            lp = torch.log_softmax(logits.masked_fill(~mask, -1e4), -1)
            ce_i = -(target * lp).sum(-1)
            loss_ce = (ce_i * w).sum() / w.sum().clamp_min(1e-6)
            touch = sum(p.sum() for p in all_params) * 0.0
            loss = loss_ce / GRAD_ACCUM + touch

            scaler.scale(loss).backward()
            accum_step += 1

            if accum_step % GRAD_ACCUM == 0 or (b_idx + MICRO_BATCH) >= len(my_items):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(ddp_model.parameters(), 1.0)
                scaler.step(optimizer)
                scale_before = scaler.get_scale()
                scaler.update()
                if scaler.get_scale() >= scale_before:
                    scheduler.step()
                optimizer.zero_grad(set_to_none=True)

            epoch_loss += loss.item() * GRAD_ACCUM
            n_batches += 1

        if rank == 0:
            print(f"=== Epoch {epoch+1}/{EPOCHS} Completed in {time.time()-t0:.1f}s | Avg Loss: {epoch_loss/max(1, n_batches):.4f} ===")

        if is_distributed:
            dist.barrier()

        if rank == 0:
            h_nll, h_acc = eval_holdout(model, calib_items, tok, device)
            print(f"  Hold-out soft-CE: {h_nll:.4f} | argmax acc: {h_acc:.3f}")
            if h_nll < best["nll"]:
                best.update(nll=h_nll, epoch=epoch + 1, sd={k: v.detach().cpu().clone() for k, v in model.state_dict().items()})

        if is_distributed:
            dist.barrier()

    # Post-training Calibration on Rank 0
    if rank == 0:
        print("\n=== Post-Training Temperature Calibration ===")
        del optimizer, scaler, scheduler
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        if best["sd"] is not None:
            model.load_state_dict(best["sd"])
            print(f"Loaded best epoch {best['epoch']} (Soft-CE: {best['nll']:.4f})")
        model.eval()

        calib_preds = []
        with torch.no_grad():
            for c_idx in range(0, len(calib_items), 16):
                c_chunk = calib_items[c_idx:c_idx + 16]
                cb = collate_train_batch(c_chunk, tok.pad_token_id)
                with torch.autocast("cuda", dtype=torch.float16, enabled=(device.type == "cuda")):
                    l_sub, _ = model(
                        cb["input_ids"].to(device),
                        cb["attention_mask"].to(device),
                        cb["marker_pos"].to(device),
                        cb["marker_mask"].to(device),
                        cb["qtype"].to(device)
                    )
                l_np = l_sub.float().cpu().numpy()
                for r, it in enumerate(c_chunk):
                    k = len(it["markers"])
                    calib_preds.append((it["qtype"], l_np[r, :k], it["target"], it.get("qid", "__all__")))

        hacc = np.mean([int(np.argmax(z) == int(np.argmax(t))) for _, z, t, _ in calib_preds])
        print(f"Held-out typed-decisions accuracy: {hacc:.3f} on {len(calib_preds)} items")

        fitted_temps = [1.0, 1.0, 1.0]
        tbo = {}
        try:
            by_bucket = {}
            for qt in range(3):
                sel = [(z, t) for q_type, z, t, _ in calib_preds if q_type == qt]
                fitted_temps[qt] = fit_one_temp(sel)
            for q_type, z, t, _ in calib_preds:
                by_bucket.setdefault(temp_bucket(q_type, len(z)), []).append((z, t))
            for qt in range(3):
                for k in (2, 4, 8, 12):
                    key = temp_bucket(qt, k)
                    pairs = by_bucket.get(key, [])
                    tbo[key] = fit_one_temp(pairs, MIN_BUCKET_N) if len(pairs) >= MIN_BUCKET_N else fitted_temps[qt]
            print("Fitted type temperatures (choice, score, noul):", [round(t, 3) for t in fitted_temps])
            print("Fitted bucket temperatures:", {k: round(v, 3) for k, v in tbo.items()})
        except Exception as e:
            print("Temperature fitting fallback error:", repr(e))

        def T_for(qt, k):
            return tbo.get(temp_bucket(qt, k), fitted_temps[qt])

        confs, corr = [], []
        for qt, z, t, _ in calib_preds:
            p = softmax_np(z, T_for(qt, len(z)))
            confs.append(p.max())
            corr.append(float(np.argmax(p) == int(np.argmax(t))))

        raw_c = [softmax_np(z).max() for _, z, _, _ in calib_preds]
        e_raw, e_cal = ece_np(raw_c, corr), ece_np(confs, corr)
        print(f"Calibration ECE: raw {e_raw:.3f} -> calibrated {e_cal:.3f}")

        if e_cal > e_raw:
            fitted_temps, tbo = [1.0, 1.0, 1.0], {k: 1.0 for k in tbo}
            print("Calibration degraded ECE -> Reset temperatures to 1.0")

        # Save artifacts
        os.makedirs(output_dir, exist_ok=True)
        sd = {k: v.half().contiguous().cpu() for k, v in model.state_dict().items()}
        save_file(sd, os.path.join(output_dir, "model.safetensors"))
        model.encoder.config.save_pretrained(os.path.join(output_dir, "encoder"))
        tok.save_pretrained(os.path.join(output_dir, "tokenizer"))

        cfg["fine_tuned"] = True
        cfg["model_name"] = "laya-typed-decisions-v2"
        cfg["temperature"] = fitted_temps
        cfg["temperature_by_options"] = tbo

        with open(os.path.join(output_dir, "rl_agent_config.json"), "w") as f:
            json.dump(cfg, f, indent=2)

        print(f"\n[+] Fine-tuned model artifacts successfully saved to: {output_dir}")

    if is_distributed:
        dist.destroy_process_group()

if __name__ == "__main__":
    main()
