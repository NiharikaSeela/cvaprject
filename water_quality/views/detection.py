"""Water Detection page: DJI Tello live camera and image upload."""
import atexit
import hashlib
import time
from html import escape

import cv2
import streamlit as st

import config
from core import database as db
from core.classification import display_name, is_alert_class
from core.evidence import save_evidence
from core.detector import WaterDetector, decode_image, draw_detections, to_rgb
from core.monitoring import record_detections, summarize_detections
from core.tello_drone import ALERT_WATER, DroneSession
from ui.components import badge, banner, empty_state, html, page_header, section, table
from ui.keyboard_control import keyboard_control

DISPLAY_FPS = 15
TELEMETRY_REFRESH_SECONDS = 0.5


@st.cache_resource(show_spinner="Loading YOLO model...")
def load_detector(model_path: str) -> WaterDetector:
    return WaterDetector(model_path)


@st.cache_resource
def get_drone() -> DroneSession:
    """One drone session shared by the whole app."""
    session = DroneSession()
    # On app shutdown only close the connection; the drone is never landed automatically.
    atexit.register(session.disconnect, True)
    return session


def get_detector() -> WaterDetector | None:
    try:
        return load_detector(str(config.MODEL_PATH))
    except FileNotFoundError:
        banner("alert", "Model weights not found",
               f"Expected file: {config.MODEL_PATH}. Update MODEL_PATH in config.py "
               "or set the WQM_MODEL_PATH environment variable.")
    except Exception as exc:  # e.g. ultralytics not installed or corrupt weights
        banner("alert", "Could not load the YOLO model", str(exc))
    return None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def show_water_status(detections: list[dict]) -> None:
    classes = {d["class_name"] for d in detections}
    alerts = sorted(c for c in classes if is_alert_class(c))
    if alerts:
        banner("alert", "Environmental Alert",
               "Detected: " + ", ".join(display_name(c) for c in alerts))
    elif config.HEALTHY_CLASS in classes:
        banner("ok", "Clear Water Detected", "No pollution indicators found.")
    else:
        banner("neutral", "No objects detected",
               "Try lowering the confidence threshold or using a clearer image.")


def describe_pub(pub: dict | None) -> str:
    if not pub:
        return "No PUB report needed."
    if pub["status"] == "Submitted":
        return f"PUB report submitted ({pub['reference_id']})."
    if pub["status"] == "Failed":
        return "PUB submission failed. It can be retried from Monitoring Reports."
    return f"PUB: {pub['message']}"


# ---------------------------------------------------------------------------
# Live Camera (DJI Tello)
# ---------------------------------------------------------------------------
def water_banner_html(water: str) -> str:
    if water in ALERT_WATER:
        kind, title, text = "alert", "Environmental Alert", f"Confirmed: {water.title()}"
    elif water == "CLEAN":
        kind, title, text = "ok", "Clear Water Detected", "No pollution indicators found."
    elif water == "OFF":
        kind, title, text = ("neutral", "Detection off",
                             "Press I to start AI detection on the drone feed.")
    else:
        kind, title, text = ("neutral", "Scanning",
                             f"Waiting for {config.VOTES_NEEDED} of the last "
                             f"{config.VOTE_WINDOW} frames to agree.")
    return (f'<div class="wq-banner {kind}"><div class="wq-banner-title">{title}</div>'
            f'<div class="wq-banner-text">{escape(text)}</div></div>')


def telemetry_html(s: dict) -> str:
    battery_class = "wq-stat-value alert" if s["low_battery"] else "wq-stat-value"
    distance_class = "wq-stat-value alert" if s["obstacle"] else "wq-stat-value"
    flight = badge("Flying" if s["flying"] else "Landed")
    detection = badge("Detecting" if s["detecting"] else "Detection Off")
    stats = [
        ("Battery", f'<div class="{battery_class}">{escape(s["battery"])}</div>'),
        ("Height", f'<div class="wq-stat-value">{escape(s["height"])}</div>'),
        ("Front Distance", f'<div class="{distance_class}">{escape(s["distance"])}</div>'),
        ("Status", f'<div class="wq-stat-value">{flight} {detection}</div>'),
    ]
    cells = "".join(f'<div class="wq-stat"><div class="wq-stat-label">{label}</div>{value}</div>'
                    for label, value in stats)
    notes = [f"Drone: {s['last']}"]
    if s["low_battery"]:
        notes.append("Battery low - land soon. The drone will not land by itself.")
    error = (f'<div class="wq-live-note" style="color:var(--alert)">{escape(s["error"])}</div>'
             if s["error"] else "")
    return (f'<div class="wq-stats">{cells}</div>'
            f'<div class="wq-live-note">{escape(" ".join(notes))}</div>{error}')


def handle_key(event: dict, drone: DroneSession, detector: WaterDetector) -> None:
    """Run the action for one key press from the keyboard panel."""
    key, cm = event["key"], event.get("cm")

    if key == "m":                                   # arrow distance (works any time)
        drone.set_move_distances(cm or drone.move_cm, drone.forward_cm)
        st.rerun()
    if key == "c":
        with st.spinner("Connecting to the Tello..."):
            ok, message = drone.connect(detector)
        if not ok:
            st.session_state.drone_error = message
        st.rerun()
    if not drone.connected:
        return

    if key == "n":
        drone.disconnect()
        st.rerun()
    elif key == "i":
        drone.stop_detection() if drone.detecting else drone.start_detection()
        st.rerun()
    elif key in ("t", "g", "h", "x"):
        drone.command({"t": "takeoff", "g": "land", "h": "hover", "x": "emergency"}[key])
    else:
        drone.key_move(key, cm)                      # arrows, W/S (cm), Q/E


