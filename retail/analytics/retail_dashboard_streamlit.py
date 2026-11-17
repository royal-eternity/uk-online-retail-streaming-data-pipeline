from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pyarrow.dataset as ds
import streamlit as st
from plotly.subplots import make_subplots


# =========================================================
# PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Retail Sales Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = (
        Path(__file__).resolve().parents[1]
        / "output"
        / "full_streamed_parquet"
)

COLUMNS = [
    "invoice",
    "stock_code",
    "description",
    "quantity",
    "invoice_date",
    "price",
    "customer_id",
    "country",
    "revenue",
]

# Palette taken from the reference retail dashboard
STEEL = "#4a7f9e"      # header / primary
TEAL = "#6cc5d1"       # KPI 1
GREEN = "#5cb870"      # KPI 2
SLATE = "#5b8aa5"      # KPI 3
YELLOW = "#e9b824"     # KPI 4
ORANGE = "#f28c28"     # line accent
RED = "#e0605e"
NAVY = "#2b4f6b"
INK = "#2e3f4f"

CHART_COLORS = [
    "#4a7f9e", "#6cc5d1", "#e9b824", "#e0605e",
    "#5cb870", "#f28c28", "#8aa4b8", "#2b4f6b",
]


# =========================================================
# THEME
# =========================================================
st.markdown(
    f"""
    <style>
    .stApp {{
        background: #e8eef2;
        color: {INK};
    }}

    header[data-testid="stHeader"] {{
        background: transparent;
    }}

    .block-container {{
        max-width: 1600px;
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }}

    /* ---------- Sidebar ---------- */
    [data-testid="stSidebar"] {{
        background: #ffffff;
        border-right: 1px solid #d5dee6;
    }}
    [data-testid="stSidebar"] * {{
        color: {INK};
    }}
    [data-testid="stSidebar"] h1 {{
        font-size: 1.25rem;
        color: {STEEL};
        font-weight: 800;
    }}
    [data-testid="stSidebar"] h3 {{
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        color: {STEEL};
        font-weight: 800;
        margin-top: 0.6rem;
    }}
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="input"] > div,
    [data-testid="stSidebar"] [data-testid="stDateInput"] > div > div {{
        background: #f4f7fa !important;
        border: 1px solid #cfdae3 !important;
        border-radius: 6px;
    }}
    [data-testid="stSidebar"] input {{
        color: {INK} !important;
    }}
    [data-testid="stSidebar"] [data-baseweb="tag"] {{
        background: {STEEL} !important;
        border-radius: 4px;
    }}
    [data-testid="stSidebar"] [data-baseweb="tag"] span,
    [data-testid="stSidebar"] [data-baseweb="tag"] svg {{
        color: #ffffff !important;
        fill: #ffffff !important;
    }}
    [data-testid="stSidebar"] button {{
        background: {STEEL};
        border: 1px solid {STEEL};
        color: #ffffff !important;
        border-radius: 6px;
        font-weight: 600;
    }}
    [data-testid="stSidebar"] button * {{
        color: #ffffff !important;
    }}
    [data-testid="stSidebar"] button:hover {{
        background: {NAVY};
        border-color: {NAVY};
    }}

    /* ---------- Header banner ---------- */
    .dash-header {{
        background: {STEEL};
        border-radius: 6px;
        padding: 18px 28px;
        margin-bottom: 16px;
        box-shadow: 0 2px 6px #2b4f6b22;
    }}
    .dash-header h1 {{
        color: #ffffff !important;
        font-size: 28px;
        font-weight: 800;
        letter-spacing: 0.01em;
        margin: 0;
        padding: 0;
    }}
    .dash-header p {{
        color: #e3eef5 !important;
        font-size: 13px;
        margin: 4px 0 0 0;
    }}

    /* ---------- Info strip ---------- */
    .info-strip {{
        background: #ffffff;
        border: 1px solid #d5dee6;
        border-radius: 6px;
        padding: 10px 18px;
        font-size: 13px;
        color: #4a5b6a;
        margin-bottom: 16px;
    }}
    .info-strip b {{
        color: {STEEL};
    }}

    /* ---------- Section titles ---------- */
    .section-title {{
        font-size: 15px;
        font-weight: 800;
        color: {NAVY};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 22px 0 10px 0;
        padding-left: 10px;
        border-left: 4px solid {ORANGE};
    }}

    /* ---------- KPI tiles ---------- */
    .kpi {{
        border-radius: 6px;
        padding: 14px 16px 12px 16px;
        color: #ffffff;
        text-align: center;
        box-shadow: 0 2px 5px #2b4f6b26;
        min-height: 92px;
        margin-bottom: 12px;
    }}
    .kpi .kpi-label {{
        font-size: 12.5px;
        font-weight: 600;
        opacity: 0.95;
        margin-bottom: 4px;
    }}
    .kpi .kpi-value {{
        font-size: 28px;
        font-weight: 800;
        line-height: 1.15;
    }}

    /* ---------- Chart / table cards ---------- */
    [data-testid="stPlotlyChart"] {{
        background: #ffffff;
        border: 1px solid #d5dee6;
        border-radius: 8px;
        padding: 6px;
        box-shadow: 0 1px 4px #2b4f6b12;
    }}
    [data-testid="stDataFrame"] {{
        background: #ffffff;
        border: 1px solid #d5dee6;
        border-radius: 8px;
    }}

    div[data-testid="stDownloadButton"] button {{
        background: {STEEL};
        color: #ffffff;
        border: 1px solid {STEEL};
        border-radius: 6px;
        font-weight: 600;
    }}
    div[data-testid="stDownloadButton"] button:hover {{
        background: {NAVY};
        border-color: {NAVY};
        color: #ffffff;
    }}

    hr {{
        border-color: #cfdae3;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def kpi_card(label: str, value: str, color: str) -> str:
    return (
        f'<div class="kpi" style="background:{color};">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f"</div>"
    )


# =========================================================
# LOAD DATA
# =========================================================
@st.cache_data(show_spinner="Loading retail sales data...")
def load_data(folder_path: str) -> pd.DataFrame:
    folder = Path(folder_path)

    if not folder.exists():
        raise FileNotFoundError(f"Sales data folder not found: {folder}")

    dataset = ds.dataset(str(folder), format="parquet")
    available = set(dataset.schema.names)
    missing = set(COLUMNS) - available

    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(sorted(missing))
        )

    data = dataset.to_table(columns=COLUMNS).to_pandas()

    data["invoice_date"] = pd.to_datetime(
        data["invoice_date"], errors="coerce"
    )

    for column in ["quantity", "price", "revenue"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    for column in ["country", "description"]:
        data[column] = (
            data[column]
            .fillna("Unknown")
            .astype(str)
            .str.strip()
            .replace("", "Unknown")
        )

    data["customer_id"] = data["customer_id"].astype("string")
    data["invoice"] = data["invoice"].astype("string")
    data["stock_code"] = data["stock_code"].astype("string")

    return data


try:
    df = load_data(str(DATA_DIR))
except Exception as exc:
    st.error(f"Unable to load retail sales data: {exc}")
    st.stop()

if df.empty:
    st.warning("No sales records were found.")
    st.stop()


# =========================================================
# PREPARE FILTER OPTIONS
# =========================================================
countries = sorted(df["country"].unique().tolist(), key=str.casefold)

products = sorted(
    df.loc[df["description"].notna(), "description"].unique().tolist(),
    key=str.casefold,
)

valid_dates = df["invoice_date"].dropna()

if valid_dates.empty:
    st.error("The dataset has no valid invoice dates.")
    st.stop()

min_date = valid_dates.min().date()
max_date = valid_dates.max().date()


# =========================================================
# INITIALIZE FILTER STATE
# =========================================================
if "country_filter" not in st.session_state:
    st.session_state["country_filter"] = countries.copy()

if "product_filter" not in st.session_state:
    st.session_state["product_filter"] = []

if "date_filter" not in st.session_state:
    st.session_state["date_filter"] = (min_date, max_date)

st.session_state["country_filter"] = [
    v for v in st.session_state["country_filter"] if v in countries
]
st.session_state["product_filter"] = [
    v for v in st.session_state["product_filter"] if v in products
]

saved_dates = st.session_state["date_filter"]

if isinstance(saved_dates, (tuple, list)) and len(saved_dates) == 2:
    saved_start, saved_end = saved_dates
else:
    saved_start, saved_end = min_date, max_date

saved_start = max(min_date, min(max_date, saved_start))
saved_end = max(min_date, min(max_date, saved_end))

if saved_start > saved_end:
    saved_start, saved_end = min_date, max_date

st.session_state["date_filter"] = (saved_start, saved_end)


# =========================================================
# SIDEBAR FILTERS
# =========================================================
st.sidebar.title("Dashboard Filters")
st.sidebar.caption("Choose filters to explore the sales data.")

st.sidebar.markdown("### COUNTRY")
selected_countries = st.sidebar.multiselect(
    "Select one or more countries",
    options=countries,
    key="country_filter",
    placeholder="Search countries...",
    label_visibility="collapsed",
)

st.sidebar.markdown("### INVOICE DATE RANGE")
date_range = st.sidebar.date_input(
    "Choose start and end dates",
    min_value=min_date,
    max_value=max_date,
    key="date_filter",
    format="YYYY-MM-DD",
    label_visibility="collapsed",
)

st.sidebar.markdown("### PRODUCTS")
selected_products = st.sidebar.multiselect(
    "Search and select products",
    options=products,
    key="product_filter",
    placeholder="Type a product name to search...",
    label_visibility="collapsed",
    help=(
        "Type part of a product name, select it, then search "
        "for another product. All selected products remain selected."
    ),
)

st.sidebar.caption(f"{len(products):,} distinct product descriptions available")

if selected_products:
    st.sidebar.caption(f"{len(selected_products):,} product(s) selected")
else:
    st.sidebar.caption("All products included")

st.sidebar.markdown("---")

if st.sidebar.button(
        "Reset all filters",
        use_container_width=True,
        key="reset_filters",
):
    st.session_state["country_filter"] = countries.copy()
    st.session_state["product_filter"] = []
    st.session_state["date_filter"] = (min_date, max_date)
    st.session_state["table_page"] = 1
    st.rerun()


# =========================================================
# FILTER DATA
# =========================================================
filtered = df[df["country"].isin(selected_countries)].copy()

if isinstance(date_range, (tuple, list)):
    if len(date_range) == 2:
        start_date, end_date = date_range
    elif len(date_range) == 1:
        start_date = end_date = date_range[0]
    else:
        start_date, end_date = min_date, max_date
else:
    start_date = end_date = date_range

if start_date > end_date:
    st.sidebar.error("Start date must be before end date.")
    st.stop()

invoice_dates = filtered["invoice_date"].dt.date
filtered = filtered[
    invoice_dates.notna() & invoice_dates.between(start_date, end_date)
    ]

if selected_products:
    filtered = filtered[filtered["description"].isin(selected_products)]

st.sidebar.markdown("---")
st.sidebar.markdown("### CURRENT SELECTION")
st.sidebar.caption(f"Countries selected: {len(selected_countries)}")

if selected_products:
    st.sidebar.caption(f"Products selected: {len(selected_products)}")
else:
    st.sidebar.caption("Products: All products")

st.sidebar.caption(f"Matching rows: {len(filtered):,}")

if filtered.empty:
    st.warning(
        "No transactions match the current filters. "
        "Try another country, date range, or product."
    )
    st.stop()


# =========================================================
# HEADER
# =========================================================
st.markdown(
    """
    <div class="dash-header">
        <h1>Retail Sales Analytics</h1>
        <p>Revenue performance &nbsp;·&nbsp; Product intelligence &nbsp;·&nbsp;
        Customer insights &nbsp;·&nbsp; Market analysis</p>
    </div>
    """,
    unsafe_allow_html=True,
)

product_count = filtered["description"].nunique()

st.markdown(
    f"""
    <div class="info-strip">
        <b>Reporting period:</b> {start_date:%d %b %Y} – {end_date:%d %b %Y}
        &nbsp;|&nbsp; <b>Transactions:</b> {len(filtered):,}
        &nbsp;|&nbsp; <b>Products:</b> {product_count:,}
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# KPIs
# =========================================================
revenue = filtered["revenue"].sum()
orders = filtered["invoice"].nunique()
units = filtered["quantity"].sum()

customer_ids = filtered["customer_id"].dropna().astype(str).str.strip()
customer_ids = customer_ids[customer_ids.ne("") & customer_ids.ne("<NA>")]
customer_count = customer_ids.nunique()

average_order = revenue / orders if orders else 0

st.markdown('<div class="section-title">Sales Overview</div>', unsafe_allow_html=True)

k1, k2, k3 = st.columns(3)
k4, k5, k6 = st.columns(3)

k1.markdown(kpi_card("Total Revenue", f"£{revenue:,.2f}", TEAL), unsafe_allow_html=True)
k2.markdown(kpi_card("Total Orders", f"{orders:,}", GREEN), unsafe_allow_html=True)
k3.markdown(kpi_card("Units Sold", f"{units:,.0f}", SLATE), unsafe_allow_html=True)
k4.markdown(kpi_card("Customers", f"{customer_count:,}", YELLOW), unsafe_allow_html=True)
k5.markdown(kpi_card("Products", f"{product_count:,}", RED), unsafe_allow_html=True)
k6.markdown(kpi_card("Average Revenue per Order", f"£{average_order:,.2f}", NAVY), unsafe_allow_html=True)


# =========================================================
# SHARED CHART STYLE
# =========================================================
chart_layout = {
    "paper_bgcolor": "#ffffff",
    "plot_bgcolor": "#ffffff",
    "font": {"family": "Arial, sans-serif", "size": 12, "color": INK},
    "title": {
        "font": {"size": 15, "color": NAVY},
        "x": 0.03,
        "xanchor": "left",
    },
    "margin": {"l": 25, "r": 20, "t": 60, "b": 35},
    "hoverlabel": {
        "bgcolor": NAVY,
        "font": {"color": "#ffffff", "size": 13},
    },
    "legend": {"font": {"color": INK}},
}

axis_style = dict(
    showgrid=True,
    gridcolor="#edf1f5",
    zeroline=False,
    linecolor="#cfdae3",
    tickfont=dict(color="#5a6b7a", size=11),
    title_font=dict(color=INK, size=12),
)


# =========================================================
# REVENUE PERFORMANCE
# =========================================================
st.markdown('<div class="section-title">Revenue Performance</div>', unsafe_allow_html=True)

chart_data = filtered.dropna(subset=["invoice_date"]).copy()

if not chart_data.empty:
    chart_data["month"] = chart_data["invoice_date"].dt.to_period("M").astype(str)

    monthly = (
        chart_data.groupby("month", as_index=False)
        .agg(revenue=("revenue", "sum"), orders=("invoice", "nunique"))
        .sort_values("month")
    )

    country_sales = (
        filtered.groupby("country", as_index=False)
        .agg(revenue=("revenue", "sum"))
        .nlargest(10, "revenue")
        .sort_values("revenue")
    )

    left, right = st.columns([1.5, 1])

    with left:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=monthly["month"],
                y=monthly["revenue"],
                name="Revenue",
                marker_color=STEEL,
                hovertemplate="Month: %{x}<br>Revenue: £%{y:,.2f}<extra></extra>",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=monthly["month"],
                y=monthly["orders"],
                name="Orders",
                mode="lines+markers",
                line=dict(color=ORANGE, width=3),
                marker=dict(size=7, color="#ffffff", line=dict(color=ORANGE, width=2)),
                hovertemplate="Month: %{x}<br>Orders: %{y:,}<extra></extra>",
            ),
            secondary_y=True,
        )
        combo_layout = {
            **chart_layout,
            "title": {**chart_layout["title"], "text": "Monthly Revenue & Orders"},
            "legend": {
                **chart_layout["legend"],
                "orientation": "h",
                "y": 1.12,
                "x": 0.55,
            },
            "bargap": 0.35,
        }
        fig.update_layout(**combo_layout)
        fig.update_xaxes(**axis_style, tickangle=-30)
        fig.update_yaxes(
            **axis_style, tickprefix="£", tickformat="~s",
            title_text="Revenue (£)", secondary_y=False,
        )
        fig.update_yaxes(
            showgrid=False, tickfont=dict(color="#5a6b7a", size=11),
            title_text="Orders", secondary_y=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        fig = px.bar(
            country_sales,
            x="revenue",
            y="country",
            orientation="h",
            title="Top 10 Countries by Revenue",
            labels={"country": "Country", "revenue": "Revenue (£)"},
            color_discrete_sequence=[TEAL],
        )
        fig.update_traces(
            hovertemplate="%{y}<br>Revenue: £%{x:,.2f}<extra></extra>"
        )
        fig.update_layout(**chart_layout)
        fig.update_xaxes(**axis_style, tickprefix="£", tickformat="~s")
        fig.update_yaxes(**axis_style)
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No valid invoice dates are available for this selection.")


# =========================================================
# PRODUCT AND MARKET ANALYSIS
# =========================================================
st.markdown('<div class="section-title">Product & Market Analysis</div>', unsafe_allow_html=True)

product_sales = (
    filtered.groupby("description", as_index=False)
    .agg(revenue=("revenue", "sum"), units=("quantity", "sum"))
    .nlargest(10, "revenue")
    .sort_values("revenue")
)

country_mix = (
    filtered.groupby("country", as_index=False)
    .agg(revenue=("revenue", "sum"))
    .nlargest(8, "revenue")
)

left, right = st.columns([1.45, 1])

with left:
    fig = px.bar(
        product_sales,
        x="revenue",
        y="description",
        orientation="h",
        title="Top 10 Products by Revenue",
        labels={"description": "Product", "revenue": "Revenue (£)", "units": "Units sold"},
        hover_data=["units"],
        color_discrete_sequence=[STEEL],
    )
    fig.update_traces(
        hovertemplate=(
            "%{y}<br>Revenue: £%{x:,.2f}"
            "<br>Units sold: %{customdata[0]:,.0f}<extra></extra>"
        )
    )
    fig.update_layout(**chart_layout)
    fig.update_xaxes(**axis_style, tickprefix="£", tickformat="~s")
    fig.update_yaxes(**axis_style, automargin=True)
    st.plotly_chart(fig, use_container_width=True)

with right:
    if not country_mix.empty:
        fig = px.pie(
            country_mix,
            names="country",
            values="revenue",
            title="Revenue Share by Country",
            hole=0.58,
            color_discrete_sequence=CHART_COLORS,
        )
        fig.update_traces(
            textposition="inside",
            textinfo="percent",
            insidetextfont=dict(color="white", size=12),
            marker=dict(line=dict(color="#ffffff", width=2)),
            hovertemplate=(
                "%{label}<br>Revenue: £%{value:,.2f}"
                "<br>Share: %{percent}<extra></extra>"
            ),
        )
        fig.update_layout(**chart_layout)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No country revenue data is available.")


# =========================================================
# ORDER AND CUSTOMER INSIGHTS
# =========================================================
st.markdown('<div class="section-title">Orders & Customer Insights</div>', unsafe_allow_html=True)

order_data = filtered.copy()
order_data["order_status"] = (
    order_data["invoice"]
    .astype(str)
    .str.startswith("C")
    .map({True: "Cancellation", False: "Regular invoice"})
)

order_summary = order_data.groupby("order_status", as_index=False).agg(
    transaction_rows=("invoice", "size"),
    invoice_count=("invoice", "nunique"),
    revenue=("revenue", "sum"),
)

customer_data = filtered.copy()
customer_data["customer_id"] = customer_data["customer_id"].astype("string")
customer_data = customer_data[
    customer_data["customer_id"].notna()
    & customer_data["customer_id"].str.strip().ne("")
    ]

top_customers = (
    customer_data.groupby("customer_id", as_index=False)
    .agg(revenue=("revenue", "sum"), orders=("invoice", "nunique"))
    .nlargest(10, "revenue")
    .sort_values("revenue")
)

left, right = st.columns(2)

with left:
    fig = px.bar(
        order_summary,
        x="order_status",
        y="transaction_rows",
        title="Invoice Transaction Breakdown",
        labels={"order_status": "Invoice category", "transaction_rows": "Transaction rows"},
        color="order_status",
        color_discrete_map={"Cancellation": RED, "Regular invoice": STEEL},
    )
    fig.update_traces(hovertemplate="%{x}<br>Rows: %{y:,}<extra></extra>")
    fig.update_layout(**chart_layout, showlegend=False, bargap=0.45)
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style, tickformat="~s")
    st.plotly_chart(fig, use_container_width=True)

