from pathlib import Path
import pandas as pd

SOURCE = Path("retail_data/extracted/online_retail_II.xlsx")
OUTPUT = Path("retail/output/parquet")
OUTPUT.mkdir(parents=True, exist_ok=True)

SHEETS = ["Year 2009-2010", "Year 2010-2011"]
TOTAL_ROWS = 0

for sheet_index, sheet in enumerate(SHEETS, start=1):
    print(f"\nProcessing: {sheet}", flush=True)

    df = pd.read_excel(SOURCE, sheet_name=sheet)

    df.columns = [
        "invoice", "stock_code", "description", "quantity",
        "invoice_date", "price", "customer_id", "country"
    ]

    # Identifiers must be strings, not numeric columns
    df["invoice"] = df["invoice"].astype("string")
    df["stock_code"] = df["stock_code"].astype("string")
    df["description"] = df["description"].astype("string")
    df["country"] = df["country"].astype("string")

    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["customer_id"] = pd.to_numeric(df["customer_id"], errors="coerce")

    output_file = OUTPUT / f"retail_{sheet_index}.parquet"
    df.to_parquet(output_file, index=False, compression="snappy")

    rows = len(df)
    TOTAL_ROWS += rows
    print(f"Rows written: {rows:,}")
    print(f"File: {output_file}")
    print(f"File size: {output_file.stat().st_size / (1024 * 1024):.2f} MiB")

    del df

print(f"\nTotal rows converted: {TOTAL_ROWS:,}")
print("Conversion complete.")
