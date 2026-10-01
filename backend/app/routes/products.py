"""Product catalog, search, and ingestion API routes."""

import logging
from typing import Optional, List, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.product import Product
from app.tools.product_search_tool import ProductSearchTool
from app.database.ingest import run_dataset_ingestion

logger = logging.getLogger("shopai.routes.products")

products_router = APIRouter(prefix="/api", tags=["Products"])


@products_router.get("/products")
async def get_products(
    category: Optional[str] = Query(None, description="Category filter"),
    brand: Optional[List[str]] = Query(None, description="Brand filter(s)"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    sort: Optional[str] = Query(None, description="Sorting parameter"),
    limit: Optional[int] = Query(50, description="Max records to return"),
    db: Session = Depends(get_db),
):
    """
    Retrieves catalog products matching optional category, brand, and price filters.
    Returns normalized product list compatible with the React storefront.
    """
    tool = ProductSearchTool(db)
    items = tool.search_products(
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort,
        limit=limit or 50,
    )
    # Return formatted list expected by frontend api.ts
    formatted = []
    for item in items:
        prod = db.query(Product).filter(Product.id == item["id"]).first()
        if prod:
            formatted.append(prod.to_frontend_dict())
    return formatted


@products_router.get("/products/search")
async def search_products(
    q: Optional[str] = Query(None, description="Search query keyword"),
    category: Optional[str] = Query(None, description="Category filter"),
    brand: Optional[List[str]] = Query(None, description="Brand filter(s)"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    sort: Optional[str] = Query(None, description="Sorting parameter"),
    limit: Optional[int] = Query(50, description="Max records to return"),
    db: Session = Depends(get_db),
):
    """
    Performs full text and multi-faceted product search across the PostgreSQL catalog.
    """
    tool = ProductSearchTool(db)
    items = tool.search_products(
        query=q,
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort,
        limit=limit or 50,
    )
    formatted = []
    for item in items:
        prod = db.query(Product).filter(Product.id == item["id"]).first()
        if prod:
            formatted.append(prod.to_frontend_dict())
    return formatted


@products_router.get("/products/{product_id}")
async def get_product(product_id: str, db: Session = Depends(get_db)):
    """Retrieves single product details by ID."""
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' not found.",
        )
    return prod.to_frontend_dict()


@products_router.post("/products/ingest")
async def trigger_ingest():
    """Triggers reload and ingestion of the JSONL dataset into PostgreSQL."""
    success, msg = run_dataset_ingestion()
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg)
    return {"status": "success", "message": msg}


@products_router.get("/categories")
async def get_categories(db: Session = Depends(get_db)):
    """Returns list of all distinct product categories in PostgreSQL."""
    cats = db.query(Product.category).distinct().filter(Product.category != None).all()
    return sorted([c[0] for c in cats if c[0]])


@products_router.get("/brands")
async def get_brands(db: Session = Depends(get_db)):
    """Returns list of all distinct brands in PostgreSQL."""
    brands = db.query(Product.brand).distinct().filter(Product.brand != None).all()
    return sorted([b[0] for b in brands if b[0]])
