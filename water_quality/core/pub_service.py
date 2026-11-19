"""
Mock PUB (Singapore's National Water Agency) reporting service.

No real API is called. The service:
  1. Builds a summarised payload for a location's active alert.
  2. Records the submission as Pending.
  3. "Transmits" it to a simulated endpoint, which succeeds or fails.
  4. Updates the record to Submitted or Failed.

Duplicate prevention: an unchanged report (same issue types and levels) is not
resent within PUB_RESUBMIT_SECONDS, and a failed report is not retried
automatically within PUB_RETRY_SECONDS.
"""
import hashlib
import json
import random
import time
from datetime import datetime

import config
from core import database as db
from core.classification import display_name, is_alert_class, level_for


def build_payload(conn, location_id: int, alert_id: int) -> dict:
    location = db.get_location(conn, location_id)
    alert = db.get_alert(conn, alert_id)
    reports = db.get_location_reports(conn, location_id)

    issues = [
        {
            "type": display_name(r["class_name"]),
            "level": level_for(r["detection_count"]),
            "detection_count": r["detection_count"],
            "highest_confidence": round(r["highest_confidence"], 3),
            "last_detected": r["last_detected"],
        }
        for r in reports
        if is_alert_class(r["class_name"]) and r["last_detected"] >= alert["created_at"]
    ]

    return {
        "agency": "PUB (simulated)",
        "location": location["name"],
        "area": location["area"],
        "alert_id": alert_id,
        "severity": alert["severity"],
        "summary": alert["issues"],
        "issues": issues,
        "reported_at": db.now_str(),
    }


def _signature(payload: dict) -> str:
    """Hash only what matters: which issues exist and at what level."""
    key = sorted((i["type"], i["level"]) for i in payload["issues"])
    return hashlib.sha256(json.dumps(key).encode()).hexdigest()


def _seconds_since(timestamp: str) -> float:
    return (datetime.now() - db.parse_time(timestamp)).total_seconds()


def _should_skip(last: dict | None, signature: str) -> bool:
    if last is None or last["payload_hash"] != signature:
        return False
    age = _seconds_since(last["updated_at"])
    if last["status"] in ("Submitted", "Pending"):
        return age < config.PUB_RESUBMIT_SECONDS
    if last["status"] == "Failed":
        return age < config.PUB_RETRY_SECONDS
    return False


def _transmit(payload: dict) -> tuple[str, str | None, str]:
    """Simulated network call to PUB."""
    time.sleep(config.PUB_SIMULATED_LATENCY_SECONDS)
    if random.random() < config.PUB_FAILURE_RATE:
        return "Failed", None, "Mock PUB endpoint did not respond (simulated timeout)."
    reference = f"PUB-{datetime.now():%Y%m%d}-{random.randint(10000, 99999)}"
    return "Submitted", reference, "Report accepted by mock PUB system."


def submit_alert_report(location_id: int, alert_id: int, force: bool = False) -> dict:
    with db.get_connection() as conn:
        payload = build_payload(conn, location_id, alert_id)
        if not payload["issues"]:
            return {"status": "Skipped", "reference_id": None,
                    "message": "No active issues to report."}

        signature = _signature(payload)
        last = db.get_last_pub_submission(conn, location_id)
        if not force and _should_skip(last, signature):
            return {"status": "Skipped", "reference_id": last["reference_id"],
                    "message": f"Unchanged since last submission ({last['status']})."}

        submission_id = db.create_pub_submission(
            conn, location_id, alert_id, json.dumps(payload), signature, "Pending", db.now_str()
        )

    # Transmit outside the transaction so the Pending record is already saved
    status, reference, message = _transmit(payload)
    db.update_pub_submission(submission_id, status, reference, message)
    return {"status": status, "reference_id": reference, "message": message,
            "submission_id": submission_id}


def retry_location(location_id: int) -> dict:
    """Manually resubmit the active alert for a location (used by the Retry button)."""
    with db.get_connection() as conn:
        alert = db.get_active_alert(conn, location_id)
    if alert is None:
        return {"status": "Skipped", "reference_id": None,
                "message": "This location has no active alert."}
    return submit_alert_report(location_id, alert["id"], force=True)
