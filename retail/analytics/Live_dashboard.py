"""Real-time retail sales analytics dashboard (reference-template style)."""

import html
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from Live_engine import LiveEngine
from Theme import (
    GREEN,
    INK,
    NAVY,
    NEUTRAL,
    ORANGE,
    RED,
    SERIES,
    SLATE,
    STEEL,
    TEAL,
    YELLOW,
    apply_theme,
    card_title,
    kpi_card,
    style_figure,
)


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="Retail Sales Analytics | Live",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

HOME_MARKET = "United Kingdom"

REQUIRED_COLUMNS = [
    "event_time",
    "invoice",
    "stock_code",
    "description",
    "quantity",
    "price",
    "revenue",
    "customer_id",
    "country",
]

WINDOWS = {
    "Last 1 minute": 60,
    "Last 5 minutes": 300,
    "Last 15 minutes": 900,
    "Last 30 minutes": 1800,
}

# Bucket size (seconds) per window for the two time-series charts.
TREND_BUCKET_S = {60: 2, 300: 10, 900: 30, 1800: 60}
BASKET_BUCKET_S = {60: 10, 300: 30, 900: 90, 1800: 180}

# Values that mean "no real customer".
NO_CUSTOMER = {"", "Unknown", "nan", "None", "<NA>"}

# Country name -> ISO-3 (for the map). None = not a real country.
ISO3 = {
    "United Kingdom": "GBR", "Germany": "DEU", "France": "FRA",
    "EIRE": "IRL", "Ireland": "IRL", "Spain": "ESP",
    "Netherlands": "NLD", "Belgium": "BEL", "Switzerland": "CHE",
    "Portugal": "PRT", "Australia": "AUS", "Norway": "NOR",
    "Italy": "ITA", "Channel Islands": "JEY", "Finland": "FIN",
    "Cyprus": "CYP", "Sweden": "SWE", "Austria": "AUT",
    "Denmark": "DNK", "Japan": "JPN", "Poland": "POL",
    "Israel": "ISR", "USA": "USA", "United States": "USA",
    "Hong Kong": "HKG", "Singapore": "SGP", "Iceland": "ISL",
    "Canada": "CAN", "Greece": "GRC", "Malta": "MLT",
    "United Arab Emirates": "ARE", "RSA": "ZAF", "Lebanon": "LBN",
    "Lithuania": "LTU", "Brazil": "BRA", "Czech Republic": "CZE",
    "Bahrain": "BHR", "Saudi Arabia": "SAU", "Unspecified": None,
    "European Community": None, "Unknown": None,
}


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def money(value, decimals=2):
    """Format a numeric value as GBP (negatives as -£1,234)."""
    sign = "-" if value < 0 else ""
    return f"{sign}£{abs(value):,.{decimals}f}"


def short_label(text, limit=18):
    """Title-case and truncate long product names for chart axes."""
    text = str(text).title()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def make_product_label(description, stock_code):
    """'DESCRIPTION | CODE' when a code exists, else description."""
    code = stock_code.str.strip()
    return description.where(code.eq(""), description + " | " + code)


def pct_change(current, previous):
    """Percent change, or None when it cannot be computed."""
    if previous is None or previous == 0 or pd.isna(previous):
        return None
    return (current - previous) / abs(previous) * 100


def card(key, icon, title, color=STEEL):
    """White card with an icon + title (styled via Theme CSS)."""
    box = st.container(key=f"card-{key}")
    with box:
        st.markdown(card_title(icon, title, color), unsafe_allow_html=True)
    return box


def empty_state(message):
    """Message shown when a chart has no data."""
    st.info(message)


def show(fig, key):
    """Render a Plotly figure.

    On an older Streamlit that rejects `width="stretch"`, use
    `use_container_width=True` here and in the st.dataframe call.
    """
    st.plotly_chart(
        fig,
        width="stretch",
        key=key,
        config={"displayModeBar": False},
    )


