"""Dataset ingestion pipeline for Poorvika JSONL product records.

Preserves all 22 attributes without data loss.
Extracts category from 'Generic Name', calculates discounts,
and flattens specifications for fast retrieval.
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.config import settings
from app.models.product import Product
from app.database.session import engine, SessionLocal, check_db_connection
from app.database.base import Base

logger = logging.getLogger("shopai.database.ingest")


def parse_specifications(raw_specs: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    """
    Parses raw Poorvika specifications dict:
    - Extracts 'Generic Name' to serve as category
    - Builds a clean flattened key-value dictionary for fast lookup
    """
    category = "Electronics"
    flattened: Dict[str, str] = {}

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


def load_dataset_records(file_path: str) -> List[Dict[str, Any]]:
    """Reads and parses JSONL product records from disk."""
    if not os.path.exists(file_path):
        logger.warning(f"Dataset file not found at: {file_path}")
        return []

    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            clean_line = line.strip()
            if not clean_line:
                continue
            try:
                record = json.loads(clean_line)
                records.append(record)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON on line {line_num}: {e}")
    return records


def ingest_products(db: Session, records: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Upserts product records into the database.
    Returns (inserted_count, updated_count).
    """
    inserted = 0
    updated = 0

    for item in records:
        pid = item.get("product_id") or item.get("id")
        if not pid:
            continue

        raw_specs = item.get("specifications", {})
        category, flattened_specs = parse_specifications(raw_specs)

        # Price calculations
        online_price = float(item.get("online_price") or item.get("price", 0))
        mrp_val = item.get("mrp")
        mrp = float(mrp_val) if mrp_val is not None else None
        discount_percent = 0.0
        if mrp and online_price and mrp > online_price:
            discount_percent = round(((mrp - online_price) / mrp) * 100, 2)

        # Stock & availability
        stock = int(item.get("stock", 0))
        in_stock = stock > 0
        availability = item.get("availability") or ("https://schema.org/InStock" if in_stock else "https://schema.org/OutOfStock")

        # Images
        images = item.get("images", [])
        if isinstance(images, str):
            images = [images]
        image_url = images[0] if images and len(images) > 0 else item.get("image")

        # Check existing
        existing = db.query(Product).filter(Product.id == pid).first()
        if existing:
            existing.name = item.get("name", existing.name)
            existing.brand = item.get("brand", existing.brand)
            existing.model = item.get("model", existing.model)
            existing.category = category
            existing.sku = item.get("sku", existing.sku)
            existing.item_code = item.get("item_code", existing.item_code)
            existing.erp_item_code = item.get("erp_item_code", existing.erp_item_code)
            existing.price = online_price
            existing.online_price = online_price
            existing.mrp = mrp
            existing.shop_price = float(item["shop_price"]) if item.get("shop_price") is not None else None
            existing.discount_percent = discount_percent
            existing.currency = item.get("currency", "INR")
            existing.stock = stock
            existing.in_stock = in_stock
            existing.availability = availability
            existing.rating = float(item["rating"]) if item.get("rating") is not None else None
            existing.rating_count = int(item.get("rating_count", 0))
            existing.image = image_url
            existing.images = images
            existing.description = item.get("description", existing.description)
            existing.url = item.get("url", existing.url)
            existing.canonical_url = item.get("canonical_url", existing.canonical_url)
            existing.specifications = raw_specs
            existing.flattened_specs = flattened_specs
            existing.source_hash = item.get("source_hash")
            existing.scraped_at = item.get("scraped_at")
            updated += 1
        else:
            product = Product(
                id=pid,
                name=item.get("name", ""),
                brand=item.get("brand", "Unknown"),
                model=item.get("model"),
                category=category,
                sku=item.get("sku"),
                item_code=item.get("item_code"),
                erp_item_code=item.get("erp_item_code"),
                price=online_price,
                online_price=online_price,
                mrp=mrp,
                shop_price=float(item["shop_price"]) if item.get("shop_price") is not None else None,
                discount_percent=discount_percent,
                currency=item.get("currency", "INR"),
                stock=stock,
                in_stock=in_stock,
                availability=availability,
                rating=float(item["rating"]) if item.get("rating") is not None else None,
                rating_count=int(item.get("rating_count", 0)),
                image=image_url,
                images=images,
                description=item.get("description"),
                url=item.get("url"),
                canonical_url=item.get("canonical_url"),
                specifications=raw_specs,
                flattened_specs=flattened_specs,
                source_hash=item.get("source_hash"),
                scraped_at=item.get("scraped_at"),
            )
            db.add(product)
            inserted += 1

    db.commit()
    logger.info(f"Ingestion complete: {inserted} inserted, {updated} updated.")
    return inserted, updated


def run_dataset_ingestion(dataset_path: str = None) -> Tuple[bool, str]:
    """Ensures tables exist and ingests the JSONL dataset into PostgreSQL."""
    path = dataset_path or settings.DATASET_PATH
    if not os.path.exists(path):
        msg = f"Dataset not found at: {path}"
        logger.warning(msg)
        return False, msg

    records = load_dataset_records(path)
    if not records:
        msg = f"No valid records found in {path}"
        return False, msg

    # Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        ins, upd = ingest_products(db, records)
        msg = f"Successfully ingested {len(records)} products ({ins} inserted, {upd} updated)"
        return True, msg
    except Exception as e:
        db.rollback()
        msg = f"Ingestion error: {e}"
        logger.error(msg, exc_info=True)
        return False, msg
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    success, message = run_dataset_ingestion()
    print(f"Ingestion Result: {message}")
    sys.exit(0 if success else 1)
