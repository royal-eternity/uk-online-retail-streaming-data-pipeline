"""Shared look and feel for the retail dashboards.

Visual language follows the reference "Retail Dashboard" template:
steel-blue banner, solid coloured KPI tiles, white cards with an
icon + title, soft grey page background.
"""

import streamlit as st

# ---------------------------------------------------------
# PALETTE (taken from the reference dashboard)
# ---------------------------------------------------------

STEEL = "#4a7f9e"    # banner / primary
TEAL = "#6cc5d1"     # KPI 1
GREEN = "#5cb870"    # KPI 2
SLATE = "#5b8aa5"    # KPI 3
YELLOW = "#e9b824"   # KPI 4
ORANGE = "#f28c28"   # line accent
RED = "#e0605e"
NAVY = "#2b4f6b"
INK = "#2e3f4f"
MUTED = "#6b7c8c"
GRID = "#e7edf3"
BORDER = "#d5dee6"
PAGE_BG = "#e8eef2"
NEUTRAL = "#c4ced8"
FONT = "Inter, 'Segoe UI', Arial, sans-serif"

# Slice / bar colours used in order across charts.
SERIES = [NAVY, TEAL, GREEN, YELLOW, RED, SLATE]


# ---------------------------------------------------------
# PLOTLY STYLING
# ---------------------------------------------------------

def style_figure(fig, title: str = "", height: int = 330):
    """Apply the shared chart style to a Plotly figure.

    Cards already show a title, so `title` is normally empty.
    """
    fig.update_layout(
        title=(
            {
                "text": title,
                "font": {"size": 14, "color": INK, "family": FONT},
                "x": 0.01,
                "xanchor": "left",
            }
            if title else None
        ),
        height=height,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font={"family": FONT, "size": 11, "color": INK},
        margin={"l": 10, "r": 16, "t": 56 if title else 30, "b": 28},
        hoverlabel={
            "bgcolor": NAVY,
            "bordercolor": NAVY,
            "font": {"color": "#FFFFFF", "size": 12, "family": FONT},
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.0,
            "xanchor": "right",
            "x": 1,
            "font": {"size": 11, "color": INK},
        },
        bargap=0.35,
    )

    axis = {
        "showgrid": True,
        "gridcolor": GRID,
        "zeroline": False,
        "linecolor": BORDER,
        "tickfont": {"color": MUTED, "size": 10},
        "title_font": {"color": INK, "size": 11},
    }
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


# ---------------------------------------------------------
# HTML COMPONENTS
# ---------------------------------------------------------

def kpi_card(
        label: str,
        value: str,
        color: str,
        delta: float | None = None,
        note: str = "",
) -> str:
    """Solid coloured KPI tile with optional % change."""
    if delta is None:
        footer = note or "&nbsp;"
    else:
        if delta > 0.05:
            arrow = "▲"
        elif delta < -0.05:
            arrow = "▼"
        else:
            arrow = "●"
        footer = f"{arrow} {abs(delta):.1f}% vs previous window"

    return (
        f'<div class="kpi" style="background:{color};">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-foot">{footer}</div>'
        "</div>"
    )


def card_title(icon: str, title: str, color: str) -> str:
    """Card heading: round coloured icon + title."""
    return (
        '<div class="card-head">'
        f'<span class="card-icon" style="background:{color};">{icon}</span>'
        f'<span class="card-title">{title}</span>'
        "</div>"
    )


# ---------------------------------------------------------
# GLOBAL CSS
# ---------------------------------------------------------
# NOTE: no blank lines inside the <style> block, otherwise
# Streamlit's markdown parser ends the HTML block early.

_FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2"
    "?family=Inter:wght@400;500;600;700;800&display=swap');"
)