# ---------------------------------------------------------
# DATA PREPARATION
# ---------------------------------------------------------

def prepare_snapshot(raw):
    """Return a normalized snapshot with consistent columns."""

    df = (
        pd.DataFrame(columns=REQUIRED_COLUMNS)
        if raw is None
        else raw.copy()
    )

    defaults = {
        "event_time": pd.NaT,
        "invoice": "",
        "stock_code": "",
        "description": "Unknown product",
        "quantity": 0,
        "price": 0,
        "revenue": 0,
        "customer_id": "Unknown",
        "country": "Unknown",
    }

    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # The engine emits timezone-naive LOCAL timestamps
    # (datetime.now()), so the dashboard compares against
    # pd.Timestamp.now() (also naive local).
    df["event_time"] = pd.to_datetime(df["event_time"], errors="coerce")
    if df["event_time"].dt.tz is not None:
        df["event_time"] = df["event_time"].dt.tz_convert(None)

    for col in ["quantity", "price", "revenue"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in ["invoice", "stock_code", "description",
                "customer_id", "country"]:
        df[col] = df[col].fillna(defaults[col]).astype(str).str.strip()

    df = df.dropna(subset=["event_time"]).copy()

    df["is_cancelled"] = df["invoice"].str.startswith("C").astype(bool)
    df["product_label"] = make_product_label(
        df["description"], df["stock_code"]
    )

    return df[REQUIRED_COLUMNS + ["is_cancelled", "product_label"]]


def summarize(frame):
    """Compute the headline metrics for a block of transactions."""

    if frame is None or frame.empty:
        return {
            "net": 0.0, "gross": 0.0, "cancel_value": 0.0,
            "orders": 0, "cancelled_orders": 0, "units": 0.0,
            "customers": 0, "aov": 0.0, "units_per_order": 0.0,
            "cancel_rate": 0.0,
        }

    regular = frame[~frame["is_cancelled"]]
    cancelled = frame[frame["is_cancelled"]]

    orders = int(regular["invoice"].nunique())
    cancelled_orders = int(cancelled["invoice"].nunique())
    total_invoices = orders + cancelled_orders

    gross = float(regular["revenue"].sum())
    cancel_value = float(cancelled["revenue"].sum())
    regular_units = float(regular["quantity"].sum())

    ids = frame["customer_id"]
    customers = int(ids[~ids.isin(NO_CUSTOMER)].nunique())

    return {
        "net": gross + cancel_value,
        "gross": gross,
        "cancel_value": cancel_value,
        "orders": orders,
        "cancelled_orders": cancelled_orders,
        "units": float(frame["quantity"].sum()),
        "customers": customers,
        "aov": gross / orders if orders else 0.0,
        "units_per_order": regular_units / orders if orders else 0.0,
        "cancel_rate": (
            cancelled_orders / total_invoices * 100
            if total_invoices else 0.0
        ),
    }


def bucketed(frame, now, window_s, bucket_s, data_start=None):
    """Aggregate revenue / orders / units into fixed time buckets.

    - Only COMPLETE buckets are returned (the bucket that is still
      filling would otherwise show as a false dip at the right edge).
    - Empty buckets are zero-filled so gaps are visible.
    - Buckets before the first event ever received are dropped.
    """
    freq = f"{bucket_s}s"
    step = pd.Timedelta(seconds=bucket_s)

    start = (now - pd.Timedelta(seconds=window_s)).ceil(freq)
    if data_start is not None and pd.notna(data_start):
        start = max(start, data_start.ceil(freq))
    end = now.floor(freq)

    empty = pd.DataFrame(
        columns=["bucket", "revenue", "orders", "units"]
    )

    index = pd.date_range(start, end - step, freq=freq)
    if len(index) == 0:
        return empty

    data = frame[
        (frame["event_time"] >= start) & (frame["event_time"] < end)
        ]

    floor = data["event_time"].dt.floor(freq)
    revenue = data.groupby(floor)["revenue"].sum()
    units = data.groupby(floor)["quantity"].sum()

    regular = data[~data["is_cancelled"]]
    orders = regular.groupby(
        regular["event_time"].dt.floor(freq)
    )["invoice"].nunique()

    return pd.DataFrame({
        "bucket": index,
        "revenue": revenue.reindex(index, fill_value=0.0).to_numpy(),
        "orders": orders.reindex(index, fill_value=0).to_numpy(),
        "units": units.reindex(index, fill_value=0.0).to_numpy(),
    })


# ---------------------------------------------------------
# STREAM ENGINE
# ---------------------------------------------------------

@st.cache_resource
def get_engine():
    """Create one shared stream engine."""
    return LiveEngine()


engine = get_engine()


# ---------------------------------------------------------
# SIDEBAR CONTROLS
# ---------------------------------------------------------

st.sidebar.title("Live Controls")
st.sidebar.caption(
    "Monitor sales and filter the dashboard in real time."
)

window_label = st.sidebar.selectbox(
    "Time window",
    options=list(WINDOWS.keys()),
    index=1,
)

window_s = WINDOWS[window_label]

refresh = st.sidebar.select_slider(
    "Refresh every (seconds)",
    options=[1, 2, 3, 5, 10],
    value=2,
)


# ---------------------------------------------------------
# FILTER OPTIONS (built from everything currently buffered)
# ---------------------------------------------------------

catalogue_df = prepare_snapshot(engine.snapshot())

country_options = sorted(
    catalogue_df["country"].unique().tolist(), key=str.casefold
)
product_options = sorted(
    catalogue_df["product_label"].unique().tolist(), key=str.casefold
)

# Drop stale selections (e.g. a product that rolled out of the buffer).
for state_key, valid in (
        ("selected_countries", country_options),
        ("selected_products", product_options),
):
    if state_key in st.session_state and valid:
        st.session_state[state_key] = [
            value for value in st.session_state[state_key]
            if value in valid
        ]


# ---------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------

st.sidebar.markdown("### COUNTRY")

selected_countries = st.sidebar.multiselect(
    "Countries (empty = all)",
    options=country_options,
    placeholder="All countries",
    key="selected_countries",
)

st.sidebar.markdown("### SELECT PRODUCTS")

selected_products = st.sidebar.multiselect(
    "Choose products",
    options=product_options,
    placeholder="All products",
    help="Leave empty to include all products.",
    key="selected_products",
)

st.sidebar.markdown("### SEARCH PRODUCTS")

product_search = st.sidebar.text_input(
    "Search by name or stock code",
    placeholder="Type a product name or code...",
    key="product_search",
)

st.sidebar.markdown("### MARKET VIEW")

exclude_home = st.sidebar.toggle(
    f"Exclude {HOME_MARKET} from market charts",
    value=False,
    help=(
        f"{HOME_MARKET} dominates revenue, which squashes every other "
        "country into slivers. Switch this on to compare the "
        "international markets against each other. KPIs are not affected."
    ),
    key="exclude_home",
)

st.sidebar.caption(
    "Filters apply to KPIs, charts and the transaction feed."
)

if not product_options:
    st.sidebar.info(
        "No products received yet. Product options will "
        "populate when transaction data arrives."
    )

st.sidebar.markdown("---")
st.sidebar.markdown("### STREAM STATUS")
st.sidebar.caption(f"Source: {engine.source}")
st.sidebar.caption(f"Status: {engine.status}")
st.sidebar.caption(f"Events received: {engine.total:,}")


def apply_filters(frame):
    """Apply country, product and search filters."""

    if frame.empty:
        return frame

    if selected_countries:
        frame = frame[frame["country"].isin(selected_countries)]

    if selected_products:
        frame = frame[frame["product_label"].isin(selected_products)]

    term = product_search.strip()
    if term:
        matches = (
                frame["description"].str.contains(
                    term, case=False, na=False, regex=False
                )
                | frame["stock_code"].str.contains(
            term, case=False, na=False, regex=False
        )
        )
        frame = frame[matches]

    return frame


# ---------------------------------------------------------
# BANNER
# ---------------------------------------------------------

st.markdown(
    """
    <div class="dash-banner">
        <h1>Retail Dashboard – Live Sales by Geo, Product &amp; Customer</h1>
        <p>Real-time revenue · Product intelligence · Market analysis</p>
        <div class="live-pill"><span class="live-dot"></span>LIVE</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# CHART BUILDERS
# ---------------------------------------------------------

def product_table(products):
    """Reference-style 'Key Product Revenues' table (HTML)."""

    header = (
        '<tr><th class="l">Product</th><th>Revenue</th><th>Units</th>'
        "<th>Orders</th><th>Avg price</th><th>Share</th></tr>"
    )

    rows = []
    for item in products.itertuples():
        rows.append(
            '<tr><td class="l">'
            f"{html.escape(short_label(item.description, 30))}"
            f"</td><td>{money(item.revenue, 0)}</td>"
            f"<td>{item.units:,.0f}</td>"
            f"<td>{item.orders:,}</td>"
            f"<td>{money(item.avg_price)}</td>"
            f"<td>{item.share:.1f}%</td></tr>"
        )

    st.markdown(
        f'<table class="ref-table">{header}{"".join(rows)}</table>',
        unsafe_allow_html=True,
    )


def ring_gauge(name, pct, color, key):
    """Small ring gauge (reference 'Sales by Geography' side dials)."""

    label = f"{pct:.0f}%" if pct >= 1 else "<1%"

    fig = go.Figure(
        go.Pie(
            values=[pct, max(100 - pct, 0)],
            hole=0.74,
            sort=False,
            direction="clockwise",
            marker={"colors": [color, "#E3E8EE"]},
            textinfo="none",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=140,
        margin={"l": 4, "r": 4, "t": 4, "b": 4},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[{
            "text": f"<b>{label}</b>",
            "x": 0.5, "y": 0.5,
            "showarrow": False,
            "font": {"size": 15, "color": INK},
        }],
    )
    show(fig, key)
    st.markdown(
        f'<div class="ring-label">{html.escape(name)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# LIVE DASHBOARD
# ---------------------------------------------------------

def live_view():
    """Render one dashboard refresh."""

    df = prepare_snapshot(engine.snapshot())
    now = pd.Timestamp.now()

    data_start = df["event_time"].min() if not df.empty else None

    # -----------------------------------------------------
    # WINDOWS: current and previous (for % change)
    # -----------------------------------------------------

    filtered = apply_filters(df)

    cutoff = now - pd.Timedelta(seconds=window_s)
    prev_cutoff = cutoff - pd.Timedelta(seconds=window_s)

    win = filtered[filtered["event_time"] >= cutoff].sort_values(
        "event_time"
    )

    # Only compare with the previous window once the buffer
    # actually covers it; otherwise the % change is meaningless.
    has_prev = data_start is not None and data_start <= prev_cutoff

    prev = (
        filtered[
            (filtered["event_time"] >= prev_cutoff)
            & (filtered["event_time"] < cutoff)
            ]
        if has_prev else None
    )

    cur = summarize(win)
    old = summarize(prev) if has_prev else None

    def change(key):
        return pct_change(cur[key], old[key]) if old else None

    if win.empty:
        st.warning(
            "No transactions match the current filters. "
            "Try a longer time window or clear your "
            "country/product filters."
        )

    # Event rate from the UNFILTERED stream (pipeline health).
    recent = (
        df[df["event_time"] >= now - pd.Timedelta(seconds=10)]
        if not df.empty else df
    )
    events_per_second = len(recent) / 10.0

    # Market view: optionally hide the home market.
    market = win[win["country"].ne(HOME_MARKET)] if exclude_home else win
    market_tag = " (International)" if exclude_home else ""

    # -----------------------------------------------------
    # KPI TILES
    # -----------------------------------------------------

    brand_col, *kpi_cols = st.columns([1.15, 1, 1, 1, 1])

    brand_col.markdown(
        '<div class="brand-box">'
        '<div class="brand-name">Retail Analytics</div>'
        f'<div class="brand-sub">{window_label} · {engine.source}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    tiles = [
        ("Net Revenue", money(cur["net"], 0), TEAL, change("net")),
        ("Orders", f"{cur['orders']:,}", GREEN, change("orders")),
        ("Avg Order Value", money(cur["aov"]), SLATE, change("aov")),
        ("Avg Units / Order", f"{cur['units_per_order']:.1f}", YELLOW,
         change("units_per_order")),
    ]

    for col, (label, value, color, delta) in zip(kpi_cols, tiles):
        col.markdown(
            kpi_card(label, value, color, delta=delta),
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="info-strip">
            <b>Last updated:</b> {datetime.now():%H:%M:%S}
            &nbsp; | &nbsp;
            <b>Transactions:</b> {len(win):,}
            &nbsp; | &nbsp;
            <b>Active customers:</b> {cur["customers"]:,}
            &nbsp; | &nbsp;
            <b>Units sold:</b> {cur["units"]:,.0f}
            &nbsp; | &nbsp;
            <b>Cancellation rate:</b> {cur["cancel_rate"]:.1f}%
            &nbsp; | &nbsp;
            <b>Events / sec:</b> {events_per_second:.1f}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------
    # ROW 1: KEY PRODUCTS TABLE + SALES BY PRODUCT
    # -----------------------------------------------------

    if win.empty:
        products = pd.DataFrame()
    else:
        products = (
            win.groupby(["stock_code", "description"], as_index=False)
            .agg(
                revenue=("revenue", "sum"),
                units=("quantity", "sum"),
                orders=("invoice", "nunique"),
            )
            .nlargest(6, "revenue")
            .reset_index(drop=True)
        )
        total_rev = float(win["revenue"].sum())
        products["avg_price"] = np.where(
            products["units"] > 0,
            products["revenue"] / products["units"].replace(0, np.nan),
            0.0,
            )
        products["share"] = (
            products["revenue"] / total_rev * 100 if total_rev else 0.0
        )

    left, right = st.columns([1, 1])

    with left:
        with card("products", "🏷️", "Key Product Revenues", STEEL):
            if products.empty:
                empty_state("Product table will appear when data matches.")
            else:
                product_table(products)

    with right:
        with card("bycat", "📊", "Sales by Product", SLATE):
            if products.empty:
                empty_state("Product chart will appear when data matches.")
            else:
                top5 = products.head(5)

                fig = make_subplots(specs=[[{"secondary_y": True}]])

                fig.add_trace(
                    go.Bar(
                        x=[short_label(d, 16) for d in top5["description"]],
                        y=top5["revenue"],
                        name="Revenue",
                        marker={"color": SERIES[: len(top5)]},
                        text=[money(v, 0) for v in top5["revenue"]],
                        textposition="outside",
                        cliponaxis=False,
                        customdata=top5[["description", "stock_code"]],
                        hovertemplate=(
                            "<b>%{customdata[0]}</b><br>"
                            "Code: %{customdata[1]}<br>"
                            "Revenue: £%{y:,.2f}<extra></extra>"
                        ),
                    ),
                    secondary_y=False,
                )

                fig.add_trace(
                    go.Scatter(
                        x=[short_label(d, 16) for d in top5["description"]],
                        y=top5["units"],
                        name="Units sold",
                        mode="lines+markers",
                        line={"color": ORANGE, "width": 3},
                        marker={
                            "size": 8, "color": "#FFFFFF",
                            "line": {"color": ORANGE, "width": 2},
                        },
                        hovertemplate="Units: %{y:,.0f}<extra></extra>",
                    ),
                    secondary_y=True,
                )

                style_figure(fig, height=330)

                fig.update_yaxes(
                    tickprefix="£", tickformat="~s", rangemode="tozero",
                    title_text="Revenue", secondary_y=False,
                )
                fig.update_yaxes(
                    rangemode="tozero", showgrid=False,
                    title_text="Units", secondary_y=True,
                )
                fig.update_xaxes(showgrid=False)

                show(fig, "live_by_product")

    # -----------------------------------------------------
    # ROW 2: GEOGRAPHY + ORDER COMPLETION + REVENUE SHARE
    # -----------------------------------------------------

    country_rev = (
        market.groupby("country", as_index=False)["revenue"].sum()
        if not market.empty
        else pd.DataFrame(columns=["country", "revenue"])
    )
    positive = country_rev[country_rev["revenue"] > 0].sort_values(
        "revenue", ascending=False
    )
    positive_total = float(positive["revenue"].sum())

    geo_col, order_col, share_col = st.columns([2.5, 1, 1.25])

    # ---------- Sales by Geography ----------
    with geo_col:
        with card("geo", "🌍", f"Sales by Geography{market_tag}", ORANGE):
            geo = positive.copy()
            geo["iso"] = geo["country"].map(ISO3)
            geo = geo.dropna(subset=["iso"])

            if geo.empty:
                empty_state("Map will appear when data matches.")
            else:
                dial_colors = [NAVY, TEAL, GREEN, YELLOW]
                dials = [
                    (row.country, row.revenue / positive_total * 100)
                    for row in positive.head(4).itertuples()
                ]

                gl, gm, gr = st.columns([1, 3.4, 1])

                with gl:
                    for i in (0, 1):
                        if i < len(dials):
                            ring_gauge(
                                dials[i][0], dials[i][1],
                                dial_colors[i], f"ring_{i}",
                            )

                with gm:
                    # Log scale: otherwise one big market turns every
                    # other country the same pale colour.
                    geo["intensity"] = np.log10(geo["revenue"] + 1)

                    fig = go.Figure(
                        go.Choropleth(
                            locations=geo["iso"],
                            locationmode="ISO-3",
                            z=geo["intensity"],
                            customdata=geo[["country", "revenue"]],
                            colorscale=[
                                [0.0, "#cfe9ee"],
                                [0.5, TEAL],
                                [1.0, NAVY],
                            ],
                            showscale=False,
                            marker_line_color="#FFFFFF",
                            marker_line_width=0.6,
                            hovertemplate=(
                                "<b>%{customdata[0]}</b><br>"
                                "Revenue: £%{customdata[1]:,.0f}"
                                "<extra></extra>"
                            ),
                        )
                    )
                    fig.update_geos(
                        fitbounds="locations",
                        visible=False,
                        showcountries=True,
                        countrycolor="#FFFFFF",
                        showland=True,
                        landcolor="#E3E8EE",
                        projection_type="natural earth",
                        bgcolor="rgba(0,0,0,0)",
                    )
                    fig.update_layout(
                        height=300,
                        margin={"l": 0, "r": 0, "t": 0, "b": 0},
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    show(fig, "live_map")

                with gr:
                    for i in (2, 3):
                        if i < len(dials):
                            ring_gauge(
                                dials[i][0], dials[i][1],
                                dial_colors[i], f"ring_{i}",
                            )

    # ---------- Order completion donut ----------
    with order_col:
        with card("orders", "🧾", "Order Completion", RED):
            completed = cur["orders"]
            cancelled_n = cur["cancelled_orders"]

            if completed + cancelled_n == 0:
                empty_state("Appears when data matches.")
            else:
                fig = go.Figure(
                    go.Pie(
                        labels=["Completed", "Cancelled"],
                        values=[completed, cancelled_n],
                        hole=0.62,
                        sort=False,
                        direction="clockwise",
                        marker={
                            "colors": [GREEN, RED],
                            "line": {"color": "#FFFFFF", "width": 1.5},
                        },
                        texttemplate=(
                            "<b>%{label}</b><br>"
                            "%{value:,} (%{percent})"
                        ),
                        textposition="outside",
                        hovertemplate=(
                            "<b>%{label}</b><br>"
                            "Invoices: %{value:,}<br>"
                            "Share: %{percent}<extra></extra>"
                        ),
                        showlegend=False,
                    )
                )
                style_figure(fig, height=330)
                fig.update_layout(
                    margin={"l": 30, "r": 30, "t": 30, "b": 30},
                    annotations=[{
                        "text": (
                            f"<b>{cur['cancel_rate']:.1f}%</b>"
                            "<br>cancelled"
                        ),
                        "x": 0.5, "y": 0.5, "showarrow": False,
                        "font": {"size": 13, "color": INK},
                    }],
                )
                show(fig, "live_completion")

    # ---------- Revenue share donut ----------
    with share_col:
        with card("share", "🥧", f"Revenue Share by Country{market_tag}",
                  TEAL):
            if positive.empty:
                empty_state("Appears when data matches.")
            else:
                head = positive.head(5)
                other = float(positive.iloc[5:]["revenue"].sum())

                labels = head["country"].tolist()
                values = head["revenue"].tolist()
                colors = SERIES[: len(head)]

                if other > 0:
                    labels.append("Other markets")
                    values.append(other)
                    colors = colors + [NEUTRAL]

                pcts = [v / positive_total * 100 for v in values]

                fig = go.Figure(
                    go.Pie(
                        labels=labels,
                        values=values,
                        hole=0.62,
                        sort=False,
                        direction="clockwise",
                        marker={
                            "colors": colors,
                            "line": {"color": "#FFFFFF", "width": 1},
                        },
                        # Hide labels on slivers so they never overlap.
                        text=[f"{p:.0f}%" if p >= 6 else "" for p in pcts],
                        textinfo="text",
                        textposition="inside",
                        insidetextfont={"color": "#FFFFFF", "size": 12},
                        hovertemplate=(
                            "<b>%{label}</b><br>"
                            "Revenue: £%{value:,.2f}<br>"
                            "Share: %{percent}<extra></extra>"
                        ),
                    )
                )
                style_figure(fig, height=330)
                fig.update_layout(
                    margin={"l": 6, "r": 6, "t": 10, "b": 10},
                    legend={
                        "orientation": "h",
                        "x": 0.5, "xanchor": "center",
                        "y": -0.02, "yanchor": "top",
                        "font": {"size": 10, "color": INK},
                    },
                    annotations=[{
                        "text": (
                            f"<b>{money(positive_total, 0)}</b>"
                            "<br>revenue"
                        ),
                        "x": 0.5, "y": 0.55, "showarrow": False,
                        "font": {"size": 13, "color": INK},
                    }],
                )
                show(fig, "live_share")

    # -----------------------------------------------------
    # ROW 3: REAL-TIME REVENUE + BASKET VALUE
    # -----------------------------------------------------

    left, right = st.columns([1.3, 1])

    with left:
        with card("trend", "⚡", "Real-time Revenue & Orders", STEEL):
            bucket_s = TREND_BUCKET_S[window_s]
            trend = bucketed(win, now, window_s, bucket_s, data_start)

            if trend.empty:
                empty_state("Revenue trend will appear when data arrives.")
            else:
                fig = make_subplots(specs=[[{"secondary_y": True}]])

                fig.add_trace(
                    go.Scatter(
                        x=trend["bucket"],
                        y=trend["revenue"],
                        name="Revenue",
                        mode="lines",
                        line={"color": NAVY, "width": 2.5},
                        fill="tozeroy",
                        fillcolor="rgba(43,79,107,0.10)",
                        hovertemplate=(
                            "%{x|%H:%M:%S}<br>"
                            "Revenue: £%{y:,.2f}<extra></extra>"
                        ),
                    ),
                    secondary_y=False,
                )

                fig.add_trace(
                    go.Scatter(
                        x=trend["bucket"],
                        y=trend["orders"],
                        name="Orders",
                        mode="lines",
                        line={"color": ORANGE, "width": 2.2},
                        hovertemplate=(
                            "%{x|%H:%M:%S}<br>"
                            "Orders: %{y:,}<extra></extra>"
                        ),
                    ),
                    secondary_y=True,
                )

                style_figure(fig, height=330)

                fig.update_xaxes(tickformat="%H:%M:%S", title=None)
                fig.update_yaxes(
                    tickprefix="£", tickformat="~s", rangemode="tozero",
                    title_text="Revenue", secondary_y=False,
                )
                # Orders are whole numbers: no 17.6 / 16.00 ticks.
                fig.update_yaxes(
                    tickformat=",.0f", rangemode="tozero",
                    showgrid=False, title_text="Orders",
                    secondary_y=True,
                )

                show(fig, "live_ts")

    with right:
        with card("basket", "🛒", "Basket Value (avg)", NAVY):
            basket_s = BASKET_BUCKET_S[window_s]
            basket = bucketed(win, now, window_s, basket_s, data_start)

            if basket.empty or basket["orders"].sum() == 0:
                empty_state("Basket value will appear when data arrives.")
            else:
                basket["aov"] = np.where(
                    basket["orders"] > 0,
                    basket["revenue"] / basket["orders"].replace(0, np.nan),
                    np.nan,
                    )

                fig = go.Figure(
                    go.Scatter(
                        x=basket["bucket"],
                        y=basket["aov"],
                        mode="lines+markers+text",
                        line={"color": SLATE, "width": 3,
                              "shape": "spline", "smoothing": 0.8},
                        marker={
                            "size": 8, "color": "#FFFFFF",
                            "line": {"color": SLATE, "width": 2},
                        },
                        text=[
                            "" if pd.isna(v) else f"£{v:,.0f}"
                            for v in basket["aov"]
                        ],
                        textposition="top center",
                        textfont={"size": 10, "color": INK},
                        connectgaps=True,
                        hovertemplate=(
                            "%{x|%H:%M:%S}<br>"
                            "Avg basket: £%{y:,.2f}<extra></extra>"
                        ),
                    )
                )

                style_figure(fig, height=330)

                fig.update_xaxes(tickformat="%H:%M:%S", showgrid=False)
                fig.update_yaxes(
                    tickprefix="£", tickformat="~s",
                    title_text="Avg order value",
                )

                show(fig, "live_basket")

    # -----------------------------------------------------
    # LIVE TRANSACTION FEED
    # -----------------------------------------------------

    with card("feed", "📋", "Live Transaction Feed", SLATE):
        if win.empty:
            st.info(
                "The transaction feed will show matching "
                "transactions here."
            )
        else:
            feed = win.tail(12).iloc[::-1].copy()
            feed["event_time"] = feed["event_time"].dt.strftime("%H:%M:%S")

            st.dataframe(
                feed[REQUIRED_COLUMNS],
                width="stretch",
                hide_index=True,
                column_config={
                    "event_time": "Time",
                    "invoice": "Invoice",
                    "stock_code": "Stock Code",
                    "description": "Product",
                    "quantity": st.column_config.NumberColumn(
                        "Quantity", format="%.0f"
                    ),
                    "price": st.column_config.NumberColumn(
                        "Price", format="£%.2f"
                    ),
                    "revenue": st.column_config.NumberColumn(
                        "Revenue", format="£%.2f"
                    ),
                    "customer_id": "Customer ID",
                    "country": "Country",
                },
            )


# ---------------------------------------------------------
# AUTO-REFRESH
# ---------------------------------------------------------

live_view_fragment = st.fragment(run_every=float(refresh))(live_view)

live_view_fragment()

st.markdown("---")

st.caption(
    "Retail Sales Analytics · Live | "
    "Built with Python, Kafka, Pandas, Plotly and Streamlit"
)