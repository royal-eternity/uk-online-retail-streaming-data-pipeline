from pathlib import Path
import duckdb

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "output" / "streamed_parquet" / "retail_stream.parquet"
OUTPUT_DIR = BASE_DIR / "output" / "analytics"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

con = duckdb.connect(str(OUTPUT_DIR / "retail_analytics.duckdb"))

parquet_path = INPUT_FILE.as_posix().replace("'", "''")

con.execute(f"""
    CREATE OR REPLACE VIEW retail_transactions AS
    SELECT *,
           ROUND(quantity * price, 2) AS calculated_revenue
    FROM read_parquet('{parquet_path}')
""")

print("\n=== PIPELINE SUMMARY ===")
print("Total records:", con.execute(
    "SELECT COUNT(*) FROM retail_transactions"
).fetchone()[0])

print("\n=== TOP 10 COUNTRIES BY REVENUE ===")
print(con.execute("""
    SELECT country,
           ROUND(SUM(calculated_revenue), 2) AS revenue
    FROM retail_transactions
    GROUP BY country
    ORDER BY revenue DESC
    LIMIT 10
""").df().to_string(index=False))

print("\n=== TOP 10 PRODUCTS BY QUANTITY ===")
print(con.execute("""
    SELECT stock_code,
           MAX(description) AS description,
           SUM(quantity) AS total_quantity
    FROM retail_transactions
    GROUP BY stock_code
    ORDER BY total_quantity DESC
    LIMIT 10
""").df().to_string(index=False))

con.close()
print("\nANALYTICS_COMPLETE")