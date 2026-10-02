#!/usr/bin/env python3
"""Collect real Poorvika products from official listing and detail pages."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "poorvika_products.jsonl"
OUTPUT = ROOT / "data" / "poorvika_products_expanded.jsonl"
REPORT = ROOT / "data" / "poorvika_scrape_report.json"
BASE = "https://www.poorvika.com"
START_URLS = [f"{BASE}/mobiles-accessories/s"]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
DELAY_SECONDS = 1.2
TIMEOUT_SECONDS = 20
RETRIES = 3
TARGET = 900
MAX_PRODUCTS = 1000


def official(url: str) -> bool:
    return urlparse(url).netloc.lower() in {"poorvika.com", "www.poorvika.com"}


def robots_rules(session: requests.Session) -> RobotFileParser:
    response = session.get(f"{BASE}/robots.txt", timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    rules = RobotFileParser(f"{BASE}/robots.txt")
    rules.parse(response.text.splitlines())
    return rules


def fetch(session: requests.Session, robots: RobotFileParser, url: str) -> str:
    if not official(url):
        raise ValueError(f"Refusing non-Poorvika URL: {url}")
    if not robots.can_fetch(USER_AGENT, url):
        raise PermissionError(f"robots.txt disallows {url}")
    error = None
    for attempt in range(RETRIES):
        time.sleep(DELAY_SECONDS * (attempt + 1))
        try:
            response = session.get(url, timeout=TIMEOUT_SECONDS)
            if response.status_code in (401, 403, 429, 503):
                raise PermissionError(f"HTTP {response.status_code} for {url}; stopping")
            response.raise_for_status()
            return response.text
        except PermissionError:
            raise
        except requests.RequestException as exc:
            error = exc
    raise requests.RequestException(f"Failed to fetch {url}: {error}")


def product_and_listing_links(html: str, page_url: str) -> tuple[set[str], set[str]]:
    soup = BeautifulSoup(html, "html.parser")
    products, listings = set(), set()
    for anchor in soup.select("a[href]"):
        url = urljoin(page_url, anchor.get("href", "")).split("#", 1)[0]
        if not official(url):
            continue
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if re.search(r"/p$", path, re.I):
            products.add(url)
        elif path.lower().endswith("/s"):
            listings.add(url)
        elif anchor.get("rel") and "next" in anchor.get("rel", []):
            listings.add(url)
    return products, listings


def product_nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from product_nodes(item)
    elif isinstance(value, dict):
        if value.get("@type") == "Product" or (isinstance(value.get("@type"), list) and "Product" in value["@type"]):
            yield value
        for key, item in value.items():
            if key in {"@graph", "mainEntity", "itemListElement"}:
                yield from product_nodes(item)


def text_value(value):
    if isinstance(value, dict):
        return value.get("name") or value.get("@id")
    return value


def scalar_price(offers, key):
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if not isinstance(offers, dict):
        return None
    val = offers.get(key)
    try:
        number = float(val)
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return None


def parse_product(html: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    product = None
    source = None
    for tag in soup.select('script[type="application/ld+json"]'):
        raw = tag.string or tag.get_text()
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        product = next(product_nodes(parsed), None)
        if product is not None:
            source = raw
            break
    if not product or not isinstance(product.get("name"), str) or not product["name"].strip():
        return None
    canonical_tag = soup.find("link", rel="canonical")
    canonical = urljoin(url, canonical_tag.get("href", "")) if canonical_tag else url
    if not official(canonical):
        canonical = url
    offers = product.get("offers")
    brand = text_value(product.get("brand"))
    images = product.get("image") or []
    if isinstance(images, str):
        images = [images]
    if not isinstance(images, list):
        images = []
    images = [urljoin(url, item) for item in images if isinstance(item, str)]
    rating = product.get("aggregateRating") or {}
    availability = offers.get("availability") if isinstance(offers, dict) else None
    sku = product.get("sku") or product.get("mpn")
    product_id = product.get("productID") or product.get("productId") or sku
    normalized = {
        "url": url,
        "canonical_url": canonical,
        "name": product["name"].strip(),
        "brand": brand,
        "model": product.get("model"),
        "sku": sku,
        "product_id": product_id,
        "item_code": None,
        "erp_item_code": None,
        "online_price": scalar_price(offers, "price"),
        "mrp": scalar_price(offers, "highPrice"),
        "shop_price": None,
        "currency": offers.get("priceCurrency") if isinstance(offers, dict) else None,
        "availability": availability,
        "stock": None,
        "rating": scalar_price(rating, "ratingValue"),
        "rating_count": scalar_price(rating, "reviewCount") or scalar_price(rating, "ratingCount"),
        "description": product.get("description"),
        "images": images,
        "specifications": {"attributeGroups": [], "attributeHighlights": []},
        "source_hash": hashlib.sha256((source or "").encode("utf-8")).hexdigest(),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    return normalized


def identities(product: dict) -> set[str]:
    values = [product.get("product_id"), product.get("sku"), product.get("canonical_url"), product.get("url"),
              f"{product.get('brand') or ''} {product.get('name') or ''}"]
    return {re.sub(r"[^a-z0-9]", "", str(value).casefold()) for value in values if value}


def main() -> int:
    original_lines = [line for line in INPUT.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = [json.loads(line) for line in original_lines]
    seen = set().union(*(identities(record) for record in records)) if records else set()
    report = {"source": BASE + "/", "existing_records": len(records), "new_records": 0,
              "duplicates_removed": 0, "final_records": len(records), "synthetic_records": 0,
              "validation_passed": False, "categories": {}, "visited_listing_pages": 0,
              "visited_product_pages": 0, "failed_pages": []}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"})
    listings = list(START_URLS)
    visited_listings, product_urls, visited_products = set(), set(), set()
    try:
        robots = robots_rules(session)
        while listings and len(visited_listings) < 200 and len(records) < MAX_PRODUCTS:
            listing_url = listings.pop(0)
            if listing_url in visited_listings:
                continue
            visited_listings.add(listing_url)
            report["visited_listing_pages"] = len(visited_listings)
            try:
                html = fetch(session, robots, listing_url)
                found_products, found_listings = product_and_listing_links(html, listing_url)
                product_urls.update(found_products)
                listings.extend(sorted(found_listings - visited_listings - set(listings)))
            except Exception as exc:
                report["failed_pages"].append({"url": listing_url, "reason": str(exc)})
        for product_url in sorted(product_urls):
            if len(records) >= MAX_PRODUCTS:
                break
            if product_url in visited_products:
                continue
            visited_products.add(product_url)
            report["visited_product_pages"] = len(visited_products)
            try:
                html = fetch(session, robots, product_url)
                record = parse_product(html, product_url)
                if record is None:
                    raise ValueError("No Product JSON-LD found; refusing to synthesize fields")
                keys = identities(record)
                if seen.intersection(keys):
                    report["duplicates_removed"] += 1
                    continue
                seen.update(keys)
                records.append(record)
            except Exception as exc:
                report["failed_pages"].append({"url": product_url, "reason": str(exc)})
        report["new_records"] = len(records) - report["existing_records"]
        report["final_records"] = len(records)
        report["validation_passed"] = len(records) >= TARGET and len(records) <= MAX_PRODUCTS and all(official(r.get("url", "")) for r in records)
        if report["validation_passed"]:
            OUTPUT.write_text("\n".join(original_lines + [json.dumps(r, ensure_ascii=False) for r in records[len(original_lines):]]) + "\n", encoding="utf-8")
    except Exception as exc:
        report["failed_pages"].append({"url": f"{BASE}/robots.txt", "reason": str(exc)})
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Existing records: {report['existing_records']}")
    print(f"New records: {report['new_records']}")
    print(f"Duplicates removed: {report['duplicates_removed']}")
    print(f"Final records: {report['final_records']}")
    print("Synthetic records: 0")
    print(f"Listing pages visited: {report['visited_listing_pages']}")
    print(f"Product pages visited: {report['visited_product_pages']}")
    print(f"Failed product pages: {len(report['failed_pages'])}")
    return 0 if report["validation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
