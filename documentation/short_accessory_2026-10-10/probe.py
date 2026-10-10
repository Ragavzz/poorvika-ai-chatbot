import asyncio,json,logging,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"backend"))
from sqlalchemy import create_engine,text,event
from sqlalchemy.orm import Session
from app.config import settings
from app.models.product import Product
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest
logging.basicConfig(level=logging.INFO)
engine=create_engine(settings.sqlalchemy_database_url,connect_args={"connect_timeout":3})
queries=[]
@event.listens_for(engine,"before_cursor_execute")
def capture(conn,cursor,statement,parameters,context,executemany):
 if "FROM products" in statement and "WHERE" in statement:
  queries.append({"where":statement.split("WHERE",1)[1],"parameters":parameters})
with Session(engine) as db:
 db.execute(text("SET TRANSACTION READ ONLY"))
 service=ChatService(db)
 message="Show me the Samsung Tab S7 screen protector"
 p=db.get(Product,"2-5d-clear-tempered-glass-screen-protector-for-samsung-tab-s7-plus-12-4-inch")
 print("PRODUCT",json.dumps({k:getattr(p,k) for k in ("id","name","brand","category","price","stock","in_stock")}))
 filters=service._filters(message)
 rows=service._find_products(filters)
 print("FILTER_SQL",json.dumps({"filters":filters,"count":len(rows),"ids":[p["id"] for p in rows],"sql":queries[-1]}))
 timings={}
 answer=asyncio.run(service.generate_response(ChatRequest(message=message),timings=timings))
 print("ANSWER",json.dumps({"response":answer.response,"timings":timings}))
engine.dispose()
