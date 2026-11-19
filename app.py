"""
Smart Water Quality Monitoring System
Run with:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Water Quality Monitor",
    layout="wide",
    initial_sidebar_state="expanded",
)

from core import database as db  # noqa: E402
from ui.components import sidebar_brand, sidebar_footer  # noqa: E402
from ui.styles import apply_styles  # noqa: E402
from views import dashboard, detection, reports  # noqa: E402

PAGES = {
    "Dashboard": dashboard.render,
    "Water Detection": detection.render,
    "Monitoring Reports": reports.render,
}


@st.cache_resource
def setup_database() -> bool:
    db.init_db()
    return True


def main() -> None:
    apply_styles()
    setup_database()

    with st.sidebar:
        sidebar_brand()
        page = st.radio("Navigation", list(PAGES), label_visibility="collapsed", key="nav")
        sidebar_footer()

    # The drone runs in background threads, so changing pages never interrupts a flight.
    PAGES[page]()


if __name__ == "__main__":
    main()
