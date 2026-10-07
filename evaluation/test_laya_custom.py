import requests
import json

payload = {
    "state": {
        "subject": "Refund not received",
        "body": "I cancelled two weeks ago and still have no refund. Please help."
    },
    "questions": {
        "department": {
            "type": "choice",
            "instructions": "Which team should handle this ticket?",
            "criteria": {
                "billing": "payments, refunds, invoices",
                "support": "product help and bugs",
                "sales": "new purchases"
            }
        },
        "urgency": {
            "type": "score",
            "instructions": "How urgent is this ticket?",
            "criteria": ["not urgent", "somewhat urgent", "urgent", "critical"]
        },
        "churn_risk": {
            "type": "noul",
            "instructions": "Is the customer likely to cancel or dispute?"
        }
    }
}

resp = requests.post("http://localhost:5055/decide", json=payload)
print("Status:", resp.status_code)
print(json.dumps(resp.json(), indent=2))
