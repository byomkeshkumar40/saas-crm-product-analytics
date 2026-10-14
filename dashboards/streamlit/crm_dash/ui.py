"""Shared look & feel: CSS, KPI cards, notes."""
import html
import inspect

import streamlit as st

# Streamlit >= 1.50 uses width="stretch"; older versions use use_container_width=True.
STRETCH = ({"width": "stretch"} if "width" in inspect.signature(st.plotly_chart).parameters
           else {"use_container_width": True})

CSS = """
<style>
html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }
h1 { font-weight: 700; letter-spacing: -0.02em; font-size: 1.9rem !important; margin-bottom: 0.1rem; }
h2, h3 { font-weight: 650; letter-spacing: -0.01em; }
.page-sub { color: #64748B; font-size: 0.95rem; margin: 0 0 1.1rem 0; }
.kpi { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px 16px 12px 16px;
       box-shadow: 0 1px 2px rgba(15,23,42,.04); height: 100%; min-height: 118px; }
.kpi .label { color: #64748B; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.kpi .value { color: #0F172A; font-size: 1.85rem; font-weight: 700; line-height: 1.25; margin-top: 2px; }
.kpi .note { color: #64748B; font-size: 0.74rem; line-height: 1.3; margin-top: 4px; }
.kpi.accent { border-left: 4px solid #2563EB; }
.scope { background: #EFF6FF; border: 1px solid #BFDBFE; color: #1E3A8A; border-radius: 10px;
         padding: 9px 14px; font-size: 0.84rem; margin: 0 0 1rem 0; }
.scope.warn { background: #FFFBEB; border-color: #FDE68A; color: #78350F; }
.section { font-size: 1.05rem; font-weight: 650; margin: 1.3rem 0 0.1rem 0; color: #0F172A; }
.section-cap { color: #64748B; font-size: 0.82rem; margin-bottom: 0.4rem; }
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E2E8F0; }
.footer { color: #94A3B8; font-size: 0.75rem; margin-top: 2rem; border-top: 1px solid #E2E8F0; padding-top: .6rem; }
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str):
    st.markdown(f"# {title}")
    st.markdown(f'<div class="page-sub">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def kpi_row(items, accent=False):
    """items: list of (label, value, note). Rendered as equal-width cards."""
    cols = st.columns(len(items))
    for col, (label, value, note) in zip(cols, items):
        col.markdown(
            f'<div class="kpi{" accent" if accent else ""}"><div class="label">{html.escape(label)}</div>'
            f'<div class="value">{html.escape(str(value))}</div><div class="note">{html.escape(note)}</div></div>',
            unsafe_allow_html=True)


def scope_note(text: str, warn: bool = False):
    st.markdown(f'<div class="scope{" warn" if warn else ""}">{text}</div>', unsafe_allow_html=True)


def section(title: str, caption: str = ""):
    st.markdown(f'<div class="section">{html.escape(title)}</div>', unsafe_allow_html=True)
    if caption:
        st.markdown(f'<div class="section-cap">{html.escape(caption)}</div>', unsafe_allow_html=True)


def footer():
    st.markdown('<div class="footer">Synthetic data (seed 42) · observation window 2026-01-01 to 2026-03-31 · '
                'definitions: reports/kpi_definitions.md</div>', unsafe_allow_html=True)


def fmt_int(x):
    return f"{int(x):,}"


def fmt_pct(x, digits=1):
    return "n/a" if x != x else f"{x:.{digits}f}%"


def fmt_num(x, digits=1):
    return "n/a" if x != x else f"{x:,.{digits}f}"


def plot(fig, key=None):
    st.plotly_chart(fig, theme=None, key=key, config={"displayModeBar": False}, **STRETCH)
