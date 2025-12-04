#!/usr/bin/env python3
"""
scrape_products.py

Scrape Floor & Decor product metadata & rich details (DCOF, specs,
install docs, recommended materials) for a single store, and store
everything in a normalized SQLite database.

This is the *offline* data-population step for your FND Agent:
  - At scrape time: hit the website for a store (e.g. San Leandro storeID=238),
    crawl all relevant flooring categories, and write into SQLite.
  - At query time: your FastAPI agent reads from SQLite only (no scraping).

Usage examples (from repo root, with your venv activated):

    # Scrape all products for San Leandro (storeID=238) into data/fnd_products.db
    python scrape_products.py --store-id 238

    # Scrape another store into the same DB (will reuse rows by SKU)
    python scrape_products.py --store-id 999

    # Customize DB path and scrape TTL (re-scrape anything older than 3 days)
    python scrape_products.py --store-id 238 --db data/fnd_products.db --ttl-days 3

Schema (created automatically if missing):

    products(
        sku TEXT PRIMARY KEY,
        name TEXT,
        url TEXT UNIQUE,
        category_slug TEXT,
        price_per_sqft TEXT,
        price_per_box TEXT,
        size_primary TEXT,
        color TEXT,
        finish TEXT,
        store_id INTEGER,
        last_scraped_at TEXT
    )

    product_specs(
        sku TEXT,
        spec_key TEXT,
        spec_value TEXT,
        PRIMARY KEY (sku, spec_key)
    )

    product_documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        doc_label TEXT,
        doc_url TEXT
    )

    product_recommended_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        rec_name TEXT,
        rec_url TEXT,
        rec_sku TEXT
    )

NOTE: Right now SKU is treated as global-primary-key. If you later need
true multi-store pricing/availability per SKU in one DB, you can split
into a global product table + a store_products table keyed by (sku, store_id).
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# ---------------------- CONSTANTS ----------------------

BASE_URL = "https://www.flooranddecor.com"

# Initial "surface" categories. We will expand this via the /sitemap page.
CATEGORY_SLUGS = [
    "/tile",
    "/stone",
    "/wood",
    "/decoratives",
]

# Where the SQLite DB lives by default
DEFAULT_DB_PATH = Path("data") / "fnd_products.db"

REQUEST_TIMEOUT = 15
SLEEP_BETWEEN_REQUESTS = 0.5  # politeness
MAX_PAGES_PER_CATEGORY = 10_000  # safety valve

# Product detail URLs look like:
#   https://www.flooranddecor.com/porcelain-tile/alto-bianco-porcelain-tile-101053254.html
PRODUCT_URL_RE = re.compile(
    r"https://www\.flooranddecor\.com/[A-Za-z0-9_\-/]+-(\d{6,})\.html"
)

# Category / URL substrings we want to completely avoid crawling
EXCLUDE_CATEGORY_SUBSTRINGS = [
    # Big buckets
    "installation-materials",
    "installation",
    "decorative-hardware",
    "cabinet-hardware",
    "vanities",
    "vanity",
    "countertops",
    "countertop",
    "slab",
    "doors",
    "door",
    "moulding",
    "molding",
    "baseboard",
    "trim",
    "stairs",  # stair parts often installation-ish
    # Grout / thinset / adhesives (kept out of *crawling* phase)
    "grout",
    "thinset",
    "thin-set",
    "mortar",
    "adhesive",
    "underlayment",
    "membrane",
]

# Product name tokens we consider "not tiles/wood/deco" even if they slipped in
EXCLUDE_PRODUCT_NAME_TOKENS = [
    # Installation materials
    "thinset",
    "thin-set",
    "mortar",
    "grout",
    "adhesive",
    "underlayment",
    "membrane",
    "primer",
    "spacer",
    "trowel",
    "saw",
    "blade",
    "bucket",
    "tape",
    "float",
    "drill",
    "sponge",
    # Plumbing / fixtures / hardware you don't care about for surfaces
    "faucet",
    "faucets",
    "toilet",
    "toilets",
    "sink",
    "sinks",
    "vanity",
    "vanities",
    "mirror",
    "mirrors",
    "countertop",
    "countertops",
    "slab",
    "slabs",
    "cabinet",
    "cabinets",
    "shower head",
    "showerhead",
    "shower base",
    "shower door",
    "shower doors",
    "niche",
    "niches",
    # Doors / knobs / pulls
    "closet door",
    "closet doors",
    "barn door",
    "barn doors",
    "interior door",
    "interior doors",
    "exterior door",
    "exterior doors",
    "knob",
    "knobs",
    "pull",
    "pulls",
    "handle",
    "handles",
    "hinge",
    "hinges",
    "lever",
    "levers",
    "cabinet hardware",
    "cabinet knob",
    "cabinet pull",
]

# Labels we care about from spec-like sections
SPEC_LABELS = [
    # Dimensions
    "Size",
    "Product Length (inches)",
    "Product Width (inches)",
    "Product Thickness",
    "Box Length",
    "Box Width",
    "Box Weight",
    "Box Quantity",
    "Coverage (sqft/pc)",
    "PEI Rating",
    "DCOF Value",
    "Water Absorption",
    # Details
    "Material",
    "Color",
    "Edge",
    "Finish",
    "Look",
    "Water Resistance",
    "Frost Resistance",
    "Print Quality",
    # Installation & Warranty
    "Suggested Grout Line Size",
    "Installation Type",
    "Placement Location",
    "Installation Options",
    "Shower Surface",
    "Radiant Heat Compatible",
    "Floor Suitability Rating",
    "Bathroom Floor Use",
    "Fireplace Surround Use",
]


# ---------------------- DATA CLASSES ----------------------


@dataclass
class ProductBasic:
    sku: Optional[str]
    name: Optional[str]
    url: str
    category_slug: Optional[str]
    price_per_sqft: Optional[str]
    price_per_box: Optional[str]
    size_primary: Optional[str]
    color: Optional[str]
    finish: Optional[str]
    store_id: Optional[int] = None


# ---------------------- LOGGING ----------------------


def init_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


# ---------------------- DB SETUP ----------------------


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            name TEXT,
            url TEXT UNIQUE,
            category_slug TEXT,
            price_per_sqft TEXT,
            price_per_box TEXT,
            size_primary TEXT,
            color TEXT,
            finish TEXT,
            store_id INTEGER,
            last_scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS product_specs (
            sku TEXT NOT NULL,
            spec_key TEXT NOT NULL,
            spec_value TEXT,
            PRIMARY KEY (sku, spec_key),
            FOREIGN KEY (sku) REFERENCES products(sku) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS product_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            doc_label TEXT,
            doc_url TEXT,
            FOREIGN KEY (sku) REFERENCES products(sku) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS product_recommended_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL,
            rec_name TEXT,
            rec_url TEXT,
            rec_sku TEXT,
            FOREIGN KEY (sku) REFERENCES products(sku) ON DELETE CASCADE
        );
        """
    )
    conn.commit()
    return conn


