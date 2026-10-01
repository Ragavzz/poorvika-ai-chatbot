"""Standalone PostgreSQL dataset importer for Poorvika product catalog.

Reads data/poorvika_products.jsonl, cleans and validates records,
preserves specifications/images in JSONB, handles stock/availability,
and safely upserts into the PostgreSQL database.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Tuple

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config import settings
from app.database.session import engine, SessionLocal, check_db_connection
from app.database.base import Base
from app.models.product import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shopai.importer")


def clean_price(val: Any) -> float:
    """Cleans numeric or string price values into a float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("₹", "").replace(",", "").replace("Rs.", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_specs(raw_specs: Any) -> Tuple[str, Dict[str, str]]:
    """
    Parses specifications to extract category from 'Generic Name'
    and builds flattened dictionary for fast attribute lookup.
    """
    category = "Electronics"
    flattened = {}

    if not isinstance(raw_specs, dict):
        return category, flattened

    attribute_groups = raw_specs.get("attributeGroups", [])
    if isinstance(attribute_groups, list):
        for group in attribute_groups:
            if not isinstance(group, dict):
                continue
            attrs = group.get("attributes", [])
            if isinstance(attrs, list):
                for attr in attrs:
                    if not isinstance(attr, dict):
                        continue
                    name = (attr.get("name") or "").strip()
                    val = (str(attr.get("value") or "")).strip()
                    if name and val:
                        flattened[name] = val
                        if name == "Generic Name":
                            category = val
    return category, flattened


def run_import(file_path: str = None) -> Dict[str, int]:
    """
    Executes product import from JSONL into PostgreSQL.
    Returns stats dict: {total, imported, updated, skipped, errors}.
    """
    dataset_path = file_path or settings.DATASET_PATH
    if not os.path.isabs(dataset_path):
        dataset_path = os.path.abspath(os.path.join(backend_dir, dataset_path))

    if not os.path.exists(dataset_path):
        # Fallback to direct path in workspace
        alt_path = os.path.join(os.path.dirname(backend_dir), "data", "poorvika_products.jsonl")
        if os.path.exists(alt_path):
            dataset_path = alt_path
        else:
            logger.error(f"Dataset file not found at: {dataset_path}")
            return {"total": 0, "imported": 0, "updated": 0, "skipped": 0, "errors": 1}

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    stats = {
        "total": 0,
        "imported": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    db = SessionLocal()
    seen_ids = set()

    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue

                stats["total"] += 1

                try:
                    record = json.loads(clean_line)
                except Exception as e:
                    logger.warning(f"Line {line_num}: JSON decode error: {e}")
                    stats["errors"] += 1
                    continue

                pid = record.get("product_id") or record.get("id")
                name = record.get("name")

                # Validation
                if not pid or not name:
                    logger.warning(f"Line {line_num}: Missing product_id or name. Skipping.")
                    stats["skipped"] += 1
                    continue

                # Deduplicate in-stream
                if pid in seen_ids:
                    logger.info(f"Duplicate product_id '{pid}' in input. Skipping duplicate.")
                    stats["skipped"] += 1
                    continue
                seen_ids.add(pid)

                try:
                    # Clean prices
                    online_price = clean_price(record.get("online_price") or record.get("price"))
                    mrp = clean_price(record.get("mrp"))
                    shop_price_raw = record.get("shop_price")
                    shop_price = clean_price(shop_price_raw) if shop_price_raw is not None else None

                    discount_percent = 0.0
                    if mrp > online_price > 0:
                        discount_percent = round(((mrp - online_price) / mrp) * 100, 2)

                    # Stock & availability
                    stock = int(record.get("stock", 0))
                    in_stock = stock > 0
                    availability = record.get("availability") or ("https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock")

                    # Specifications
                    raw_specs = record.get("specifications") or {}
                    category, flattened_specs = parse_specs(raw_specs)

                    # Images
                    images = record.get("images") or []
                    if isinstance(images, str):
                        images = [images]
                    primary_image = images[0] if images else record.get("image")

                    # Upsert logic
                    existing = db.query(Product).filter(Product.id == pid).first()
                    if existing:
                        existing.name = name
                        existing.brand = record.get("brand", existing.brand)
                        existing.model = record.get("model", existing.model)
                        existing.category = category
                        existing.sku = record.get("sku", existing.sku)
                        existing.item_code = record.get("item_code", existing.item_code)
                        existing.erp_item_code = record.get("erp_item_code", existing.erp_item_code)
                        existing.price = online_price
                        existing.online_price = online_price
                        existing.mrp = mrp
                        existing.shop_price = shop_price
                        existing.discount_percent = discount_percent
                        existing.currency = record.get("currency", "INR")
                        existing.stock = stock
                        existing.in_stock = in_stock
                        existing.availability = availability
                        rating_val = record.get("rating")
                        existing.rating = float(rating_val) if rating_val is not None else None
                        existing.rating_count = int(record.get("rating_count", 0))
                        existing.image = primary_image
                        existing.images = images
                        existing.description = record.get("description", existing.description)
                        existing.url = record.get("url", existing.url)
                        existing.canonical_url = record.get("canonical_url", existing.canonical_url)
                        existing.specifications = raw_specs
                        existing.flattened_specs = flattened_specs
                        existing.source_hash = record.get("source_hash")
                        existing.scraped_at = record.get("scraped_at")
                        stats["updated"] += 1
                    else:
                        prod = Product(
                            id=pid,
                            name=name,
                            brand=record.get("brand", "Unknown"),
                            model=record.get("model"),
                            category=category,
                            sku=record.get("sku"),
                            item_code=record.get("item_code"),
                            erp_item_code=record.get("erp_item_code"),
                            price=online_price,
                            online_price=online_price,
                            mrp=mrp,
                            shop_price=shop_price,
                            discount_percent=discount_percent,
                            currency=record.get("currency", "INR"),
                            stock=stock,
                            in_stock=in_stock,
                            availability=availability,
                            rating=float(record["rating"]) if record.get("rating") is not None else None,
                            rating_count=int(record.get("rating_count", 0)),
                            image=primary_image,
                            images=images,
                            description=record.get("description"),
                            url=record.get("url"),
                            canonical_url=record.get("canonical_url"),
                            specifications=raw_specs,
                            flattened_specs=flattened_specs,
                            source_hash=record.get("source_hash"),
                            scraped_at=record.get("scraped_at"),
                        )
                        db.add(prod)
                        stats["imported"] += 1

                except Exception as row_err:
                    logger.error(f"Error processing product '{pid}': {row_err}")
                    stats["errors"] += 1

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Fatal import transaction error: {e}", exc_info=True)
        stats["errors"] += 1
    finally:
        db.close()

    return stats


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("\n" + "=" * 50)
    print("STARTING POORVIKA DATASET IMPORT")
    print("=" * 50)

    is_connected, msg = check_db_connection(force=True)
    if not is_connected:
        print(f"\n[WARNING] Database connection check: {msg}")
        print("If PostgreSQL is not running, start PostgreSQL and configure backend/.env")

    stats = run_import()

    print("\n" + "=" * 50)
    print("POORVIKA PRODUCT DATASET INGESTION SUMMARY")
    print("=" * 50)
    print(f"Total Records Read: {stats['total']}")
    print(f"Imported (New):     {stats['imported']}")
    print(f"Updated:            {stats['updated']}")
    print(f"Skipped:            {stats['skipped']}")
    print(f"Errors:             {stats['errors']}")
    print("=" * 50)