with right:
    if not top_customers.empty:
        top_customers["customer_id"] = top_customers["customer_id"].astype(str)
        fig = px.bar(
            top_customers,
            x="revenue",
            y="customer_id",
            orientation="h",
            title="Top 10 Customers by Revenue",
            labels={"customer_id": "Customer ID", "revenue": "Revenue (£)", "orders": "Orders"},
            hover_data=["orders"],
            color_discrete_sequence=[YELLOW],
        )
        fig.update_traces(
            hovertemplate=(
                "Customer: %{y}<br>"
                "Revenue: £%{x:,.2f}<br>"
                "Orders: %{customdata[0]}<extra></extra>"
            )
        )
        fig.update_layout(**chart_layout)
        fig.update_xaxes(**axis_style, tickprefix="£", tickformat="~s")
        fig.update_yaxes(**axis_style, automargin=True, type="category")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No customer IDs are available for this selection.")


# =========================================================
# TRANSACTION DETAILS
# =========================================================
st.markdown('<div class="section-title">Transaction Details</div>', unsafe_allow_html=True)

st.caption(
    "Review the transactions matching the filters. "
    "Use the CSV export to analyze the complete filtered result."
)

page_size = st.selectbox(
    "Rows per page",
    [25, 50, 100, 250, 500],
    index=1,
    key="table_page_size",
)

total_pages = max(1, (len(filtered) + page_size - 1) // page_size)

current_page = int(st.session_state.get("table_page", 1))
current_page = min(max(current_page, 1), total_pages)
st.session_state["table_page"] = current_page

page = st.number_input(
    "Page",
    min_value=1,
    max_value=total_pages,
    step=1,
    key="table_page",
)

start = (int(page) - 1) * page_size
end = min(start + page_size, len(filtered))

display_columns = [
    "invoice",
    "invoice_date",
    "stock_code",
    "description",
    "quantity",
    "price",
    "revenue",
    "customer_id",
    "country",
]

st.dataframe(
    filtered.iloc[start:end][display_columns],
    use_container_width=True,
    hide_index=True,
)

st.caption(
    f"Page {int(page):,} of {total_pages:,} · "
    f"Showing {start + 1:,}–{end:,} of {len(filtered):,} records"
)

st.download_button(
    "Download filtered sales (CSV)",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="retail_sales_filtered.csv",
    mime="text/csv",
)

st.markdown("---")
st.caption("Retail Sales Analytics | Built with Python, Pandas, PyArrow, Plotly and Streamlit")