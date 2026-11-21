"""
Reusable UI building blocks. All HTML is built without indentation so
Streamlit's markdown renderer does not treat it as a code block.
"""
from html import escape

import streamlit as st

STATUS_STYLES = {
    "Active Alert": "alert",
    "Active": "alert",
    "Failed": "alert",
    "Healthy": "ok",
    "Submitted": "ok",
    "Pending": "warn",
    "Skipped": "neutral",
    "Resolved": "neutral",
    "Not Sent": "neutral",
    "No Data": "neutral",
    "High": "alert",
    "Moderate": "warn",
    "Flying": "ok",
    "Landed": "neutral",
    "Detecting": "ok",
    "Detection Off": "neutral",
}


def badge(status: str) -> str:
    style = STATUS_STYLES.get(status, "neutral")
    return f'<span class="wq-badge {style}">{escape(str(status))}</span>'


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def sidebar_brand() -> None:
    html(
        '<div class="wq-brand">'
        '<div class="wq-brand-mark">WQ</div>'
        '<div class="wq-brand-title">Water Quality Monitor</div>'
        '<div class="wq-brand-sub">AI-powered environmental monitoring</div>'
        '</div>'
    )


def sidebar_footer() -> None:
    html(
        '<div class="wq-sidebar-foot">'
        'DJI Tello drone with YOLO detection for plastic, algal bloom and polluted water.<br>'
        'Reports are shared with a simulated PUB system.'
        '</div>'
    )


def page_header(title: str, subtitle: str = "") -> None:
    sub = f"<p>{escape(subtitle)}</p>" if subtitle else ""
    html(f'<div class="wq-header"><h1>{escape(title)}</h1>{sub}</div>')


def section(title: str, note: str = "") -> None:
    extra = f"<span>{escape(note)}</span>" if note else ""
    html(f'<div class="wq-section">{escape(title)}{extra}</div>')


def metric_card(label: str, value, note: str = "", alert: bool = False) -> None:
    value_class = "wq-metric-value alert" if alert else "wq-metric-value"
    note_html = f'<div class="wq-metric-note">{escape(note)}</div>' if note else ""
    html(
        f'<div class="wq-card"><div class="wq-metric-label">{escape(label)}</div>'
        f'<div class="{value_class}">{escape(str(value))}</div>{note_html}</div>'
    )


def banner(kind: str, title: str, text: str = "") -> None:
    """kind: 'ok', 'alert' or 'neutral'."""
    body = f'<div class="wq-banner-text">{escape(text)}</div>' if text else ""
    html(f'<div class="wq-banner {kind}"><div class="wq-banner-title">{escape(title)}</div>{body}</div>')


def empty_state(text: str) -> None:
    html(f'<div class="wq-empty">{escape(text)}</div>')


def table(rows: list[dict], columns: list[str], badge_columns=(), muted_columns=()) -> None:
    """Render a list of dicts as a styled HTML table."""
    head = "".join(f"<th>{escape(c)}</th>" for c in columns)
    body_rows = []
    for row in rows:
        cells = []
        for col in columns:
            value = row.get(col, "")
            if col in badge_columns:
                cells.append(f"<td>{badge(value)}</td>")
            elif col in muted_columns:
                cells.append(f'<td class="wq-muted">{escape(str(value))}</td>')
            else:
                cells.append(f"<td>{escape(str(value))}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    html(
        f'<div class="wq-table-wrap"><table class="wq-table"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table></div>'
    )


def short_time(timestamp: str | None) -> str:
    """'2026-11-17 14:05:09' -> '17 Nov, 14:05'."""
    if not timestamp or timestamp == "-":
        return "-"
    from datetime import datetime
    try:
        return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").strftime("%d %b, %H:%M")
    except ValueError:
        return timestamp
