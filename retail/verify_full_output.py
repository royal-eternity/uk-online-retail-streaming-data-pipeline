import duckdb

con = duckdb.connect()
result = con.execute("""
    SELECT COUNT(*)
    FROM read_parquet(
        'retail/output/full_streamed_parquet/**/*.parquet',
        union_by_name=true
    )
""").fetchone()[0]

print("TOTAL SPARK OUTPUT RECORDS:", result)
