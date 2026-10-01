"""Product SQLAlchemy Model reflecting the real Poorvika dataset."""

from sqlalchemy import Column, String, Float, Integer, Text, Boolean, JSON, DateTime
from app.database.base import Base


class Product(Base):
    """PostgreSQL Products table schema preserving all source dataset attributes."""

    __tablename__ = "products"

    # Core Identifiers
    id = Column(String(150), primary_key=True, index=True)  # maps to product_id
    name = Column(String(255), nullable=False, index=True)
    brand = Column(String(100), nullable=False, index=True)
    model = Column(String(150), nullable=True)
    category = Column(String(100), nullable=False, index=True)  # Extracted from Generic Name
    sku = Column(String(100), nullable=True, unique=True, index=True)
    item_code = Column(String(50), nullable=True)
    erp_item_code = Column(String(50), nullable=True)

    # Pricing & Currency
    price = Column(Float, nullable=False, index=True)  # online_price
    online_price = Column(Float, nullable=False)
    mrp = Column(Float, nullable=True)
    shop_price = Column(Float, nullable=True)
    discount_percent = Column(Float, default=0.0, index=True)
    currency = Column(String(10), default="INR")

    # Stock & Availability
    in_stock = Column(Boolean, default=True, index=True)
    stock = Column(Integer, default=0, index=True)
    availability = Column(String(100), nullable=False)

    # Ratings & Reviews
    rating = Column(Float, nullable=True, index=True)
    rating_count = Column(Integer, default=0)

    # Content & Media
    image = Column(Text, nullable=True)  # Primary display image
    images = Column(JSON, nullable=True)  # Array of all image URLs
    description = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    canonical_url = Column(Text, nullable=True)

    # Specifications & Metadata
    specifications = Column(JSON, nullable=True)  # Raw attributeGroups & attributeHighlights
    flattened_specs = Column(JSON, nullable=True)  # Key-value map of specifications
    source_hash = Column(String(100), nullable=True)
    scraped_at = Column(String(50), nullable=True)

    def to_dict(self):
        """Converts model to dictionary including all database attributes."""
        return {
            "id": self.id,
            "product_id": self.id,
            "name": self.name,
            "brand": self.brand,
            "model": self.model,
            "category": self.category,
            "sku": self.sku,
            "item_code": self.item_code,
            "erp_item_code": self.erp_item_code,
            "price": self.price,
            "online_price": self.online_price,
            "mrp": self.mrp,
            "shop_price": self.shop_price,
            "discount_percent": self.discount_percent,
            "currency": self.currency,
            "in_stock": self.in_stock,
            "stock": self.stock,
            "availability": self.availability,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "image": self.image,
            "images": self.images or [],
            "description": self.description,
            "url": self.url,
            "canonical_url": self.canonical_url,
            "specifications": self.specifications or {},
            "flattened_specs": self.flattened_specs or {},
            "source_hash": self.source_hash,
            "scraped_at": self.scraped_at,
        }

    def to_frontend_dict(self):
        """Formats model to match frontend Product interface (api.ts)."""
        return {
            "id": self.id,
            "name": self.name,
            "brand": self.brand,
            "price": self.price,
            "originalPrice": self.mrp,
            "discount": self.discount_percent,
            "image": self.image,
            "images": self.images or ([self.image] if self.image else []),
            "category": self.category,
            "rating": self.rating,
            "reviewCount": self.rating_count,
            "inStock": self.in_stock,
            "description": self.description,
            "specifications": self.flattened_specs or {},
        }
