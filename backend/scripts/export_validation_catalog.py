"""Read-only PostgreSQL catalog snapshot for live QA grounding checks."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.database.session import SessionLocal
from app.models.product import Product

with SessionLocal() as db:
    products = [{key: getattr(product, key) for key in
                 ['id', 'name', 'brand', 'category', 'price', 'mrp', 'stock', 'in_stock', 'rating', 'rating_count', 'discount_percent', 'flattened_specs']}
                for product in db.query(Product).all()]
Path('../documentation/e2e-catalog-snapshot.json').write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding='utf-8')
print('Read-only catalog rows:', len(products))
