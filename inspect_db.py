import sqlite3
from pathlib import Path

# Try common locations
candidates = [
    Path("fnd_products.db"),
    Path("data") / "fnd_products.db",
]

db_path = None
for p in candidates:
    if p.exists():
        db_path = p
        break

print("=== DB PATH CHECK ===")
for p in candidates:
    print("  candidate:", p.resolve(), "exists" if p.exists() else "MISSING")

if db_path is None:
    print("\nNo fnd_products.db found in the usual places.")
    print("Make sure your scraper wrote the DB where you expect.")
    raise SystemExit(1)

print("\nUsing DB:", db_path.resolve())

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# List tables
print("\n=== TABLES ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cur.fetchall()]
if not tables:
    print("No tables found.")
else:
    for t in tables:
        print("  -", t)

# Row counts
print("\n=== ROW COUNTS ===")
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    count = cur.fetchone()[0]
    print(f"  {t}: {count} rows")

# Sample products
if "products" in tables:
    print("\n=== SAMPLE PRODUCTS ===")
    cur.execute(
        "SELECT sku, name, category_slug, store_id, last_scraped_at "
        "FROM products LIMIT 10"
    )
    rows = cur.fetchall()
    if not rows:
        print("  (no rows in products)")
    else:
        for row in rows:
            print("  ", row)

# Sample specs
if "product_specs" in tables:
    print("\n=== SAMPLE SPECS ===")
    cur.execute(
        "SELECT sku, spec_key, spec_value "
        "FROM product_specs LIMIT 10"
    )
    rows = cur.fetchall()
    if not rows:
        print("  (no rows in product_specs)")
    else:
        for row in rows:
            print("  ", row)

conn.close()
print("\nDone.")
