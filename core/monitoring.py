"""
Location-based detection grouping.

- summarize_detections(): turns a list of boxes into {class: {count, max_conf}}
- DetectionAggregator: buffers live-camera frames and releases one summary per
  time window, so the camera never writes to the database on every frame.
- record_detections(): writes one summary into the grouped tables, opens or
  updates the location's alert, and sends it to the mock PUB system.
- location_overview(): one row per location for the dashboard and reports.
"""
import time

import config
from core import database as db
from core import pub_service
from core.classification import describe_issue, display_name, is_alert_class, level_for


def summarize_detections(detections: list[dict]) -> dict:
    summary = {}
    for det in detections:
        item = summary.setdefault(det["class_name"], {"count": 0, "max_conf": 0.0})
        item["count"] += 1
        item["max_conf"] = max(item["max_conf"], det["confidence"])
    return summary


def summary_text(summary: dict) -> str:
    return ", ".join(
        f"{display_name(c)} x{s['count']}" for c, s in sorted(summary.items())
    )


class DetectionAggregator:
    """Collects live detections and releases one summary per time window."""

    def __init__(self, window_seconds: int = config.AGGREGATION_WINDOW_SECONDS,
                 min_frames: int = config.MIN_FRAMES_PER_WINDOW):
        self.window_seconds = window_seconds
        self.min_frames = min_frames
        self._reset()

    def _reset(self):
        self.buffer = {}
        self.window_start = time.time()

    def add_frame(self, detections: list[dict]) -> None:
        for class_name, item in summarize_detections(detections).items():
            buf = self.buffer.setdefault(class_name, {"count": 0, "max_conf": 0.0, "frames": 0})
            # Objects visible at the same time = peak count in any single frame
            buf["count"] = max(buf["count"], item["count"])
            buf["max_conf"] = max(buf["max_conf"], item["max_conf"])
            buf["frames"] += 1

    def ready(self) -> bool:
        return time.time() - self.window_start >= self.window_seconds

    def seconds_until_flush(self) -> int:
        return max(0, int(self.window_seconds - (time.time() - self.window_start)))

    def flush(self) -> dict:
        stable = {
            c: {"count": b["count"], "max_conf": b["max_conf"]}
            for c, b in self.buffer.items()
            if b["frames"] >= self.min_frames
        }
        self._reset()
        return stable


def record_detections(location_id: int, summary: dict, source: str,
                      source_ref: str | None = None) -> dict:
    """Write a detection summary into the grouped location report."""
    if not summary:
        return {"recorded": False, "reason": "empty"}

    ts = db.now_str()
    alert_id = None
    alert_classes = sorted(c for c in summary if is_alert_class(c))

    with db.get_connection() as conn:
        if source_ref and db.summary_exists(conn, location_id, source_ref):
            return {"recorded": False, "reason": "duplicate"}

        for class_name, item in summary.items():
            db.upsert_detection_report(conn, location_id, class_name,
                                       item["count"], item["max_conf"], ts)

        if alert_classes:
            reports = {r["class_name"]: r for r in db.get_location_reports(conn, location_id)}
            alert = db.get_active_alert(conn, location_id)
            classes = set(alert_classes)
            if alert:
                classes |= set(alert["classes"].split(","))
            classes = sorted(classes)

            counts = {c: reports[c]["detection_count"] for c in classes if c in reports}
            issues = "; ".join(describe_issue(c, n) for c, n in counts.items())
            severity = "High" if any(level_for(n) == "High" for n in counts.values()) else "Moderate"

            if alert:
                db.update_alert(conn, alert["id"], ",".join(classes), issues, severity, ts)
                alert_id = alert["id"]
            else:
                alert_id = db.create_alert(conn, location_id, ",".join(classes), issues, severity, ts)

        status = "Active Alert" if alert_classes else "Healthy"
        total = sum(item["count"] for item in summary.values())
        db.insert_detection_summary(conn, location_id, source, source_ref,
                                    summary_text(summary), total, status, ts)

    pub_result = pub_service.submit_alert_report(location_id, alert_id) if alert_id else None
    return {"recorded": True, "status": status, "summary": summary_text(summary),
            "alert_id": alert_id, "pub": pub_result, "timestamp": ts}


def _location_status(reports: list[dict], active_alert: dict | None) -> str:
    if active_alert:
        return "Active Alert"
    if any(is_alert_class(r["class_name"]) for r in reports):
        return "Resolved"
    if reports:
        return "Healthy"
    return "No Data"


def _detection_text(reports: list[dict], active_alert: dict | None) -> str:
    if active_alert:
        return active_alert["issues"]
    issues = [describe_issue(r["class_name"], r["detection_count"])
              for r in reports if is_alert_class(r["class_name"])]
    if issues:
        return "; ".join(issues)
    if reports:
        return "Clean Water"
    return "No detections yet"


STATUS_ORDER = {"Active Alert": 0, "Resolved": 1, "Healthy": 2, "No Data": 3}


def location_overview(include_empty: bool = True) -> list[dict]:
    locations = db.get_locations()
    reports = db.get_all_reports()
    active = {a["location_id"]: a for a in db.get_active_alerts()}
    latest_pub = db.get_latest_pub_by_location()

    rows = []
    for loc in locations:
        loc_reports = [r for r in reports if r["location_id"] == loc["id"]]
        if not loc_reports and not include_empty:
            continue
        alert = active.get(loc["id"])
        pub = latest_pub.get(loc["id"])
        rows.append({
            "id": loc["id"],
            "name": loc["name"],
            "area": loc["area"] or "-",
            "reports": loc_reports,
            "alert": alert,
            "pub": pub,
            "status": _location_status(loc_reports, alert),
            "detection": _detection_text(loc_reports, alert),
            "pub_status": pub["status"] if pub else "Not Sent",
            "last_updated": max((r["last_detected"] for r in loc_reports), default="-"),
        })

    rows.sort(key=lambda r: r["last_updated"], reverse=True)
    rows.sort(key=lambda r: STATUS_ORDER[r["status"]])
    return rows
