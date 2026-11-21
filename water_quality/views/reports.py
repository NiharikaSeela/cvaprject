"""Monitoring Reports page: grouped reports per location and alert history."""
from html import escape

import streamlit as st

from core import database as db
from core import pub_service
from core.classification import display_name, is_alert_class
from core.monitoring import location_overview
from ui.components import (badge, empty_state, html, page_header, section,
                           short_time, table)


def location_card(loc: dict) -> None:
    with st.container(border=True):
        html(
            '<div class="wq-loc-head"><div>'
            f'<span class="wq-loc-name">{escape(loc["name"])}</span>'
            f'<span class="wq-loc-area">{escape(loc["area"])}</span></div>'
            f'{badge(loc["status"])}</div>'
        )

        table(
            [
                {
                    "Detection Type": display_name(r["class_name"]),
                    "Count": r["detection_count"],
                    "Highest Confidence": f"{r['highest_confidence']:.1%}",
                    "First Detected": short_time(r["first_detected"]),
                    "Last Detected": short_time(r["last_detected"]),
                    "Alert Status": "Active Alert" if is_alert_class(r["class_name"]) and loc["alert"]
                    else ("Resolved" if is_alert_class(r["class_name"]) else "Healthy"),
                }
                for r in loc["reports"]
            ],
            ["Detection Type", "Count", "Highest Confidence", "First Detected",
             "Last Detected", "Alert Status"],
            badge_columns=("Alert Status",), muted_columns=("First Detected", "Last Detected"),
        )

        pub = loc["pub"]
        if pub:
            ref = f" &middot; Ref <b>{pub['reference_id']}</b>" if pub["reference_id"] else ""
            pub_line = f'PUB submission: {badge(pub["status"])}{ref} &middot; {short_time(pub["updated_at"])}'
        else:
            pub_line = f'PUB submission: {badge("Not Sent")}'
        alert_line = (f' &nbsp;&nbsp; Alert: <b>{escape(loc["alert"]["issues"])}</b>'
                      if loc["alert"] else "")
        html(f'<div class="wq-meta">{pub_line}{alert_line}</div>')

        if loc["alert"]:
            b1, b2, _ = st.columns([1, 1, 2])
            with b1:
                if st.button("Resolve Alert", key=f"resolve_{loc['id']}"):
                    db.resolve_alert(loc["alert"]["id"])
                    st.rerun()
            with b2:
                failed = pub is None or pub["status"] == "Failed"
                if st.button("Retry PUB Submission" if failed else "Resend to PUB",
                             key=f"retry_{loc['id']}"):
                    with st.spinner("Submitting to mock PUB..."):
                        pub_service.retry_location(loc["id"])
                    st.rerun()


def render() -> None:
    page_header("Monitoring Reports",
                "Detections grouped by location, with alert status and PUB reporting.")

    overview = location_overview(include_empty=False)
    if not overview:
        empty_state("No reports yet. Detections from the Water Detection page will appear here.")
        return

    options = ["All locations"] + [o["name"] for o in overview]
    choice = st.selectbox("Location", options, label_visibility="collapsed")
    selected = overview if choice == "All locations" else [o for o in overview if o["name"] == choice]

    section("Location Reports", f"{len(selected)} location(s)")
    for loc in selected:
        location_card(loc)

    # ---------------- Alert history ----------------
    section("Alert History")
    alerts = db.get_alert_history(limit=30)
    if choice != "All locations":
        alerts = [a for a in alerts if a["location_name"] == choice]
    if alerts:
        table(
            [
                {
                    "Raised": short_time(a["created_at"]),
                    "Location": a["location_name"],
                    "Issues": a["issues"],
                    "Severity": a["severity"],
                    "Status": a["status"],
                    "Resolved": short_time(a["resolved_at"]),
                }
                for a in alerts
            ],
            ["Raised", "Location", "Issues", "Severity", "Status", "Resolved"],
            badge_columns=("Severity", "Status"), muted_columns=("Raised", "Resolved"),
        )
    else:
        empty_state("No alerts raised yet.")