def live_camera_section(detector: WaterDetector, location: dict, confidence: float) -> None:
    section("Live Camera", "DJI Tello drone, keyboard controlled"
            + (" (test mode: laptop webcam)" if config.DRONE_TEST_MODE else ""))
    drone = get_drone()
    drone.set_target(location["id"], location["name"], confidence)

    def ui_state():
        s = drone.status() if drone.connected else {}
        return (drone.connected, s.get("flying", False), s.get("busy", False),
                s.get("detecting", False))

    shown_state = ui_state()
    connected, flying, busy, detecting = shown_state

    video_col, keys_col = st.columns([3, 2], gap="medium")
    with keys_col:
        event = keyboard_control(connected, flying, busy, detecting,
                                 drone.move_cm, drone.forward_cm)
        if event:
            handle_key(event, drone, detector)

    with video_col:
        if not drone.connected:
            error = st.session_state.pop("drone_error", None)
            if error:
                banner("alert", "Drone connection failed", error)
            empty_state("Drone not connected. Turn on the Tello, join its TELLO-XXXXXX Wi-Fi, "
                        "then press C on your keyboard.")
            return
        telemetry_slot = st.empty()
        frame_slot = st.empty()
        water_slot = st.empty()
        note_slot = st.empty()

    last_frame, last_telemetry, last_water = -1, 0.0, None
    while drone.connected:
        # Take-off succeeded, landing finished, a move completed or detection
        # changed: redraw so the keyboard panel enables/disables the right keys.
        if ui_state() != shown_state:
            st.rerun()
        status = drone.status()
        if not status:
            break

        frame, fid = drone.frame, drone.frame_id
        if frame is not None and fid != last_frame:
            last_frame = fid
            view = draw_detections(frame.copy(), drone.dets) if drone.detecting else frame
            ok, jpeg = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                frame_slot.image(jpeg.tobytes())

        if drone.water != last_water:
            last_water = drone.water
            water_slot.markdown(water_banner_html(last_water), unsafe_allow_html=True)

        if time.time() - last_telemetry >= TELEMETRY_REFRESH_SECONDS:
            last_telemetry = time.time()
            telemetry_slot.markdown(telemetry_html(status), unsafe_allow_html=True)
            notes = [status["report_note"], status["evidence_note"]]
            note_slot.markdown(
                "".join(f'<div class="wq-live-note">{escape(n)}</div>' for n in notes if n),
                unsafe_allow_html=True)

        time.sleep(1 / DISPLAY_FPS)


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------
def image_upload_section(detector: WaterDetector, location: dict, confidence: float) -> None:
    section("Image Upload")
    uploaded = st.file_uploader("Upload a water image",
                                type=["jpg", "jpeg", "png", "bmp", "webp"])
    if uploaded is None:
        empty_state("Upload an image to analyse water quality at the selected location.")
        return

    data = uploaded.getvalue()
    image = decode_image(data)
    if image is None:
        banner("alert", "Unreadable image", "Please upload a valid JPG or PNG file.")
        return

    with st.spinner("Analysing image..."):
        annotated, detections = detector.detect(image, confidence)

    left, right = st.columns(2)
    with left:
        st.image(to_rgb(image), caption="Original")
    with right:
        st.image(to_rgb(annotated), caption="Detection result")

    show_water_status(detections)
    if not detections:
        return

    table(
        [
            {
                "Class": display_name(d["class_name"]),
                "Confidence": f"{d['confidence']:.1%}",
                "Category": "Active Alert" if is_alert_class(d["class_name"]) else "Healthy",
            }
            for d in sorted(detections, key=lambda d: d["confidence"], reverse=True)
        ],
        ["Class", "Confidence", "Category"],
        badge_columns=("Category",),
    )

    # Each image is recorded once per location (hash-based duplicate prevention)
    image_ref = "img:" + hashlib.sha1(data).hexdigest()
    result = record_detections(location["id"], summarize_detections(detections),
                               source="Image", source_ref=image_ref)
    if result["recorded"]:
        try:
            paths = save_evidence(image, detections, location["name"], "Image")
            evidence = f"Evidence saved: {len(paths)} photo(s) in {config.EVIDENCE_DIR}."
        except OSError as exc:
            evidence = f"Could not save evidence: {exc}"
        html(f'<div class="wq-live-note">Saved to the {escape(location["name"])} report. '
             f'{describe_pub(result["pub"])} {escape(evidence)}</div>')
    elif result["reason"] == "duplicate":
        html(f'<div class="wq-live-note">This image is already recorded for '
             f'{escape(location["name"])}. The report was not updated again.</div>')


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def render() -> None:
    page_header("Water Detection",
                "Monitor water from the drone camera or an uploaded image. "
                "Results are grouped into the selected location's report.")

    locations = db.get_locations()
    names = [loc["name"] for loc in locations]
    c1, c2 = st.columns([2, 1])
    with c1:
        selected = st.selectbox("Monitoring location", names, key="selected_location")
    with c2:
        confidence = st.slider("Confidence threshold", 0.10, 0.90,
                               config.DEFAULT_CONFIDENCE, 0.05, key="confidence")
    location = next(loc for loc in locations if loc["name"] == selected)

    detector = get_detector()
    if detector is None:
        return
    html(f'<div class="wq-live-note">Model: {escape(str(config.MODEL_PATH))}</div>')

    # Live Camera is shown first, but filled last: its display loop keeps running,
    # so the Image Upload section must be drawn before the loop starts.
    live_area = st.container()
    image_area = st.container()

    with image_area:
        image_upload_section(detector, location, confidence)
    with live_area:
        live_camera_section(detector, location, confidence)
