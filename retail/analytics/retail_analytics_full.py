from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[2]
PARQUET_DIR = ROOT / "retail" / "output" / "full_streamed_parquet"
DB_DIR = ROOT / "retail" / "output" / "analytics"
DB_PATH = DB_DIR / "retail_analytics_full.duckdb"

files = list(PARQUET_DIR.rglob("*.parquet"))
if not files:
    raise FileNotFoundError(f"No Parquet files found in {PARQUET_DIR}")

DB_DIR.mkdir(parents=True, exist_ok=True)
parquet_pattern = str(PARQUET_DIR / "**" / "*.parquet").replace("\\", "/")
con = duckdb.connect(str(DB_PATH))

con.execute(f"""
    CREATE OR REPLACE VIEW retail_transactions AS
    SELECT * FROM read_parquet('{parquet_pattern}', union_by_name=true)
""")

print("FULL DATASET ANALYTICS")
print("----------------------")
print("Total records:", con.execute(
    "SELECT COUNT(*) FROM retail_transactions"
).fetchone()[0])

print("Total revenue:", round(con.execute(
    "SELECT COALESCE(SUM(revenue), 0) FROM retail_transactions"
).fetchone()[0], 2))

print("Distinct countries:", con.execute(
    "SELECT COUNT(DISTINCT country) FROM retail_transactions"
).fetchone()[0])

print("\nTOP 10 COUNTRIES BY REVENUE")
for row in con.execute("""
    SELECT country, ROUND(SUM(revenue), 2) AS revenue
    FROM retail_transactions
    WHERE country IS NOT NULL
    GROUP BY country
    ORDER BY revenue DESC
    LIMIT 10
""").fetchall():
    print(row)

print("\nTOP 10 PRODUCTS BY QUANTITY")
for row in con.execute("""
    SELECT description, SUM(quantity) AS total_quantity
    FROM retail_transactions
    WHERE description IS NOT NULL
    GROUP BY description
    ORDER BY total_quantity DESC
    LIMIT 10
""").fetchall():
    print(row)

con.close()
print("\nANALYTICS_COMPLETE")
print("Database:", DB_PATH)