def get_existing_last_scraped(conn: sqlite3.Connection, sku: str) -> Optional[datetime]:
    cur = conn.cursor()
    cur.execute("SELECT last_scraped_at FROM products WHERE sku = ?", (sku,))
    row = cur.fetchone()
    if not row or not row[0]:
        return None
    try:
        return datetime.fromisoformat(row[0])
    except Exception:
        return None


def upsert_product(conn: sqlite3.Connection, basic: ProductBasic) -> None:
    if basic.sku is None:
        raise ValueError(f"Missing SKU for product URL={basic.url}")

    now_iso = datetime.utcnow().isoformat()
    logging.info("Upserting product SKU=%s", basic.sku)
    conn.execute(
        """
        INSERT INTO products (
            sku, name, url, category_slug,
            price_per_sqft, price_per_box,
            size_primary, color, finish,
            store_id, last_scraped_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sku) DO UPDATE SET
            name = excluded.name,
            url = excluded.url,
            category_slug = excluded.category_slug,
            price_per_sqft = excluded.price_per_sqft,
            price_per_box = excluded.price_per_box,
            size_primary = excluded.size_primary,
            color = excluded.color,
            finish = excluded.finish,
            store_id = excluded.store_id,
            last_scraped_at = excluded.last_scraped_at;
        """,
        (
            basic.sku,
            basic.name,
            basic.url,
            basic.category_slug,
            basic.price_per_sqft,
            basic.price_per_box,
            basic.size_primary,
            basic.color,
            basic.finish,
            basic.store_id,
            now_iso,
        ),
    )
    conn.commit()


