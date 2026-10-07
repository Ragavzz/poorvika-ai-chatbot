import json
import pyarrow.parquet as pq
from pathlib import Path

parquet_path = Path("evaluation/jev_benchmark/dataset/test-00000-of-00001.parquet")
table = pq.read_table(parquet_path)
print("Table num rows:", table.num_rows)
print("Table column names:", table.column_names)

df_dict = table.to_pydict()
print("\nWorkflows in dataset:")
workflows = {}
for w in df_dict["workflow"]:
    workflows[w] = workflows.get(w, 0) + 1
for w, count in workflows.items():
    print(f"  - {w}: {count} cases")

# Inspect the first row
print("\n--- Inspecting Row 0 ---")
for col in ["id", "workflow", "split"]:
    print(f"{col}: {df_dict[col][0]}")

row0_state = json.loads(df_dict["state"][0])
print("\nState type:", type(row0_state))
print("State keys / content preview:", str(row0_state)[:200])

row0_questions = json.loads(df_dict["questions"][0])
print("\nQuestions count:", len(row0_questions))
print("Question keys:", list(row0_questions.keys()))
for q_name, q_val in row0_questions.items():
    print(f"  Question '{q_name}': type={q_val.get('type')}, instructions={q_val.get('instructions')}")

row0_gold = json.loads(df_dict["gold"][0])
print("\nGold count:", len(row0_gold))
print("Gold keys:", list(row0_gold.keys()))
for g_name, g_val in row0_gold.items():
    print(f"  Gold '{g_name}': keys={list(g_val.keys())}, sample={g_val}")
