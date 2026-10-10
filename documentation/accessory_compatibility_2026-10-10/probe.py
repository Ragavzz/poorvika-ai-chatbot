import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import asyncio,json,logging
from sqlalchemy import create_engine,text,event
from sqlalchemy.orm import Session
from app.config import settings
from app.models.product import Product
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest
logging.basicConfig(level=logging.INFO)
engine=create_engine(settings.sqlalchemy_database_url,connect_args={"connect_timeout":3})
sql=[]
@event.listens_for(engine,"before_cursor_execute")
def capture(conn,cursor,statement,parameters,context,executemany):
 if "FROM products" in statement and "WHERE" in statement:
  sql.append({"where":statement.split("WHERE",1)[1],"parameters":parameters})
with Session(engine) as db:
 db.execute(text("SET TRANSACTION READ ONLY"))
 service=ChatService(db)
 product=db.get(Product,"2-5d-clear-tempered-glass-screen-protector-for-samsung-tab-s7-plus-12-4-inch")
 query="Show me "+product.name
 print("PRODUCT",json.dumps({k:getattr(product,k) for k in ("id","name","brand","category","price","stock","in_stock")}))
 filters=service._filters(query)
 print("FILTERS",json.dumps(filters))
 rows=service._find_products(filters)
 print("ROWS",json.dumps([{k:p[k] for k in ("id","name","brand","price","stock","in_stock")} for p in rows]))
 print("SEARCH_SQL",json.dumps(sql[-1]))
 timings={}
 answer=asyncio.run(service.generate_response(ChatRequest(message=query),timings=timings))
 print("ANSWER",json.dumps({"response":answer.response,"timings":timings}))
engine.dispose()
