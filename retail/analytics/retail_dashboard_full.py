from pathlib import Path
from datetime import timedelta

import duckdb
import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parents[1]
DB_FILE = BASE_DIR / "output" / "analytics" / "retail_analytics_full.duckdb"

st.set_page_config(
    page_title="Retail Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("Retail Analytics Dashboard")
st.caption("UCI Online Retail II | Kafka → Spark → Parquet → DuckDB")

if not DB_FILE.exists():
    st.error("Full analytics database not found.")
    st.stop()


@st.cache_data
def get_filter_options(db_path):
    con = duckdb.connect(db_path, read_only=True)
    try:
        countries = con.execute("""
            SELECT DISTINCT country
            FROM retail_transactions
            WHERE country IS NOT NULL
            ORDER BY country
        """).fetchdf()["country"].tolist()

        bounds = con.execute("""
            SELECT
                MIN(TRY_CAST(invoice_date AS TIMESTAMP)),
                MAX(TRY_CAST(invoice_date AS TIMESTAMP))
            FROM retail_transactions
        """).fetchone()

        return countries, bounds
    finally:
        con.close()


countries, bounds = get_filter_options(str(DB_FILE))

if bounds[0] is None or bounds[1] is None:
    st.error("Invoice dates could not be read.")
    st.stop()

min_date = bounds[0].date()
max_date = bounds[1].date()

st.sidebar.header("Dashboard Filters")

selected_countries = st.sidebar.multiselect(
    "Select countries",
    options=countries,
    default=[],
    help="Leave empty to include all countries.",
)

selected_dates = st.sidebar.date_input(
    "Invoice date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

if not isinstance(selected_dates, (tuple, list)) or len(selected_dates) != 2:
    st.info("Please select both a start date and an end date.")
    st.stop()

start_date, end_date = selected_dates

if start_date > end_date:
    st.error("Start date must be before or equal to end date.")
    st.stop()

conditions = [
    "TRY_CAST(invoice_date AS TIMESTAMP) >= ?",
    "TRY_CAST(invoice_date AS TIMESTAMP) < ?",
]
params = [start_date, end_date + timedelta(days=1)]

if selected_countries:
    placeholders = ", ".join(["?"] * len(selected_countries))
    conditions.append(f"country IN ({placeholders})")
    params.extend(selected_countries)

where_sql = " AND ".join(conditions)
revenue_sql = "ROUND(COALESCE(quantity, 0) * COALESCE(price, 0), 2)"

con = duckdb.connect(str(DB_FILE), read_only=True)

try:
    records, revenue, product_count, country_count = con.execute(
        f"""
        SELECT
            COUNT(*),
            ROUND(SUM({revenue_sql}), 2),
            COUNT(DISTINCT stock_code),
            COUNT(DISTINCT country)
        FROM retail_transactions
        WHERE {where_sql}
        """,
        params,
    ).fetchone()

    country_sales = con.execute(
        f"""
        SELECT country, ROUND(SUM({revenue_sql}), 2) AS revenue
        FROM retail_transactions
        WHERE {where_sql} AND country IS NOT NULL
        GROUP BY country
        ORDER BY revenue DESC
        LIMIT 10
        """,
        params,
    ).df()

    top_products = con.execute(
        f"""
        SELECT
            COALESCE(description, stock_code) AS product,
            SUM(quantity) AS quantity
        FROM retail_transactions
        WHERE {where_sql}
        GROUP BY product
        ORDER BY quantity DESC
        LIMIT 10
        """,
        params,
    ).df()

    monthly = con.execute(
        f"""
        SELECT
            DATE_TRUNC(
                'month', TRY_CAST(invoice_date AS TIMESTAMP)
            ) AS month,
            ROUND(SUM({revenue_sql}), 2) AS revenue
        FROM retail_transactions
        WHERE {where_sql}
        GROUP BY month
        ORDER BY month
        """,
        params,
    ).df()

    preview = con.execute(
        f"""
        SELECT *,
            ROUND({revenue_sql}, 2) AS calculated_revenue
        FROM retail_transactions
        WHERE {where_sql}
        ORDER BY TRY_CAST(invoice_date AS TIMESTAMP) DESC
        LIMIT 1000
        """,
        params,
    ).df()
finally:
    con.close()

st.caption(
    f"Period: {start_date:%d %b %Y} – {end_date:%d %b %Y}"
    + (" | All countries" if not selected_countries
       else f" | {len(selected_countries)} countries selected")
)

a, b, c, d = st.columns(4)
a.metric("Transactions", f"{records:,}")
b.metric("Total Revenue", f"{(revenue or 0):,.2f}")
c.metric("Unique Products", f"{product_count:,}")
d.metric("Countries", f"{country_count:,}")

st.divider()

st.subheader("Monthly Revenue Trend")
if not monthly.empty:
    monthly["month"] = pd.to_datetime(monthly["month"])
    st.line_chart(monthly.set_index("month")["revenue"])
else:
    st.info("No monthly revenue found for these filters.")

left, right = st.columns(2)

with left:
    st.subheader("Top Countries by Revenue")
    if not country_sales.empty:
        st.bar_chart(country_sales.set_index("country")["revenue"])
    else:
        st.info("No country data found.")

with right:
    st.subheader("Top Products by Quantity")
    if not top_products.empty:
        st.bar_chart(top_products.set_index("product")["quantity"])
    else:
        st.info("No product data found.")

st.subheader("Transaction Preview")
st.caption("Showing up to 1,000 matching rows. The full dataset remains in DuckDB.")

st.dataframe(
    preview,
    use_container_width=True,
    hide_index=True,
)

if st.button("Prepare filtered CSV"):
    con = duckdb.connect(str(DB_FILE), read_only=True)
    try:
        export_df = con.execute(
            f"""
            SELECT *,
                ROUND({revenue_sql}, 2) AS calculated_revenue
            FROM retail_transactions
            WHERE {where_sql}
            """,
            params,
        ).df()
    finally:
        con.close()

    st.download_button(
        "Download filtered transactions",
        data=export_df.to_csv(index=False).encode("utf-8"),
        file_name="filtered_retail_transactions.csv",
        mime="text/csv",
    )

    st.success(f"Prepared {len(export_df):,} filtered rows.")

st.caption(
    "Full dataset | Kafka → Spark → Parquet → DuckDB → Streamlit"
)