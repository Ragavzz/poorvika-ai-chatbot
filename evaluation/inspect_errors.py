import json
from collections import Counter

with open("evaluation/jev_benchmark/results/laya_jev_benchmark_results.json", "r", encoding="utf-8") as f:
    decisions = json.load(f)

errors = [d.get("error") for d in decisions if d.get("error")]
print("Total errors:", len(errors))
counter = Counter(errors)
for err, count in counter.most_common():
    print(f"Count: {count} | Error: {err[:150]}")

# Also check which cases/workflows had errors
cases_with_errors = set(d.get("case_id") for d in decisions if d.get("error"))
print("Distinct cases with errors:", len(cases_with_errors))

# Check by workflow
wf_errors = Counter(d.get("workflow") for d in decisions if d.get("error"))
print("Errors by workflow:", wf_errors)
