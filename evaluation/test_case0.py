import json
import pyarrow.parquet as pq
from pathlib import Path
import requests

parquet_path = Path("evaluation/jev_benchmark/dataset/test-00000-of-00001.parquet")
table = pq.read_table(parquet_path)
df_dict = table.to_pydict()

# Row 0
row0_id = df_dict["id"][0]
row0_wf = df_dict["workflow"][0]
row0_state = json.loads(df_dict["state"][0])
row0_questions = json.loads(df_dict["questions"][0])
row0_gold = json.loads(df_dict["gold"][0])

print(f"Testing case: {row0_id} ({row0_wf})")
payload = {
    "state": row0_state,
    "questions": row0_questions,
}

resp = requests.post("http://localhost:5055/decide", json=payload, timeout=30)
print("Status code:", resp.status_code)
res_json = resp.json()
print("Model:", res_json.get("model"))
print("Source:", res_json.get("source"))
print("Usage:", res_json.get("usage"))

print("\nAnswers comparison:")
for q_name, q_gold in row0_gold.items():
    laya_ans = res_json.get("answers", {}).get(q_name, {})
    print(f"\nQuestion: {q_name} (type: {q_gold.get('type')})")
    print(f"  Gold: label={q_gold.get('label')}, score={q_gold.get('score')}, noul={q_gold.get('noul')}, probs={q_gold.get('probabilities')}")
    print(f"  Laya: choice={laya_ans.get('choice')}, score={laya_ans.get('score')}, noul={laya_ans.get('noul')}, confidence={laya_ans.get('confidence')}, probs={laya_ans.get('probabilities')}")
