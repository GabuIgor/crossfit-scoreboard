from __future__ import annotations

import html


def display_result_value(score: dict, value) -> str:
    if value is None or value == "":
        return ""

    score_type = score.get("type")

    if score_type == "time":
        try:
            total_seconds = int(float(value))
        except (TypeError, ValueError):
            return str(value)

        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:02d}"

    if score_type == "weight":
        try:
            num = float(value)
            if num.is_integer():
                return str(int(num))
            return str(num)
        except (TypeError, ValueError):
            return str(value)

    if score_type == "reps":
        try:
            num = float(value)
            if num.is_integer():
                return str(int(num))
            return str(num)
        except (TypeError, ValueError):
            return str(value)

    return str(value)


def compact_page_style() -> None:
    import streamlit as st

    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.8rem;
            padding-bottom: 1.2rem;
            max-width: 1500px;
        }
        h1, h2, h3 {
            line-height: 1.28 !important;
            overflow: visible !important;
            padding-top: 0.06rem !important;
            padding-bottom: 0.06rem !important;
        }
        h1 { font-size: 1.55rem !important; margin-bottom: 0.45rem !important; }
        h2 { font-size: 1.2rem !important; margin-bottom: 0.35rem !important; }
        h3 { font-size: 1.0rem !important; margin-bottom: 0.25rem !important; }
        p, li, label, .stCaption, .stMarkdown, .stTextInput, .stSelectbox, .stNumberInput {
            font-size: 0.92rem !important;
        }
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) {
            gap: 0.45rem;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.45rem;
        }
        .stButton > button, .stDownloadButton > button {
            padding-top: 0.35rem !important;
            padding-bottom: 0.35rem !important;
        }
        div[data-testid="stDataFrame"] table { font-size: 0.88rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def escape_html(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)
