"""Product Search Tool querying PostgreSQL as the single source of truth.

Guarantees the chatbot and product listing never invent or hallucinate product names,
prices, specifications, availability, or ratings.
"""

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Union
from sqlalchemy import or_, and_, desc, asc, func
from sqlalchemy.orm import Session, load_only
from app.models.product import Product

logger = logging.getLogger("shopai.tools.product_search")

# Category mapping connecting high-level UI categories and user synonyms to exact PostgreSQL categories
CATEGORY_MAPPINGS = {
    # Parent categories from UI navigation
    "mobiles": ["Mobiles", "Mobile Phone", "Smart Phone", "Mobile"],
    "mobile": ["Mobiles", "Mobile Phone", "Smart Phone", "Mobile"],
    "smartphones": ["Mobiles", "Mobile Phone", "Smart Phone", "Mobile"],
    "smartphone": ["Mobiles", "Mobile Phone", "Smart Phone", "Mobile"],
    "phones": ["Mobiles", "Mobile Phone", "Smart Phone", "Mobile"],
    "phone": ["Mobiles", "Mobile Phone", "Smart Phone", "Mobile"],
    "accessories": [
        "Data Cables", "Battery Chargers", "Cases & Covers",
        "Power Banks", "Pendrives", "Memory Cards",
        "Surge Protector", "AirTag", "Temper glass", "Car Chargers"
    ],
    "audio": ["Headphones", "Speakers"],
    "smart watches": ["Smartwatches"],
    "smartwatches": ["Smartwatches"],
    "laptops": ["Computers"],
    "televisions": ["Television"],
    "television": ["Television"],
    "appliances": [
        "Air Coolers", "Air Fryers", "Fans", "Irons",
        "Mixers Grinders & Juicers", "Voltage Stabilizers", "Voltage Stabilizer",
        "Chimney", "Refrigerators", "Refrigerator", "Washing Machine",
        "Water Purifiers", "Food Processor"
    ],
    "home appliances": [
        "Air Coolers", "Fans", "Irons",
        "Voltage Stabilizers", "Voltage Stabilizer", "Washing Machine",
        "Refrigerators", "Refrigerator"
    ],
    "mobiles & accessories": [
        "Mobiles", "Mobile Phone", "Smart Phone", "Mobile",
        "Data Cables", "Battery Chargers", "Cases & Covers",
        "Power Banks", "Pendrives", "Memory Cards",
        "Surge Protector", "AirTag", "Temper glass", "Car Chargers"
    ],
    "computers & tablets": [
        "Computers", "Tablet", "Keyboards", "Mouse",
        "Smart Keyboard", "Mother Board"
    ],
    "tv & audio": ["Television", "Headphones", "Speakers"],
    "kitchen appliances": [
        "Air Fryers", "Mixers Grinders & Juicers", "Chimney",
        "Water Purifiers", "Food Processor"
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
        exact_name: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None,
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
                Product.rating, Product.rating_count, Product.in_stock, Product.stock, Product.flattened_specs,
            ))
        filters = []
        if exclude_ids:
            filters.append(Product.id.notin_(exclude_ids))
        query_rank_terms: List[str] = []
        exact_match = (func.lower(func.trim(Product.name)) == exact_name.strip().lower()
                       if exact_name and exact_name.strip() else None)

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
            # Normalize case, punctuation and repeated whitespace, then stem
            # common plurals consistently ("iphones" -> "iphone").
            raw_words = re.findall(r"[a-z0-9]+", query.casefold())
            normalized_words = []
            for word in raw_words:
                if len(word) > 4 and word.endswith("ies"):
                    word = word[:-3] + "y"
                elif len(word) > 3 and word.endswith("s"):
                    word = word[:-1]
                normalized_words.append(word)
            q_clean = " ".join(normalized_words)
            is_redundant = (
                (brand and str(brand).lower() in q_clean and len(q_clean.split()) == 1) or
                (category and category.lower() in q_clean and len(q_clean.split()) == 1)
            )
            if not is_redundant:
                words = [w for w in normalized_words if len(w) > 2 or w.isdigit()
                         or (exact_match is not None and re.fullmatch(r"[a-z]\d|\d[a-z]", w))]
                word_clauses = []
                for w in words:
                    stem = w[:-1] if w.endswith("s") and len(w) > 3 else w
                    query_rank_terms.append(stem)
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
                    # Every meaningful product term must match; OR here lets
                    # action words or model numbers pull unrelated rows in.
                    text_match = and_(*word_clauses)
                    filters.append(or_(exact_match, text_match) if exact_match is not None else text_match)

        if exact_match is not None and not (query and query.strip()):
            filters.append(exact_match)

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
            # Prefer names that match the requested terms near the start. This
            # ranks the actual model above accessory compatibility mentions,
            # without brand/model-specific rules.
            # SQLite instr and PostgreSQL strpos both return a 1-based position,
            # zero for missing text, and NULL for NULL input. Keep PostgreSQL's
            # existing expression and ranking unchanged.
            position = func.instr if self.db.get_bind().dialect.name == "sqlite" else func.strpos
            name_match_order = [
                asc(func.nullif(position(func.lower(Product.name), term), 0)).nullslast()
                for term in query_rank_terms
            ]
            # Then in-stock first, rating, and lowest price.
            stmt = stmt.order_by(
                *([desc(exact_match)] if exact_match is not None else []),
                *name_match_order, desc(Product.in_stock), desc(Product.rating).nullslast(),
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
                    "stock": product.stock,
                    "specifications": dict(list((product.flattened_specs or {}).items())[:2]),
                }
                for product in results
            ]
        return [p.to_dict() for p in results]

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single product by primary key id from PostgreSQL."""
        p = self.db.query(Product).filter(Product.id == product_id).first()
        return p.to_dict() if p else None
