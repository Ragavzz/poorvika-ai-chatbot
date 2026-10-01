"""Pydantic schemas for Product catalog and search APIs."""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class ProductOut(BaseModel):
    """Product schema serialized for frontend presentation."""
    id: str = Field(..., description="Unique product ID slug")
    name: str = Field(..., description="Product title")
    brand: str = Field(..., description="Brand name")
    category: str = Field(..., description="Product category")
    model: Optional[str] = None
    sku: Optional[str] = None
    item_code: Optional[str] = None
    erp_item_code: Optional[str] = None
    
    # Pricing
    price: float = Field(..., description="Active selling price in INR")
    originalPrice: Optional[float] = Field(None, description="Original MRP in INR")
    online_price: Optional[float] = None
    mrp: Optional[float] = None
    discount: Optional[float] = Field(0.0, description="Discount percentage")
    currency: str = "INR"

    # Stock & Availability
    inStock: bool = Field(True, description="In-stock boolean")
    stock: int = Field(0, description="Exact stock count")
    availability: str = Field(..., description="Schema.org availability URI")

    # Reviews
    rating: Optional[float] = None
    reviewCount: Optional[int] = Field(0, description="Rating count")

    # Content
    image: Optional[str] = Field(None, description="Display image URL")
    images: List[str] = Field(default_factory=list, description="Array of image URLs")
    description: Optional[str] = None
    url: Optional[str] = None

    # Specifications
    specifications: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(
        default_factory=dict, description="Specifications mapping"
    )

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Container response for product lists."""
    products: List[ProductOut]
    total: int


class ProductQuery(BaseModel):
    """Query parameters for filtering products."""
    query: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[Union[str, List[str]]] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    sort: Optional[str] = None
    limit: Optional[int] = 50