def save_specs(conn: sqlite3.Connection, sku: str, specs: Dict[str, str]) -> None:
    logging.info("  -> specs: %d entries", len(specs))
    cur = conn.cursor()
    cur.execute("DELETE FROM product_specs WHERE sku = ?", (sku,))
    cur.executemany(
        "INSERT INTO product_specs (sku, spec_key, spec_value) VALUES (?, ?, ?)",
        [(sku, key, value) for key, value in specs.items()],
    )
    conn.commit()


def save_docs(
    conn: sqlite3.Connection, sku: str, docs: List[Tuple[str, str]]
) -> None:
    logging.info("  -> docs: %d links", len(docs))
    cur = conn.cursor()
    cur.execute("DELETE FROM product_documents WHERE sku = ?", (sku,))
    cur.executemany(
        "INSERT INTO product_documents (sku, doc_label, doc_url) VALUES (?, ?, ?)",
        [(sku, label, href) for (label, href) in docs],
    )
    conn.commit()


def save_recommended(
    conn: sqlite3.Connection, sku: str, recs: List[Tuple[str, str]]
) -> None:
    logging.info("  -> recommended: %d items", len(recs))
    cur = conn.cursor()
    cur.execute("DELETE FROM product_recommended_items WHERE sku = ?", (sku,))
    rows = []
    for name, href in recs:
        rec_sku = extract_sku_from_url(href)
        rows.append((sku, name, href, rec_sku))
    cur.executemany(
        """
        INSERT INTO product_recommended_items (sku, rec_name, rec_url, rec_sku)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


# ---------------------- HTTP / STORE CONTEXT ----------------------


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return s


def set_store_context(session: requests.Session, store_id: int) -> None:
    """
    Hit the store selector URL so cookies / context are set
    for the desired store (e.g., storeID=238 for San Leandro).
    """
    url = f"{BASE_URL}/store?storeID={store_id}"
    try:
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        logging.info(
            "Store context response: %s %s", r.status_code, url
        )
    except Exception as e:
        logging.warning("Failed to set store context: %s", e)


# ---------------------- DISCOVERY HELPERS ----------------------


def url_is_excluded(url: str) -> bool:
    """
    Return True if this URL looks like an installation-material / vanity /
    countertop / door / hardware thing that we don't want.
    """
    path = urlparse(url).path.lower()
    return any(bad in path for bad in EXCLUDE_CATEGORY_SUBSTRINGS)


def discover_category_slugs(session: requests.Session) -> List[str]:
    """
    Hit the site-wide sitemap and collect a broad set of category-like URLs.
    We:
      * start from CATEGORY_SLUGS
      * add any internal, non-product URL whose path contains flooring-ish
        keywords (tile, wood, vinyl, laminate, floor, wall, etc.), while
        skipping installation materials, vanities, countertops, doors, hardware.
    """
    sitemap_url = urljoin(BASE_URL, "/sitemap")
    slugs: Set[str] = set(CATEGORY_SLUGS)

    try:
        r = session.get(sitemap_url, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            logging.warning(
                "Sitemap %s returned status %s", sitemap_url, r.status_code
            )
            return sorted(slugs)
    except Exception as e:
        logging.warning("Failed to fetch sitemap %s: %s", sitemap_url, e)
        return sorted(slugs)

    soup = BeautifulSoup(r.text, "html.parser")

    category_keywords = [
        "tile",
        "stone",
        "wood",
        "vinyl",
        "laminate",
        "floor",
        "wall",
        "stair",
        "decor",
        "mosaic",
        "backsplash",
    ]

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        # Only internal paths
        if href.startswith("http"):
            parsed = urlparse(href)
            if "flooranddecor.com" not in (parsed.netloc or ""):
                continue
            path = parsed.path
        else:
            path = href

        if not path.startswith("/"):
            continue

        low = path.lower()

        # Skip explicit "bad" categories globally
        if any(bad in low for bad in EXCLUDE_CATEGORY_SUBSTRINGS):
            continue

        # Skip obvious leaf product pages
        if low.endswith(".html"):
            continue

        if any(kw in low for kw in category_keywords):
            slugs.add(path)

    logging.info("Discovered %d category-like slugs from sitemap", len(slugs))
    return sorted(slugs)


def fetch_product_urls_for_category(
    session: requests.Session, category_slug: str
) -> Set[str]:
    """
    Given a category slug like "/tile", crawl listing / filter / search pages
    reachable under that slug and extract product detail URLs using PRODUCT_URL_RE.

    Strategy (high-level):
      * BFS from the base category URL.
      * Any link whose URL looks like a product detail page is recorded.
      * Any link that looks like another listing/filter page for that category
        is added to the queue (bounded by MAX_PAGES_PER_CATEGORY).
      * We avoid installation-material / vanity / countertop / doors / hardware
        sections by checking EXCLUDE_CATEGORY_SUBSTRINGS.
    """
    start_url = urljoin(BASE_URL, category_slug)
    visited: Set[str] = set()
    to_visit: List[str] = [start_url]
    found_urls: Set[str] = set()

    cat_token = category_slug.strip("/").split("/")[0].lower() if category_slug else ""

    while to_visit and len(visited) < MAX_PAGES_PER_CATEGORY:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        logging.info(
            "Scanning category page (%d pages seen) %s", len(visited), url
        )
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
        except Exception as e:
            logging.warning("Failed to fetch category %s: %s", url, e)
            continue

        content_type = r.headers.get("Content-Type", "")
        if r.status_code != 200 or "text/html" not in content_type:
            logging.warning(
                "Category %s returned status %s (Content-Type=%s)",
                url,
                r.status_code,
                content_type,
            )
            continue

        html = r.text

        # Collect product URLs from this page
        for match in PRODUCT_URL_RE.finditer(html):
            full_url = match.group(0)
            if url_is_excluded(full_url):
                continue
            found_urls.add(full_url)

        # Discover more listing pages to crawl
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith("#"):
                continue
            if href.lower().startswith("javascript:"):
                continue

            full = urljoin(BASE_URL, href)
            if full in visited:
                continue

            parsed = urlparse(full)
            # Stay on main domain
            if parsed.netloc and "flooranddecor.com" not in parsed.netloc:
                continue

            # If this anchor itself is a product detail URL, just record it
            if PRODUCT_URL_RE.search(full):
                if not url_is_excluded(full):
                    found_urls.add(full)
                continue

            href_low = href.lower()

            # Don't even walk into "bad" sections
            if any(bad in href_low for bad in EXCLUDE_CATEGORY_SUBSTRINGS):
                continue

            # Decide if this looks like a listing/filter/search page
            in_same_family = False

            # Same slug (/tile, /tile/..., /tile?... etc.)
            if category_slug.lower() in href_low:
                in_same_family = True
            # Or category token in query path (/search?cgid=tile-xxx, etc.)
            elif cat_token and cat_token in href_low:
                in_same_family = True

            if not in_same_family:
                continue

            to_visit.append(full)

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    logging.info(
        "Category %s -> %d candidate product URLs from %d listing pages (cap=%d)",
        category_slug,
        len(found_urls),
        len(visited),
        MAX_PAGES_PER_CATEGORY,
    )
    return found_urls


# ---------------------- AVAILABILITY FILTER ----------------------


def is_available_in_store(soup: BeautifulSoup) -> bool:
    """
    Heuristically determine if the product is actually stocked at the current store
    (after set_store_context has been called).

    Logic:
      - Find the 'In-Store Pickup' block.
      - If that block says 'Item will be shipped and should arrive in X days',
        'not available at this store', 'online only', etc -> treat as NOT stocked.
      - Otherwise, keep it.
    """
    pickup_node = soup.find(
        string=lambda t: isinstance(t, NavigableString)
        and "In-Store Pickup" in t
    )

    # If we can't find it, don't over-filter; assume it's fine
    if not pickup_node:
        return True

    # Walk up ancestors to find the "card" that contains the pickup text
    current: Optional[Tag] = pickup_node.parent
    for _ in range(5):
        if current is None:
            break

        text = current.get_text(separator=" ", strip=True).lower()

        if "in-store pickup" in text:
            bad_phrases = [
                "item will be shipped and should arrive in",
                "not available at this store",
                "online only",
                "not sold in stores",
            ]
            if any(p in text for p in bad_phrases):
                return False

            # No bad phrase in the pickup block -> treat as in-store available
            return True

        current = current.parent  # climb up

    # Fallback if we never find a good container
    return True


# ---------------------- PARSING HELPERS ----------------------


def extract_sku_from_text(text: str) -> Optional[str]:
    """Look for 'SKU: 101363893' style patterns in the raw HTML."""
    m = re.search(r"SKU[:\s]+(\d{6,})", text)
    if m:
        return m.group(1)
    return None


def extract_sku_from_url(url: str) -> Optional[str]:
    """Fallback: get SKU from the trailing '-digits.html' in the URL."""
    m = re.search(r"-(\d{6,})\.html", url)
    if m:
        return m.group(1)
    return None


def parse_basic_info(
    soup: BeautifulSoup, url: str, store_id: Optional[int] = None
) -> Tuple[ProductBasic, str]:
    """
    Pull out core attributes and return:
      - ProductBasic dataclass
      - full flattened page text (for spec parsing)
    """
    full_text = soup.get_text(" ", strip=True)

    # Name: main H1
    h1 = soup.find("h1")
    name = h1.get_text(strip=True) if h1 else None

    if not name:
        meta_title = soup.find("meta", property="og:title")
        if meta_title and meta_title.get("content"):
            name = meta_title["content"].strip()

    if not name:
        # Fallback: use URL slug
        parsed = urlparse(url)
        last = parsed.path.rsplit("/", 1)[-1]
        name = last.replace("-", " ").replace(".html", "").title()

    # SKU: prefer "SKU: 101053254" in text; else from URL
    sku = extract_sku_from_text(full_text)
    if not sku:
        sku = extract_sku_from_url(url)

    # Size / Color / Finish line, if present.
    size_primary = color = finish = None
    m = re.search(
        r"Size:\s*([^C]+?)\s+Color:\s*([^F]+?)\s+Finish:\s*([A-Za-z ]+)",
        full_text,
        flags=re.I,
    )
    if m:
        size_primary = m.group(1).strip()
        color = m.group(2).strip()
        finish = m.group(3).strip()

    # Prices (keep the "/ sqft" or "/ box" suffix for now)
    price_per_sqft = None
    m = re.search(r"\$([0-9\.,]+)\s*/\s*sqft", full_text, flags=re.I)
    if m:
        price_per_sqft = m.group(0).strip()

    price_per_box = None
    m = re.search(r"\$([0-9\.,]+)\s*/\s*box", full_text, flags=re.I)
    if m:
        price_per_box = m.group(0).strip()

    # Category slug from URL path: /porcelain-tile/alto-bianco... => /porcelain-tile
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    category_slug = "/" + parts[0] if parts else None

    basic = ProductBasic(
        sku=sku,
        name=name,
        url=url,
        category_slug=category_slug,
        price_per_sqft=price_per_sqft,
        price_per_box=price_per_box,
        size_primary=size_primary,
        color=color,
        finish=finish,
        store_id=store_id,
    )
    return basic, full_text


def extract_spec_values_from_text(full_text: str) -> Dict[str, str]:
    """
    Generic label -> value extractor.

    For each label in SPEC_LABELS we:
      - find its position in the flattened page text
      - grab everything from that label to the start of the next known label
    This handles the dense spec blocks and gives you things like DCOF, etc.
    """
    specs: Dict[str, str] = {}
    lower = full_text.lower()

    positions: Dict[str, int] = {}
    for label in SPEC_LABELS:
        idx = lower.find(label.lower())
        if idx != -1:
            positions[label] = idx

    if not positions:
        return specs

    ordered_labels = sorted(positions.keys(), key=lambda lbl: positions[lbl])

    for i, label in enumerate(ordered_labels):
        start = positions[label] + len(label)
        if i + 1 < len(ordered_labels):
            next_label = ordered_labels[i + 1]
            end = positions[next_label]
        else:
            end = len(full_text)

        value = full_text[start:end].strip(" :\n\t\r")
        value = re.sub(r"\s{2,}", " ", value)
        if value:
            specs[label] = value

    return specs


def find_section_links(
    soup: BeautifulSoup,
    heading_text_substring: str,
    limit_headings: Tuple[str, ...] = ("h2", "h3", "h4"),
) -> List[Tuple[str, str]]:
    """
    Find (label, href) pairs under a section with a heading containing
    heading_text_substring. Used for:
      - "Install & Product documents"
      - "Materials You Need from Start to Finish"
    """
    heading = soup.find(
        lambda tag: isinstance(tag, Tag)
        and tag.name in limit_headings
        and heading_text_substring.lower()
        in tag.get_text(strip=True).lower()
    )
    if not heading:
        return []

    links: List[Tuple[str, str]] = []
    for sib in heading.next_siblings:
        if isinstance(sib, Tag) and sib.name in limit_headings:
            break
        if isinstance(sib, Tag):
            for a in sib.find_all("a", href=True):
                label = a.get_text(" ", strip=True)
                href = urljoin(BASE_URL, a["href"])
                links.append((label, href))
    return links


# ---------------------- PRODUCT SCRAPING ----------------------


def scrape_product_page_to_sql(
    conn: sqlite3.Connection,
    session: requests.Session,
    product_url: str,
    store_id: int,
    override_sku: Optional[str] = None,
) -> Optional[str]:
    """
    Scrape ONE product page and write:
      - products
      - product_specs
      - product_documents
      - product_recommended_items

    Returns SKU if scraped & stored, or None if skipped (e.g., not in store).
    """
    logging.info("Scraping product: %s", product_url)
    try:
        r = session.get(product_url, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        logging.warning("  !! Failed to fetch %s: %s", product_url, e)
        return None

    if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
        logging.warning(
            "  !! Product %s returned status %s (Content-Type=%s)",
            product_url,
            r.status_code,
            r.headers.get("Content-Type", ""),
        )
        return None

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    # Availability filter (only keep items actually stocked at this store)
    if not is_available_in_store(soup):
        logging.info("  -> Skipping (not in-store stocked for this store)")
        return None

    basic, full_text = parse_basic_info(soup, product_url, store_id=store_id)

    # Respect override SKU from caller (e.g., when we already know from URL)
    if override_sku:
        basic.sku = override_sku

    if not basic.sku:
        logging.warning("  !! Could not determine SKU for %s", product_url)
        return None

    # Filter out obvious non-surface stuff by name/url if it slipped through
    combined_for_filter = " ".join(
        part for part in [basic.name, basic.category_slug, basic.url] if part
    ).lower()
    if any(tok in combined_for_filter for tok in EXCLUDE_PRODUCT_NAME_TOKENS):
        logging.info(
            "  -> Skipping SKU=%s (%s) due to excluded product type",
            basic.sku,
            basic.name,
        )
        return None

    # Upsert core product info
    upsert_product(conn, basic)

    # Specs (DCOF, etc.)
    specs = extract_spec_values_from_text(full_text)
    if specs:
        save_specs(conn, basic.sku, specs)
    else:
        logging.info("  -> No specs parsed for SKU=%s", basic.sku)

    # Install & Product documents (PDFs, care sheets, etc.)
    docs = find_section_links(soup, "Install & Product documents")
    if docs:
        save_docs(conn, basic.sku, docs)
    else:
        logging.info("  -> No install/product docs found for SKU=%s", basic.sku)

    # "Materials You Need from Start to Finish" recommended materials
    recs = find_section_links(soup, "Materials You Need from Start to Finish")
    if recs:
        save_recommended(conn, basic.sku, recs)
    else:
        logging.info(
            "  -> No 'Materials You Need from Start to Finish' section for SKU=%s",
            basic.sku,
        )

    logging.info("  -> Done SKU=%s", basic.sku)
    return basic.sku


def scrape_product_if_stale(
    conn: sqlite3.Connection,
    session: requests.Session,
    product_url: str,
    store_id: int,
    ttl: timedelta,
) -> Optional[str]:
    """
    Check last_scraped_at for this SKU. If it's missing or older than TTL,
    scrape + save. If it's fresh, skip and return None.
    """
    sku_guess = extract_sku_from_url(product_url)
    if sku_guess:
        existing_ts = get_existing_last_scraped(conn, sku_guess)
        if existing_ts is not None:
            age = datetime.utcnow() - existing_ts
            if age <= ttl:
                logging.info(
                    "Skipping SKU=%s (age=%.2f days <= ttl=%.2f days)",
                    sku_guess,
                    age.total_seconds() / 86400,
                    ttl.total_seconds() / 86400,
                )
                return None

    return scrape_product_page_to_sql(
        conn,
        session=session,
        product_url=product_url,
        store_id=store_id,
        override_sku=sku_guess,
    )


# ---------------------- MAIN PIPELINE ----------------------


def scrape_store(
    store_id: int,
    db_path: Path,
    ttl_days: float,
) -> None:
    """
    Entry point to scrape all relevant products for a given store.
    """
    conn = init_db(db_path)
    session = make_session()

    set_store_context(session, store_id)

    # Discover categories (starting from /tile, /stone, /wood, /decoratives...)
    category_slugs = discover_category_slugs(session)
    logging.info("Using %d category slugs", len(category_slugs))

    # Crawl each category for product URLs
    all_product_urls: Set[str] = set()
    for slug in category_slugs:
        urls_for_cat = fetch_product_urls_for_category(session, slug)
        all_product_urls |= urls_for_cat

    logging.info("Total unique product URLs discovered: %d", len(all_product_urls))

    ttl = timedelta(days=ttl_days)
    scraped_count = 0
    processed_count = 0

    for product_url in sorted(all_product_urls):
        processed_count += 1
        try:
            res = scrape_product_if_stale(
                conn,
                session=session,
                product_url=product_url,
                store_id=store_id,
                ttl=ttl,
            )
            if res is not None:
                scraped_count += 1
        except Exception as e:
            logging.exception("Error scraping %s: %s", product_url, e)

    logging.info(
        "Done. Processed=%d URLs, scraped/updated=%d rows into %s",
        processed_count,
        scraped_count,
        db_path,
    )
    conn.close()


# ---------------------- CLI ----------------------


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape Floor & Decor product data for a store into SQLite."
    )
    parser.add_argument(
        "--store-id",
        type=int,
        required=True,
        help="Floor & Decor storeID (e.g., 238 for San Leandro).",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite DB file (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--ttl-days",
        type=float,
        default=1.0,
        help=(
            "Time-to-live in days for existing products. "
            "If last_scraped_at is newer than this, skip re-scrape. "
            "Default: 1.0"
        ),
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> None:
    init_logging()
    args = parse_args(argv)

    store_id = args.store_id
    db_path = Path(args.db)
    ttl_days = args.ttl_days

    logging.info("Starting scrape for store_id=%s -> DB=%s", store_id, db_path)
    scrape_store(store_id=store_id, db_path=db_path, ttl_days=ttl_days)


if __name__ == "__main__":
    main(sys.argv[1:])
