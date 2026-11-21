"""Dashboard page: key numbers and location status."""
import streamlit as st

from core import database as db
from core.monitoring import location_overview
from ui.components import empty_state, metric_card, page_header, section, short_time, table


def render() -> None:
    page_header("Dashboard", "Overview of water quality across all monitoring locations.")

    counts = db.get_counts()
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Monitoring Locations", counts["locations"], "Registered sites")
    with c2:
        metric_card("Active Alerts", counts["active_alerts"],
                    "Locations needing attention" if counts["active_alerts"] else "All locations clear",
                    alert=counts["active_alerts"] > 0)
    with c3:
        metric_card("Detection Reports", counts["reports"],
                    f"{counts['pub_submitted']} submitted to PUB")

    section("Location Status")
    overview = location_overview(include_empty=True)
    rows = [
        {
            "Location": o["name"],
            "Area": o["area"],
            "Detection": o["detection"],
            "Status": o["status"],
            "PUB": o["pub_status"],
            "Last Updated": short_time(o["last_updated"]),
        }
        for o in overview
    ]
    if rows:
        table(rows, ["Location", "Area", "Detection", "Status", "PUB", "Last Updated"],
              badge_columns=("Status", "PUB"), muted_columns=("Area", "Last Updated"))
    else:
        empty_state("No monitoring locations yet.")
