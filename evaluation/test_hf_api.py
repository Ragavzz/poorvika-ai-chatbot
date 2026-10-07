import requests

url = "https://datasets-server.huggingface.co/rows?dataset=LocalLLaMA/typed-decisions&config=all&split=test&offset=0&limit=10"
resp = requests.get(url, timeout=15)
print("Status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print("Num rows:", len(data.get("rows", [])))
    print("Total in split:", data.get("num_rows_per_page"), data.get("num_rows_total"))
else:
    print(resp.text[:500])
