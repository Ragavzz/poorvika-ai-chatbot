import json
import pyarrow.parquet as pq
from pathlib import Path

parquet_path = Path("evaluation/jev_benchmark/dataset/test-00000-of-00001.parquet")
table = pq.read_table(parquet_path)
df_dict = table.to_pydict()

total_cases = len(df_dict["id"])
total_decisions = 0
type_counts = {"choice": 0, "score": 0, "noul": 0}
wf_counts = {}

all_cases = []
for i in range(total_cases):
    case_id = df_dict["id"][i]
    wf = df_dict["workflow"][i]
    wf_counts[wf] = wf_counts.get(wf, 0) + 1
    state = json.loads(df_dict["state"][i])
    questions = json.loads(df_dict["questions"][i])
    gold = json.loads(df_dict["gold"][i])

    assert len(questions) == 5, f"Case {case_id} has {len(questions)} questions"
    assert len(gold) == 5, f"Case {case_id} has {len(gold)} gold answers"

    for q_name, q_val in questions.items():
        total_decisions += 1
        q_type = q_val.get("type")
        assert q_type in type_counts, f"Unknown type {q_type} in {case_id} {q_name}"
        type_counts[q_type] += 1
        g_val = gold.get(q_name)
        assert g_val is not None, f"Missing gold for {case_id} {q_name}"

    all_cases.append({
        "case_id": case_id,
        "workflow": wf,
        "state": state,
        "questions": questions,
        "gold": gold
    })

print(f"Verified {total_cases} cases and {total_decisions} decisions.")
print(f"Workflows: {wf_counts}")
print(f"Decision types: {type_counts}")

# Save JSON version
json_path = Path("evaluation/jev_benchmark/dataset/typed_decisions_test.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(all_cases, f, indent=2)
print(f"Saved extracted JSON to {json_path} (size: {json_path.stat().st_size} bytes)")
