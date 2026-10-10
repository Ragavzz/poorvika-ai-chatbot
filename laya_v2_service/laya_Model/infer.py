import laya

# Remote HF or Local Directory
agent = laya.load("Mass121/laya-typed-decisions-v2")
# Local: agent = laya.Agent("./laya_finetuned_typed_decisions", device="cuda")

state = {
    "channel": "customer_support_ticket",
    "ticket": "Double charged on my invoice #4921."
}

questions = {
    "cs_intent": {
        "type": "choice",
        "instructions": "Determine customer intent",
        "criteria": {
            "billing issue": "Billing/payment query",
            "technical support": "System error"
        }
    }
}

result = agent.predict(state, questions)
print(result["answers"])
