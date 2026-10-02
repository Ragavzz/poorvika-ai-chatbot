"""Product Search Tool querying PostgreSQL as the single source of truth.

Guarantees the chatbot and product listing never invent or hallucinate product names,
prices, specifications, availability, or ratings.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from sqlalchemy import or_, and_, desc, asc
from sqlalchemy.orm import Session, load_only
from app.models.product import Product

logger = logging.getLogger("shopai.tools.product_search")

# Category mapping connecting high-level UI categories and user synonyms to exact PostgreSQL categories
CATEGORY_MAPPINGS = {
    # Parent categories from UI navigation
    "accessories": [
        "Data Cables", "Battery Chargers", "Cases & Covers",
        "Power Banks", "Pendrives", "Memory Cards",
        "Surge Protector", "AirTag"
    ],
    "audio": ["Headphones"],
    "smart watches": ["Smartwatches"],
    "smartwatches": ["Smartwatches"],
    "mobiles": [],
    "laptops": [],
    "televisions": [],
    "appliances": [
        "Air Coolers", "Air Fryers", "Fans", "Irons",
        "Mixers Grinders & Juicers", "Voltage Stabilizers", "Voltage Stabilizer"
    ],
    "home appliances": [
        "Air Coolers", "Air Fryers", "Fans", "Irons",
        "Mixers Grinders & Juicers", "Voltage Stabilizers", "Voltage Stabilizer"
    ],
    "mobiles & accessories": [
        "Data Cables", "Battery Chargers", "Cases & Covers",
        "Power Banks", "Pendrives", "Memory Cards",
        "Surge Protector", "AirTag"
    ],
    "computers & tablets": [
        "Battery Chargers", "Pendrives", "Memory Cards"
    ],
    "tv & audio": ["Headphones"],
    "kitchen appliances": [
        "Air Fryers", "Mixers Grinders & Juicers"
    ],
    "smart technology": ["Smartwatches", "AirTag"],
    "personal & health care": ["Irons"],

    # Direct child categories present in PostgreSQL
    "headphones": ["Headphones"],
    "earphones": ["Headphones"],
    "earbuds": ["Headphones"],
    "data cables": ["Data Cables"],
    "cables": ["Data Cables"],
    "battery chargers": ["Battery Chargers"],
    "chargers": ["Battery Chargers"],
    "cases & covers": ["Cases & Covers"],
    "covers": ["Cases & Covers"],
    "power banks": ["Power Banks"],
    "stabilizers": ["Voltage Stabilizers", "Voltage Stabilizer"],
    "voltage stabilizers": ["Voltage Stabilizers", "Voltage Stabilizer"],
    "voltage stabilizer": ["Voltage Stabilizers", "Voltage Stabilizer"],
    "irons": ["Irons"],
    "iron": ["Irons"],
    "fans": ["Fans"],
    "air coolers": ["Air Coolers"],
    "coolers": ["Air Coolers"],
    "air fryers": ["Air Fryers"],
    "fryers": ["Air Fryers"],
    "mixers grinders & juicers": ["Mixers Grinders & Juicers"],
    "mixers": ["Mixers Grinders & Juicers"],
    "pendrives": ["Pendrives"],
    "memory cards": ["Memory Cards"],
    "airtag": ["AirTag"],
    "surge protector": ["Surge Protector"],
}


class ProductSearchTool:
    """PostgreSQL-backed tool for controlled product search and retrieval."""

    def __init__(self, db: Session):
        self.db = db

    def search_products(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        brand: Optional[Union[str, List[str]]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        in_stock_only: bool = False,
        min_rating: Optional[float] = None,
        min_discount: Optional[float] = None,
        sort_by: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        frontend_only: bool = False,
        timings: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a controlled query against PostgreSQL.
        Returns serialized product dictionaries from real database rows.
        """
        stmt = self.db.query(Product)
        if frontend_only:
            stmt = stmt.options(load_only(
                Product.id, Product.name, Product.brand, Product.price, Product.mrp,
                Product.discount_percent, Product.image, Product.images, Product.category,
                Product.rating, Product.rating_count, Product.in_stock, Product.flattened_specs,
            ))
        filters = []

        # 1. Category filter (with normalization and parent-to-child mapping)
        if category and category.strip():
            cat_clean = category.strip().lower()
            if cat_clean not in ["all", "all categories", "all products"]:
                mapped_categories = CATEGORY_MAPPINGS.get(cat_clean)
                if mapped_categories:
                    cat_clauses = [Product.category.ilike(f"%{c}%") for c in mapped_categories]
                    filters.append(or_(*cat_clauses))
                else:
                    filters.append(
                        or_(
                            Product.category.ilike(f"%{category.strip()}%"),
                            Product.name.ilike(f"%{category.strip()}%"),
                        )
                    )

        # 2. Brand filter (supports single brand or list of brands)
        if brand:
            if isinstance(brand, list) and len(brand) > 0:
                brand_filters = [Product.brand.ilike(f"%{b.strip()}%") for b in brand if b.strip()]
                if brand_filters:
                    filters.append(or_(*brand_filters))
            elif isinstance(brand, str) and brand.strip():
                filters.append(Product.brand.ilike(f"%{brand.strip()}%"))

        # 3. Price bounds
        if min_price is not None and min_price > 0:
            filters.append(Product.price >= min_price)
        if max_price is not None and max_price > 0:
            filters.append(Product.price <= max_price)

        # 4. In-stock filter
        if in_stock_only:
            filters.append(Product.in_stock == True)
        if min_rating is not None and min_rating > 0:
            filters.append(Product.rating >= min_rating)
        if min_discount is not None and min_discount > 0:
            filters.append(Product.discount_percent >= min_discount)

        # 5. Text search across name, brand, category, model, description
        if query and query.strip():
            q_clean = query.strip().lower()
            is_redundant = (
                (brand and str(brand).lower() in q_clean and len(q_clean.split()) == 1) or
                (category and category.lower() in q_clean and len(q_clean.split()) == 1)
            )
            if not is_redundant:
                words = [w for w in q_clean.split() if len(w) > 2]
                word_clauses = []
                for w in words:
                    stem = w[:-1] if w.endswith("s") and len(w) > 3 else w
                    term = f"%{stem}%"
                    word_clauses.append(
                        or_(
                            Product.name.ilike(term),
                            Product.brand.ilike(term),
                            Product.category.ilike(term),
                            Product.model.ilike(term),
                            Product.description.ilike(term),
                        )
                    )
                if word_clauses:
                    filters.append(or_(*word_clauses))

        if filters:
            stmt = stmt.filter(and_(*filters))

        # 6. Sorting
        if sort_by == "price_asc":
            stmt = stmt.order_by(asc(Product.price), asc(Product.id))
        elif sort_by == "price_desc":
            stmt = stmt.order_by(desc(Product.price), asc(Product.id))
        elif sort_by in ["rating", "rating_desc"]:
            stmt = stmt.order_by(desc(Product.rating).nullslast(), desc(Product.rating_count), asc(Product.id))
        elif sort_by in ["discount", "discount_desc"]:
            stmt = stmt.order_by(desc(Product.discount_percent), asc(Product.id))
        else:
            # Default: in-stock first, then rating, then lowest price
            stmt = stmt.order_by(
                desc(Product.in_stock), desc(Product.rating).nullslast(),
                asc(Product.price), asc(Product.id),
            )

        query_started = time.perf_counter()
        if timings is not None:
            timings["postgres_query_start"] = datetime.now(timezone.utc).isoformat()
            timings["postgres_query_count"] = timings.get("postgres_query_count", 0) + 1
        results = stmt.offset(max(0, offset)).limit(max(1, min(limit, 100))).all()
        if timings is not None:
            timings["postgres_query_end"] = datetime.now(timezone.utc).isoformat()
            timings["postgres_query_duration_ms"] = round((time.perf_counter() - query_started) * 1000, 1)
        if frontend_only:
            return [
                {
                    "id": product.id,
                    "name": product.name,
                    "brand": product.brand,
                    "price": product.price,
                    "originalPrice": product.mrp,
                    "discount": product.discount_percent,
                    "image": product.image,
                    "images": product.images or ([product.image] if product.image else []),
                    "category": product.category,
                    "rating": product.rating,
                    "reviewCount": product.rating_count,
                    "inStock": product.in_stock,
                    "specifications": dict(list((product.flattened_specs or {}).items())[:2]),
                }
                for product in results
            ]
        return [p.to_dict() for p in results]

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single product by primary key id from PostgreSQL."""
        p = self.db.query(Product).filter(Product.id == product_id).first()
        return p.to_dict() if p else None
