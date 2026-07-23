#!/usr/bin/env python3
"""
Daily Product Carousel Picker for ai.xinca.com

Queries Shopify Admin API for products from 4 categories, uses deepseek-v4-flash
to randomly select 3 per category (12 total) and generate SEO alt-text.
Writes to src/data/featured-products.json.

Schedule: daily 6am HKT (22:00 UTC)
"""
import json
import os
import random
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Optional, List, Dict

# ---------- CONFIG ----------
# Load env early (before DEEPSEEK_KEY resolution)
_env_file = Path(__file__).resolve().parent.parent / ".env.shopify"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            if _k not in os.environ:
                os.environ[_k] = _v

SHOPIFY_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "your-shopify-token-here")
SHOPIFY_API = "https://888ab7.myshopify.com/admin/api/2026-07/graphql.json"
DEEPSEEK_API = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

OUTPUT_FILE = Path(__file__).resolve().parent.parent / "src" / "data" / "featured-products.json"
PER_CATEGORY = 3  # 4 categories × 3 = 12 products

# Category → Shopify collection ID (or product_type query)
CATEGORIES = {
    "IAQ": {
        "collection_id": "gid://shopify/Collection/300407390294",
        "label": "Indoor Air Quality",
        "badge_color": "#7EBEC5",  # teal
    },
    "Air-side Controls": {
        "collection_id": "gid://shopify/Collection/312448843862",
        "label": "Damper Actuators",
        "badge_color": "#2ea3f2",  # blue
    },
    "Water-side Controls": {
        "collection_id": "gid://shopify/Collection/312448876630",
        "label": "Control Valves",
        "badge_color": "#329f5b",  # green
    },
    "IoT": {
        # IoT uses product_type filter since no clean collection exists
        "product_type_query": "(product_type:Sensors OR product_type:Detectors OR product_type:Controllers) AND (tag:LoRa OR tag:Modbus OR tag:BACnet OR tag:WiFi OR tag:NB-IoT OR tag:Wireless)",
        "label": "IoT & Sensors",
        "badge_color": "#32373c",  # dark
    },
}

# ---------- SHOPIFY GRAPHQL ----------
def gql(query: str, variables: Optional[Dict] = None) -> dict:
    """Execute a Shopify Admin GraphQL query."""
    body = json.dumps({"query": query, "variables": variables or {}})
    req = Request(SHOPIFY_API, data=body.encode(), method="POST")
    req.add_header("X-Shopify-Access-Token", SHOPIFY_TOKEN)
    req.add_header("Content-Type", "application/json")
    
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                if "errors" in data:
                    raise RuntimeError(f"GraphQL errors: {data['errors']}")
                return data["data"]
        except (HTTPError, URLError) as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Shopify API error after 3 attempts: {e}") from e

def fetch_category_products(collection_id: str, limit: int = 30) -> List[dict]:
    """Fetch products from a collection, returning more than needed for LLM selection."""
    query = """
    query($id: ID!, $first: Int!) {
      collection(id: $id) {
        products(first: $first, sortKey: CREATED, reverse: true) {
          edges {
            node {
              id
              title
              handle
              description
              productType
              tags
              vendor
              priceRangeV2 { minVariantPrice { amount currencyCode } }
              featuredImage { url altText }
              status
            }
          }
        }
      }
    }
    """
    data = gql(query, {"id": collection_id, "first": limit})
    products = []
    for edge in data.get("collection", {}).get("products", {}).get("edges", []):
        node = edge["node"]
        if node.get("status") == "ACTIVE" and node.get("featuredImage"):
            products.append(_normalize_product(node))
    return products

def fetch_iot_products(query_str: str, limit: int = 30) -> List[dict]:
    """Fetch IoT products using product query (no collection)."""
    gql_query = """
    query($q: String!, $first: Int!) {
      products(first: $first, query: $q, sortKey: CREATED_AT, reverse: true) {
        edges {
          node {
            id
            title
            handle
            description
            productType
            tags
            vendor
            priceRangeV2 { minVariantPrice { amount currencyCode } }
            featuredImage { url altText }
            status
          }
        }
      }
    }
    """
    data = gql(gql_query, {"q": query_str, "first": limit})
    products = []
    for edge in data.get("products", {}).get("edges", []):
        node = edge["node"]
        if node.get("status") == "ACTIVE" and node.get("featuredImage"):
            products.append(_normalize_product(node))
    return products

def _normalize_product(node: dict) -> dict:
    """Extract essential fields from Shopify product node."""
    img = node.get("featuredImage") or {}
    price = node.get("priceRangeV2", {}).get("minVariantPrice", {})
    return {
        "id": node["id"],
        "title": node["title"],
        "handle": node["handle"],
        "description": (node.get("description") or "")[:200],
        "productType": node.get("productType", ""),
        "vendor": node.get("vendor", ""),
        "tags": node.get("tags", []),
        "price": f"{price.get('amount', 'N/A')} {price.get('currencyCode', 'HKD')}",
        "image_url": img.get("url", ""),
        "image_alt": img.get("altText") or "",
        "url": f"https://shop.xinca.com/products/{node['handle']}",
        "available": node.get("status", "") == "ACTIVE",
        "inventory": 0,
    }

