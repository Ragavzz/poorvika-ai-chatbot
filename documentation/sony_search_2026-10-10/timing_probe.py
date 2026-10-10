import asyncio,json,logging,time
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from app.config import settings
from app.routes.chat import chat
from app.schemas.chat import ChatRequest
class Capture(logging.Handler):
 def emit(self,record):
  message=record.getMessage()
  if message.startswith("[TIMING] "):
   print("ROUTE_TIMING",message[9:])
logging.getLogger("shopai.routes.chat").setLevel(logging.INFO)
logging.getLogger("shopai.routes.chat").addHandler(Capture())
engine=create_engine(settings.sqlalchemy_database_url,connect_args={"connect_timeout":3})
try:
 for i in range(3):
  with Session(engine) as db:
   db.execute(text("SET TRANSACTION READ ONLY"))
   response=asyncio.run(chat(ChatRequest(message="Show me Sony earphones under 1000 rupees"),db))
   print("MATCH",json.dumps({"sample":i+1,"matched":"sony-mdr-ex15ap-earphone-black" in response.response,"price_correct":"829" in response.response}))
finally:
 engine.dispose()
