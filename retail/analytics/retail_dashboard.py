
from pathlib import Path

import duckdb
import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[1]
DB_FILE = BASE_DIR / "output" / "analytics" / "retail_analytics.duckdb"

st.set_page_config(
    page_title="Retail Analytics Dashboard",
    page_icon="🛍️",
    layout="wide",
)

st.title("🛍️ Retail Analytics Dashboard")
st.caption("UCI Online Retail II | Kafka → Spark → Parquet → DuckDB")

if not DB_FILE.exists():
    st.error("Analytics database not found. Run retail_analytics.py first.")
    st.stop()

con = duckdb.connect(str(DB_FILE), read_only=True)

try:
    df = con.execute("SELECT * FROM retail_transactions").df()
finally:
    con.close()

if df.empty:
    st.warning("No records found in the analytics database.")
    st.stop()

df["calculated_revenue"] = df["quantity"] * df["price"]
df["calculated_revenue"] = df["calculated_revenue"].round(2)

total_records = len(df)
total_revenue = df["calculated_revenue"].sum()
unique_products = df["stock_code"].nunique()
unique_countries = df["country"].nunique()

a, b, c, d = st.columns(4)
a.metric("Records", f"{total_records:,}")
b.metric("Total Revenue", f"{total_revenue:,.2f}")
c.metric("Unique Products", f"{unique_products:,}")
d.metric("Countries", f"{unique_countries:,}")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Revenue by Country")
    country_sales = (
        df.groupby("country", dropna=False)["calculated_revenue"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .sort_values()
    )
    st.bar_chart(country_sales)

with right:
    st.subheader("Top Products by Quantity")
    products = (
        df.groupby("stock_code", dropna=False)["quantity"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .sort_values()
    )
    st.bar_chart(products)

st.subheader("Retail Transaction Data")
st.dataframe(df, use_container_width=True)

st.download_button(
    "Download displayed data as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="retail_transactions.csv",
    mime="text/csv",
)

st.caption(
    "Current dashboard reflects the streamed test batch. "
    "Full-dataset analytics will be added after the pipeline is scaled up."
)