# ---------- LLM SELECTION ----------
def llm_pick_products(category_products: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
    """
    Feed candidate products to deepseek-v4-flash for random selection + alt-text writing.
    
    Returns: {"iaq": [...3], "air_side": [...3], "water_side": [...3], "iot": [...3]}
    """
    # Build prompt: for each category, show candidates, ask LLM to pick 3 and write alt-text
    candidates_text = ""
    for cat_name, products in category_products.items():
        cat_config = CATEGORIES[cat_name]
        candidates_text += f"\n## {cat_name} ({cat_config['label']}) — {len(products)} candidates\n"
        for i, p in enumerate(products):
            candidates_text += (
                f"  [{i}] {p['title']}\n"
                f"      handle: {p['handle']}\n"
                f"      vendor: {p['vendor']} | type: {p['productType']}\n"
                f"      tags: {', '.join(p['tags'][:5])}\n"
                f"      price: {p['price']}\n"
                f"      desc: {p['description'][:120]}\n\n"
            )

    date_seed = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_seed = random.randint(0, 9999)

    prompt = f"""You are a product curator for an HVAC controls e-commerce carousel. 
Today's seed: {date_seed}-{random_seed}. Use this for deterministic-but-random picks.

{candidates_text}

## Task
For EACH of the 4 categories above, pick {PER_CATEGORY} products using the seed for randomness:
- Prefer products with interesting/memorable titles and good descriptions.
- Ensure diversity within each category (different vendors, different use cases).
- Favor products that have descriptive tags and non-empty descriptions (better for SEO).

Then for EACH selected product, write an SEO-optimized alt-text:
- ≤ 15 words
- Include product model/variant keywords, key specifications, and HVAC application context
- Natural language, not keyword stuffing
- Example: "Belimo TF24-MFT 2.5Nm spring-return damper actuator for VAV box airflow control in commercial HVAC"

Output STRICT JSON (no markdown, no backticks):
{{
  "iaq": [
    {{"index": <candidate_index>, "alt": "<SEO alt-text>"}},
    ...
  ],
  "air_side": [...],
  "water_side": [...],
  "iot": [...]
}}"""

    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 3000,
    })
    req = Request(DEEPSEEK_API, data=body.encode(), method="POST")
    req.add_header("Authorization", f"Bearer {DEEPSEEK_KEY}")
    req.add_header("Content-Type", "application/json")
    
    print(f"  Calling deepseek-v4-flash...")
    with urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    
    raw = result["choices"][0]["message"]["content"]
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    
    selections = json.loads(raw)
    
    # Map indices back to full product data
    key_map = {
        "IAQ": "iaq",
        "Air-side Controls": "air_side",
        "Water-side Controls": "water_side",
        "IoT": "iot",
    }
    final = {}
    for cat_name, cat_key in key_map.items():
        picks = selections.get(cat_key, [])
        products = category_products[cat_name]
        final[cat_key] = []
        for pick in picks[:PER_CATEGORY]:
            idx = pick["index"]
            if 0 <= idx < len(products):
                p = products[idx].copy()
                p["alt"] = pick["alt"]
                final[cat_key].append(p)
    
    return final

# ---------- OUTPUT ----------
def write_json(data: Dict[str, List[dict]]):
    """Write featured-products.json with category metadata."""
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "deepseek-v4-flash",
        "categories": {},
    }
    for cat_key in ["iaq", "air_side", "water_side", "iot"]:
        products = data.get(cat_key, [])
        output["categories"][cat_key] = products
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(output, indent=2, ensure_ascii=False)
    OUTPUT_FILE.write_text(json_str)
    print(f"  Wrote {sum(len(v) for v in output['categories'].values())} products to {OUTPUT_FILE}")

# ---------- MAIN ----------
def main():
    print(f"🔄 Product Carousel Picker — {datetime.now(timezone.utc).isoformat()}")
    
    # Step 1: Fetch candidates from each category
    category_products = {}
    for cat_name, cat_config in CATEGORIES.items():
        print(f"\n  Fetching {cat_name} ({cat_config['label']})...")
        if "collection_id" in cat_config:
            products = fetch_category_products(cat_config["collection_id"], limit=30)
        else:
            products = fetch_iot_products(cat_config["product_type_query"], limit=30)
        print(f"    → {len(products)} available (in-stock, with image)")
        if len(products) < PER_CATEGORY:
            print(f"    ⚠️  Only {len(products)} available — need {PER_CATEGORY}")
        category_products[cat_name] = products
    
    # Step 2: LLM selection + alt-text
    if not DEEPSEEK_KEY:
        print("\n  ⚠️  DEEPSEEK_API_KEY not set — falling back to random picks")
        selected = _fallback_random_picks(category_products)
    else:
        print(f"\n  🧠 LLM product selection...")
        selected = llm_pick_products(category_products)
    
    # Step 3: Write output
    write_json(selected)
    
    # Step 4: Summary
    for cat_key, products in selected.items():
        print(f"\n  {cat_key}:")
        for p in products:
            print(f"    {p['title'][:60]} | {p['price']}")

    print(f"\n✅ Done. Ready for Astro build.")

def _fallback_random_picks(category_products: dict) -> Dict[str, List[dict]]:
    """Random fallback when no LLM key available."""
    result = {}
    for cat_name, products in category_products.items():
        key = {"IAQ": "iaq", "Air-side Controls": "air_side", "Water-side Controls": "water_side", "IoT": "iot"}[cat_name]
        picked = random.sample(products, min(PER_CATEGORY, len(products)))
        for p in picked:
            p["alt"] = f"{p['title']} — {p.get('productType', 'HVAC product')} by {p.get('vendor', 'XINCA')}"
        result[key] = picked
    return result

if __name__ == "__main__":
    main()
