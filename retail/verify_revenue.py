from pathlib import Path
import duckdb

root = Path(__file__).resolve().parent
parquet_dir = root / "output" / "full_streamed_parquet"
pattern = (parquet_dir / "**" / "*.parquet").as_posix()

con = duckdb.connect()
con.execute(
    f"CREATE VIEW retail AS SELECT * FROM read_parquet('{pattern}', union_by_name=true)"
)

print("REVENUE VALIDATION")
print("------------------")

results = con.execute("""
    SELECT
        COUNT(*) AS records,
        ROUND(SUM(revenue), 2) AS spark_saved_revenue,
        ROUND(SUM(ROUND(quantity * price, 2)), 2) AS row_rounded_revenue,
        ROUND(SUM(quantity * price), 2) AS unrounded_sum_revenue,
        COUNT(*) FILTER (WHERE revenue IS NULL) AS null_saved_revenue
    FROM retail
""").fetchone()

labels = [
    "Total records",
    "Sum of Spark-saved revenue",
    "Sum of row-rounded quantity * price",
    "Rounded sum of quantity * price",
    "Rows with NULL saved revenue",
]

for label, value in zip(labels, results):
    print(f"{label}: {value}")

con.close()

