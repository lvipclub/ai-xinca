#!/usr/bin/env python3
"""Parse the Shopify Knowledge Base FAQ corpus and generate Markdown files."""

import re
import json
import os

# Read the FAQ corpus
corpus_path = "/home/hermerr/workspace/shared/shopify-knowledge-base-faqs.md"
with open(corpus_path, "r") as f:
    content = f.read()

# Category mapping from corpus categories to our target categories
CATEGORY_MAP = {
    "STORE OVERVIEW & POLICIES": "products",
    "CONTROL VALVES": "water",
    "ACTUATORS": "controls",
    "SENSORS & MEASUREMENT": "controls",
    "THERMOSTATS & ROOM CONTROLLERS": "controls",
    "BUILDING AUTOMATION & CONTROLS": "controls",
    "CHILLERS, COOLING & REFRIGERATION": "water",
    "HEATING, BOILERS & WATER HEATERS": "water",
    "AIR HANDLING & VENTILATION": "air",
    "BRAND AUTHORITY & SPECIALTY": "products",
}

def slugify(text):
    """Convert text to URL-friendly slug."""
    # Remove question marks and special chars
    text = re.sub(r'[?.,!;:\'\"()]', '', text.lower())
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text.strip())
    text = re.sub(r'-+', '-', text)
    return text[:80].strip('-')