_RULES = """
html, body, .stApp { font-family: var(--font); }
.stApp { background: var(--page); color: var(--ink); }
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1600px; padding-top: 1.2rem; padding-bottom: 3rem; }
[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid var(--border); }
[data-testid="stSidebar"] * { color: var(--ink); }
[data-testid="stSidebar"] h1 { font-size: 1.2rem; color: var(--steel); font-weight: 800; }
[data-testid="stSidebar"] h3 { font-size: 0.76rem; letter-spacing: 0.08em; color: var(--steel); font-weight: 800; margin-top: 0.6rem; }
[data-testid="stSidebar"] input { color: var(--ink) !important; }
[data-testid="stSidebar"] [data-baseweb="select"] > div { background: #f4f7fa !important; border: 1px solid #cfdae3 !important; border-radius: 6px; }
[data-testid="stSidebar"] [data-baseweb="tag"] { background: var(--steel) !important; border-radius: 4px; }
[data-testid="stSidebar"] [data-baseweb="tag"] span, [data-testid="stSidebar"] [data-baseweb="tag"] svg { color: #fff !important; fill: #fff !important; }
.dash-banner { background: var(--steel); border-radius: 4px; padding: 18px 24px; margin-bottom: 14px; text-align: center; position: relative; box-shadow: 0 2px 6px rgba(43,79,107,0.18); }
.dash-banner h1 { color: #fff !important; font-size: 30px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.02em; margin: 0; padding: 0; line-height: 1.2; }
.dash-banner p { color: #e3eef5 !important; font-size: 12.5px; margin: 4px 0 0; letter-spacing: 0.04em; }
.live-pill { position: absolute; right: 20px; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.5); color: #fff; border-radius: 20px; padding: 5px 14px; font-size: 12px; font-weight: 700; letter-spacing: 0.1em; white-space: nowrap; }
.live-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #ff5a5a; margin-right: 8px; animation: pulse 1.4s infinite; }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(255,90,90,0.65); } 70% { box-shadow: 0 0 0 9px rgba(255,90,90,0); } 100% { box-shadow: 0 0 0 0 rgba(255,90,90,0); } }
.brand-box { background: #fff; border-radius: 4px; min-height: 86px; margin-bottom: 12px; display: flex; flex-direction: column; justify-content: center; align-items: center; box-shadow: 0 2px 5px rgba(43,79,107,0.12); }
.brand-box .brand-name { color: var(--teal); font-size: 19px; font-weight: 800; letter-spacing: 0.04em; text-transform: uppercase; }
.brand-box .brand-sub { color: var(--muted); font-size: 11.5px; margin-top: 3px; }
.kpi { border-radius: 4px; padding: 12px 10px 8px; color: #fff; text-align: center; box-shadow: 0 2px 5px rgba(43,79,107,0.15); min-height: 86px; margin-bottom: 12px; }
.kpi-label { font-size: 13px; font-weight: 500; opacity: 0.96; }
.kpi-value { font-size: 25px; font-weight: 800; line-height: 1.2; overflow-wrap: anywhere; }
.kpi-foot { font-size: 10.5px; opacity: 0.92; min-height: 14px; }
.info-strip { background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 9px 18px; font-size: 12.5px; color: #4a5b6a; margin-bottom: 14px; text-align: center; }
.info-strip b { color: var(--steel); }
div[class*="st-key-card-"] { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px 10px; margin-bottom: 14px; box-shadow: 0 1px 4px rgba(43,79,107,0.08); }
.card-head { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.card-icon { width: 30px; height: 30px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 15px; flex: none; }
.card-title { font-size: 17px; font-weight: 600; color: var(--ink); }
.ref-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.ref-table th { color: var(--steel); font-weight: 700; text-align: right; padding: 7px 8px; border-bottom: 2px solid var(--border); white-space: nowrap; }
.ref-table td { text-align: right; padding: 7px 8px; border-bottom: 1px solid #edf1f5; color: var(--ink); }
.ref-table th.l, .ref-table td.l { text-align: left; }
.ref-table tr:nth-child(even) td { background: #f6f9fb; }
.ring-label { text-align: center; font-size: 11.5px; color: var(--muted); margin: -6px 0 6px; font-weight: 600; }
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 6px; }
hr { border-color: #cfdae3; }
"""


def apply_theme() -> None:
    """Apply shared dashboard CSS."""
    root = (
        ":root {"
        f"--steel:{STEEL}; --teal:{TEAL}; --green:{GREEN};"
        f"--yellow:{YELLOW}; --orange:{ORANGE}; --red:{RED};"
        f"--navy:{NAVY}; --ink:{INK}; --muted:{MUTED};"
        f"--border:{BORDER}; --page:{PAGE_BG}; --font:{FONT};"
        "}"
    )
    st.markdown(
        f"<style>{_FONT_IMPORT}{root}{_RULES}</style>",
        unsafe_allow_html=True,
    )