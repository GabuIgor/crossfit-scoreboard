import streamlit as st


def apply_compact_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0.75rem !important;
            padding-bottom: 0.7rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }

        section[data-testid="stSidebar"] {
            min-width: 220px !important;
            max-width: 220px !important;
        }

        div[data-testid="stVerticalBlock"] {
            gap: 0.35rem !important;
        }

        div[data-testid="stHorizontalBlock"] {
            gap: 0.45rem !important;
        }

        h1 {
            font-size: 1.55rem !important;
            line-height: 1.15 !important;
            margin: 0 0 0.35rem 0 !important;
        }

        h2 {
            font-size: 1.1rem !important;
            line-height: 1.15 !important;
            margin: 0.2rem 0 0.25rem 0 !important;
        }

        h3 {
            font-size: 1rem !important;
            line-height: 1.1 !important;
            margin: 0.15rem 0 0.2rem 0 !important;
        }

        p, li, label, [data-testid="stCaptionContainer"], [data-testid="stMarkdownContainer"] p {
            font-size: 0.92rem !important;
        }

        [data-testid="stToolbar"] {
            top: 0.25rem !important;
        }

        div[data-testid="stForm"] {
            padding: 0.55rem 0.7rem !important;
            border-radius: 10px !important;
        }

        div[data-testid="stForm"] > div {
            gap: 0.3rem !important;
        }

        [data-testid="stAlertContainer"] {
            padding-top: 0.1rem !important;
            padding-bottom: 0.1rem !important;
        }

        [data-testid="stAlert"] {
            padding: 0.45rem 0.7rem !important;
            border-radius: 10px !important;
        }

        div[data-baseweb="input"] input,
        div[data-baseweb="textarea"] textarea,
        div[data-baseweb="select"] > div,
        div[data-testid="stNumberInput"] input {
            min-height: 2rem !important;
            padding-top: 0.25rem !important;
            padding-bottom: 0.25rem !important;
            font-size: 0.92rem !important;
        }

        div[data-testid="stNumberInput"] button,
        div[data-baseweb="select"] svg {
            transform: scale(0.9);
        }

        [data-testid="stFileUploaderDropzone"] {
            padding: 0.55rem 0.7rem !important;
        }

        button[kind], .stDownloadButton button {
            min-height: 2rem !important;
            padding: 0.28rem 0.75rem !important;
            font-size: 0.9rem !important;
            border-radius: 9px !important;
        }

        .stButton, .stDownloadButton {
            margin-top: 0.1rem !important;
            margin-bottom: 0.1rem !important;
        }

        [data-testid="stCheckbox"] label, [data-testid="stRadio"] label {
            gap: 0.3rem !important;
        }

        [data-testid="stExpander"] details {
            border-radius: 10px !important;
        }

        [data-testid="stExpander"] summary {
            padding-top: 0.3rem !important;
            padding-bottom: 0.3rem !important;
        }

        [data-testid="stExpanderDetails"] {
            padding-top: 0.25rem !important;
        }

        [data-testid="stImage"] img {
            border-radius: 6px;
        }

        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            font-size: 0.88rem !important;
        }

        hr {
            margin: 0.4rem 0 0.45rem 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