def short_title(question):
    """Create a short title from the question."""
    title = question.rstrip('?').strip()
    
    # Remove multi-word question prefixes
    patterns = [
        r'^what\s+(is|are|does|do|was|were)\s+',
        r'^how\s+(do|does|can|should|is|are)\s+',
        r'^where\s+(is|are|can|do|does)\s+',
        r'^when\s+(is|are|should|can|do)\s+',
        r'^why\s+(is|are|does|do|should)\s+',
        r'^(can|does|do|is|are|was|were)\s+',
    ]
    for pat in patterns:
        title = re.sub(pat, '', title, flags=re.IGNORECASE)
    
    title = title.strip()
    
    # Handle compound questions: take only the first part
    if ' and ' in title.lower():
        # Check if it's like "X and why do I need one"
        if re.search(r'\band\s+(why|how|what|when|where)\b', title, flags=re.IGNORECASE):
            title = re.split(r'\s+and\s+(?=why|how|what|when|where)', title, flags=re.IGNORECASE)[0]
    
    # Clean up leading articles for better titles
    title = re.sub(r'^(a|an|the)\s+', '', title, flags=re.IGNORECASE)
    
    # Fix common patterns from "does X / can I" questions
    title = re.sub(r'^XINCA sell\s+', 'XINCA sells ', title)
    title = re.sub(r'^XINCA carry\s+', 'XINCA carries ', title)
    title = re.sub(r'^XINCA help\s+', 'XINCA helps with ', title)
    title = re.sub(r'^XINCA ship\s+', 'XINCA ships ', title)
    title = re.sub(r'^XINCA (offer|provide|support|supply|have)\s+', r'XINCA \1s ', title)
    title = re.sub(r'^I (get|buy|contact|find|see|check|improve|retrofit|need|want|use|choose|replace|control|know|select)\s+', '', title)
    
    # Fix "What <noun> does/do XINCA <verb>" → "<Noun> XINCA <verb>s"
    title = re.sub(r'^What\s+(.+?)\s+(does|do)\s+XINCA\s+(.+)$', r'\1 XINCA \3', title)
    title = re.sub(r'^What\s+(.+?)\s+(are|is)\s+(.+)$', r'\1: \3', title)
    
    # Fix "How fast do / How long does" 
    title = re.sub(r'^How\s+(fast|long|often|much|many)\s+(do|does|can|should)\s+', '', title)
    
    # Fix "supplys" → "supplies" and double "with"
    title = title.replace('supplys', 'supplies')
    title = title.replace('with with', 'with')
    
    # Clean up leading articles (again, after I-verb removal)
    title = re.sub(r'^(a|an|the)\s+', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s+from\s+XINCA\s*$', '', title, flags=re.IGNORECASE)
    
    # Fix "where is" remnants
    title = re.sub(r'^XINCA located\s*$', 'XINCA Location', title)
    title = re.sub(r'^XINCA sell\s*$', 'XINCA Products', title)
    title = re.sub(r'^XINCA an authorized\s*$', 'XINCA Authorized Distributor Status', title)
    
    # Fix "If my actuator..." → "Actuator compatibility"
    title = re.sub(r'^If my\s+', '', title, flags=re.IGNORECASE)
    title = re.sub(r'^My existing\s+', '', title, flags=re.IGNORECASE)
    
    # Fix "XINCA an authorized distributor"
    title = re.sub(r'^XINCA an authorized', 'XINCA Authorized Distributor Status', title)
    
    # Fix "XINCA shipping take" → "XINCA shipping time"
    title = re.sub(r'^XINCA shipping take$', 'XINCA Shipping Time', title)
    
    # Fix leading "Right" → capitalize properly
    title = re.sub(r'^Right\s+', 'Selecting the right ', title)
    
    # Capitalize first letter
    title = title.strip()
    if title:
        title = title[0].upper() + title[1:]
    else:
        title = question.rstrip('?').strip()
    
    # Limit length
    if len(title) > 60:
        title = title[:57] + '...'
    return title

# Parse categories and FAQs
faqs = []
current_category = None
category_counts = {}

# Split into sections
sections = re.split(r'\n## \d+\.\s+', content)
# First section is the header, skip it

for section in sections[1:]:  # Skip the header
    lines = section.strip().split('\n')
    # First line is the category name like "STORE OVERVIEW & POLICIES (14 FAQs)"
    category_line = lines[0].strip()
    category_name = re.sub(r'\s*\(\d+\s*FAQs\)', '', category_line).strip()
    
    # Map to target category
    target_cat = CATEGORY_MAP.get(category_name, "products")
    
    # Parse table rows
    for line in lines:
        # Match table rows like: | 1 | What does XINCA sell? | XINCA is a specialized... |
        match = re.match(r'\|\s*\d+\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|', line)
        if match:
            question = match.group(1).strip()
            answer = match.group(2).strip()
            
            slug = slugify(question)
            title = short_title(question)
            
            faqs.append({
                "question": question,
                "answer": answer,
                "slug": slug,
                "title": title,
                "category": target_cat,
                "original_category": category_name,
            })
            
            if target_cat not in category_counts:
                category_counts[target_cat] = 0
            category_counts[target_cat] += 1

print(f"Parsed {len(faqs)} FAQs across {len(category_counts)} categories")
for cat, count in sorted(category_counts.items()):
    print(f"  {cat}: {count}")

# Write individual FAQ files
base_dir = "/home/hermerr/workspace/ai-xinca/src/content/faq"
written = 0

for faq in faqs:
    cat_dir = os.path.join(base_dir, faq["category"])
    filepath = os.path.join(cat_dir, f"{faq['slug']}.md")
    
    # Build markdown content
    md = f"""---
title: '{faq["title"]}'
category: '{faq["category"]}'
---
# {faq["question"]}

{faq["answer"]}

---

**Related products:** [Browse HVAC Products at XINCA](https://www.xincashop.com)
"""
    
    with open(filepath, "w") as f:
        f.write(md)
    written += 1

print(f"\nWrote {written} FAQ files to {base_dir}")

# Write categories.json index
categories_json = {
    "description": "XINCA HVAC FAQ Categories",
    "source": "xincashop.com Shopify Knowledge Base",
    "total_faqs": len(faqs),
    "categories": {}
}

for cat in ["air", "water", "fluid", "controls", "products"]:
    count = category_counts.get(cat, 0)
    categories_json["categories"][cat] = {
        "name": {
            "air": "Air-side HVAC",
            "water": "Water-side HVAC",
            "fluid": "Fluid Handling",
            "controls": "Building Controls",
            "products": "Product-specific"
        }[cat],
        "description": {
            "air": "Air-side HVAC (dampers, VAV, air distribution)",
            "water": "Water-side HVAC (valves, coils, hydronics)",
            "fluid": "Fluid handling (flow sensors, pressure)",
            "controls": "Building controls (actuators, sensors, BMS)",
            "products": "Product-specific (installation, compatibility)"
        }[cat],
        "count": count
    }

index_path = os.path.join(base_dir, "categories.json")
with open(index_path, "w") as f:
    json.dump(categories_json, f, indent=2)

print(f"Wrote categories index to {index_path}")
print("\nSample entries:")
for faq in faqs[:3]:
    print(f"  [{faq['category']}] {faq['slug']}.md → {faq['title']}")
for faq in faqs[-3:]:
    print(f"  [{faq['category']}] {faq['slug']}.md → {faq['title']}")
