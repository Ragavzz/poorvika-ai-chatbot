import json
import pyarrow.parquet as pq
from pathlib import Path

parquet_path = Path("evaluation/jev_benchmark/dataset/test-00000-of-00001.parquet")
table = pq.read_table(parquet_path)
df_dict = table.to_pydict()

workflows_questions = {}
for i in range(len(df_dict["id"])):
    wf = df_dict["workflow"][i]
    qs = json.loads(df_dict["questions"][i])
    if wf not in workflows_questions:
        workflows_questions[wf] = {}
        for q_name, q_val in qs.items():
            workflows_questions[wf][q_name] = {
                "type": q_val.get("type"),
                "instructions": q_val.get("instructions"),
                "criteria_type": type(q_val.get("criteria")).__name__,
                "criteria": q_val.get("criteria")
            }

print(f"Total cases: {len(df_dict['id'])}")
for wf, qs in workflows_questions.items():
    print(f"\nWorkflow: {wf} (5 questions):")
    for q_name, q_info in qs.items():
        print(f"  [{q_info['type'].upper()}] {q_name}: {q_info['instructions']}")
        if q_info['criteria_type'] == 'dict':
            print(f"     options ({len(q_info['criteria'])}): {list(q_info['criteria'].keys())}")
        elif q_info['criteria_type'] == 'list':
            print(f"     levels ({len(q_info['criteria'])}): {q_info['criteria']}")
