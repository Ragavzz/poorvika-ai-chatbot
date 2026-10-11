"""Isolated API failure injection; never stops or replaces running model services."""
import json
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import requests
from app.config import settings
from app.database.session import get_db
from app.routes.chat import chat_router
from app.routes.suggestions import suggestions_router
from app.services.laya_client import POORVIKA_ACTIONS
from app.services.suggestion_service import CACHE

app = FastAPI()
app.include_router(chat_router)
app.include_router(suggestions_router)
app.dependency_overrides[get_db] = lambda: Mock()
client = TestClient(app)
valid_laya = Mock()
valid_laya.json.return_value = {'model':'Mass121/laya-typed-decisions-v2','answers':{'intent':{
    'type':'choice','choice':'general_query','confidence':1,
    'probabilities':{key:int(key=='general_query') for key in POORVIKA_ACTIONS},
}}}
results=[]
def record(label, endpoint, body, laya, ollama):
    CACHE.clear()
    started=time.perf_counter()
    with patch('app.services.laya_client.HTTP.post', **laya), patch('app.services.ollama_service.HTTP.post', **ollama):
        response=client.post(endpoint,json=body,headers={'X-ShopAI-Request-ID':label})
    timing_header='X-ShopAI-Suggestion-Timing' if endpoint.endswith('suggestions') else 'X-ShopAI-Chat-Timing'
    payload=response.json()
    result={'case':label,'execution':'Isolated TestClient network-failure injection; not a live outage',
            'input':body,'http_status':response.status_code,'latency_ms':(time.perf_counter()-started)*1000,
            'payload':payload,'timings':json.loads(response.headers.get(timing_header,'null'))}
    if label.startswith('laya'):
        result['pass']=response.status_code==200 and payload.get('response_source')=='decision_service_error' and 'unavailable' in payload.get('response','')
    else:
        result['pass']=response.status_code in (503,504) and 'response' not in payload and 'suggestions' not in payload
    results.append(result)

record('laya-timeout','/api/chat',{'message':'Hi'},{'side_effect':requests.Timeout('injected timeout')},{'side_effect':AssertionError('Ollama must not run')})
bad_laya=Mock();bad_laya.json.return_value={'model':'unexpected-model'}
record('laya-malformed','/api/chat',{'message':'Hi'},{'return_value':bad_laya},{'side_effect':AssertionError('Ollama must not run')})
for label, failure in [('ollama-timeout',requests.Timeout('injected')),('ollama-connection',requests.ConnectionError('injected'))]:
    record(label,'/api/chat',{'message':'Hi'},{'return_value':valid_laya},{'side_effect':failure})
empty=Mock();empty.json.return_value={'message':{'content':''}}
record('ollama-empty','/api/chat',{'message':'Hi'},{'return_value':valid_laya},{'return_value':empty})
for label, failure in [('suggestion-timeout',requests.Timeout('injected')),('suggestion-connection',requests.ConnectionError('injected'))]:
    record(label,'/api/chat/suggestions',{'product':{'name':'Phone'}},{'side_effect':AssertionError('No Laya dependency')},{'side_effect':failure})
malformed=Mock();malformed.json.return_value={'message':{'content':'not json'}}
record('suggestion-malformed','/api/chat/suggestions',{'product':{'name':'Phone'}},{'side_effect':AssertionError('No Laya dependency')},{'return_value':malformed})
record('suggestion-empty-context','/api/chat/suggestions',{'product':{}},{'side_effect':AssertionError('No model')},{'side_effect':AssertionError('No model')})
results[-1]['pass']=results[-1]['http_status']==422
Path('../documentation/e2e-controlled-failures.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('Isolated failure contracts:',sum(r['pass'] for r in results),'/',len(results))
if not all(r['pass'] for r in results):
    raise SystemExit(1)
