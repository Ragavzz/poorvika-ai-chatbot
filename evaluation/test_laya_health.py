import requests
import json

resp = requests.get("http://localhost:5055/health")
print("Health status code:", resp.status_code)
print("Health body:", resp.json())

# Let's test a sample decide request
sample_req = {
    "state": {"message": "Looking for a samsung phone under 20000"},
}
resp2 = requests.post("http://localhost:5055/decide", json=sample_req)
print("Decide status code:", resp2.status_code)
print("Decide body:", json.dumps(resp2.json(), indent=2))
