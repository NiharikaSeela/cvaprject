"""
DJI Tello / RoboMaster TT integration (adapted from CVA_V3.py).

Includes
  - Drone link: SDK commands over UDP, telemetry, keep-alive, flight command queue
  - Drone live camera feed (UDP 11111 via OpenCV/FFmpeg)
  - AI model: YOLO on every frame, 5-of-8 frame voting for a stable water status
  - Dot-Matrix Display: top LED colour + 8x8 matrix icon follow the water status
  - Distance Sensing Module: front ToF sensor ("EXT tof?"), used to block unsafe
    forward moves
  - Keyboard flight: arrow keys, W/S (distance asked each time), Q/E turns
  - Evidence photos for every confirmed class (core/evidence.py)
  - Location-based reporting: confirmed detections go into the selected
    location's report through the same aggregator used for images

No automatic landing: the drone only lands when Land (G) or Emergency stop
(X X) is pressed. (The Tello firmware itself still lands if it hears nothing from the
computer for 15 seconds; the keep-alive below prevents that while connected.)

Everything runs in background threads. Streamlit only reads the latest frame
and status, so changing pages never interrupts a flight.
"""
import os
import queue
import socket
import threading
import time
from collections import deque

import cv2

import config
from core.camera import open_camera
from core.evidence import save_evidence
from core.monitoring import DetectionAggregator, record_detections

# ---------------------------------------------------------------- Dot-Matrix Display
LED_COLOURS = {"POLLUTION": (255, 0, 0), "CLEAR": (0, 255, 0), "SCANNING": (0, 0, 255)}
LED_OFF = (0, 0, 0)
MATRIX_ICONS = {
    "POLLUTION": ["000rr000", "000rr000", "000rr000", "000rr000",
                  "000rr000", "00000000", "000rr000", "00000000"],
    "CLEAR": ["00000000", "00000b00", "0000bb00", "b000bb00",
              "bb0bb000", "0bbb0000", "00b00000", "00000000"],
    "SCANNING": ["00bbbb00", "0b0000b0", "b00bb00b", "b0b00b0b",
                 "b0b00b0b", "b00bb00b", "0b0000b0", "00bbbb00"],
}

# Voted water status -> display status
WATER_PRIORITY = [
    ("polluted_water", "POLLUTED"),
    ("algal_bloom", "ALGAL BLOOM"),
    ("Plastic", "PLASTIC"),
    ("clean_water", "CLEAN"),
]
ALERT_WATER = {"POLLUTED", "ALGAL BLOOM", "PLASTIC"}

TOF_OUT_OF_RANGE_MM = 8190


# ================================================================ drone link
class TelloLink:
    """Low-level connection to the drone (ported from the Tello class)."""

    def __init__(self, test_mode: bool):
        self.test_mode = test_mode
        self.running = False
        self.flying = False
        self.busy = False
        self.battery = "?"
        self.height = 0
        self.pitch = None
        self.roll = None
        self.distance_cm = None
        self.tof_status = "Not available" if test_mode else "Waiting"
        self.last = "Ready"
        self.lock = threading.Lock()
        self.q = queue.Queue(1)
        self.sock = None
        self.state_sock = None
        self.threads = []

    # -------- lifecycle
    def start(self) -> None:
        self.running = True
        if not self.test_mode:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("", config.TELLO_LOCAL_PORT))
            self.state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.state_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.state_sock.bind(("", config.TELLO_STATE_PORT))
            self.state_sock.settimeout(1)
            self._spawn(self._state_loop)
            self._spawn(self._sensor_loop)
        self._spawn(self._worker)

    def stop(self) -> None:
        self.running = False
        for t in self.threads:
            t.join(timeout=2)
        for s in (self.sock, self.state_sock):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
        self.sock = self.state_sock = None

    def _spawn(self, target) -> None:
        t = threading.Thread(target=target, daemon=True)
        t.start()
        self.threads.append(t)

    # -------- commands
    def raw(self, cmd: str) -> None:
        """Send without waiting for a reply."""
        if self.test_mode or self.sock is None:
            return
        try:
            self.sock.sendto(cmd.encode(), config.TELLO_ADDRESS)
        except OSError:
            pass

    def send(self, cmd: str, timeout: float = 7, quiet: bool = False) -> str:
        """Send and wait for the reply."""
        if self.test_mode:
            return "ok"
        if self.sock is None:
            return "error"
        with self.lock:
            self.sock.setblocking(False)
            try:
                while True:
                    self.sock.recvfrom(1024)   # drop stale replies
            except OSError:
                pass
            self.sock.settimeout(timeout)
            self.raw(cmd)
            try:
                reply = self.sock.recvfrom(1024)[0].decode(errors="ignore").strip()
            except OSError:
                reply = "timeout"
        if not quiet:
            print(f"-> {cmd:<14} <- {reply}")
        return reply

    def rc(self, lr=0, fb=0, ud=0, yaw=0) -> None:
        self.raw(f"rc {lr} {fb} {ud} {yaw}")

    def do(self, label: str, cmd: str) -> bool:
        """Queue a flight command (one at a time)."""
        if self.busy or self.q.full():
            self.last = f"Busy - ignored {label}"
            return False
        self.q.put((label, cmd))
        self.last = f"{label}: in progress"
        return True

    def hover(self) -> None:
        self.rc()
        self.raw("stop")
        self.last = "Hovering"
        while not self.q.empty():
            self.q.get_nowait()

    def land(self) -> None:
        self.hover()
        time.sleep(0.3)
        self.raw("land")
        self.flying, self.last = False, "Landing"

    def emergency(self) -> None:
        self.raw("emergency")
        self.flying, self.last = False, "EMERGENCY STOP - motors off"
        while not self.q.empty():
            self.q.get_nowait()

    # -------- Dot-Matrix Display
    def set_top_led(self, rgb) -> None:
        r, g, b = rgb
        self.raw(f"EXT led {r} {g} {b}")

    def set_matrix(self, rows) -> None:
        pattern = "".join(rows)
        if len(pattern) != 64 or set(pattern) - set("rbp0"):
            raise ValueError("LED matrix needs 64 characters using r, b, p or 0.")
        self.raw(f"EXT mled g {pattern}")

    # -------- background loops
    def _worker(self) -> None:
        while self.running:
            try:
                label, cmd = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            self.busy = True
            self.rc()
            time.sleep(0.15)
            reply = self.send(cmd, 20)
            if self.test_mode:
                time.sleep(1)
            if cmd == "takeoff":
                if reply == "ok" or self.height >= 20:
                    self.flying = True   # all keyboard controls unlock from here
                    self.last = "Take off: ok - keyboard controls enabled"
                else:
                    self.last = f"Take off failed ({reply}). Check battery and drone status."
                time.sleep(config.TAKEOFF_SETTLE_SECONDS)
            else:
                if cmd == "land" and reply == "ok":
                    self.flying = False
                self.last = f"{label}: {reply}"
                time.sleep(config.MOVE_SETTLE_SECONDS)
            self.busy = False

    def _sensor_loop(self) -> None:
        """Distance Sensing Module + keep-alive (the Tello lands after 15 s of silence)."""
        last_battery, failures = 0.0, 0
        while self.running:
            time.sleep(config.TOF_POLL_SECONDS)
            if self.busy:
                continue  # the running flight command keeps the link alive
            if self.tof_status != "Not available":
                reply = self.send("EXT tof?", 1, quiet=True)
                parts = reply.split()
                if len(parts) == 2 and parts[0] == "tof" and parts[1].isdigit():
                    mm = int(parts[1])
                    failures = 0
                    if mm >= TOF_OUT_OF_RANGE_MM:
                        self.distance_cm, self.tof_status = None, "Clear"
                    else:
                        self.distance_cm, self.tof_status = mm // 10, "Measured"
                else:
                    failures += 1
                    if failures >= 5:  # no Dot-Matrix & Distance Sensing Module attached
                        self.distance_cm, self.tof_status = None, "Not available"
            if time.time() - last_battery > config.KEEPALIVE_SECONDS:
                reply = self.send("battery?", 3, quiet=True)
                if reply.isdigit():
                    self.battery = reply
                last_battery = time.time()

    def _state_loop(self) -> None:
        while self.running:
            try:
                data = self.state_sock.recv(1024).decode()
                fields = dict(p.split(":", 1) for p in data.split(";") if ":" in p)
            except (OSError, ValueError, AttributeError):
                continue
            try:
                self.height = int(float(fields.get("h", 0)))
                if "pitch" in fields:
                    self.pitch = float(fields["pitch"])
                if "roll" in fields:
                    self.roll = float(fields["roll"])
            except ValueError:
                pass
            self.battery = fields.get("bat", self.battery)


# ================================================================ session
class DroneSession:
    """Drone + camera + AI + reporting. One shared instance for the whole app.

    Connect (C) starts the video and object detection together (I pauses and
    resumes detection). The drone never takes off, moves or lands on its own.
    """

    def __init__(self):
        self.test_mode = config.DRONE_TEST_MODE
        self.link = None
        self.cap = None
        self.detector = None
        self.running = False
        self.threads = []
        self._lock = threading.Lock()

        self.frame = None
        self.frame_id = 0
        self.dets = []

        self.location_id = None
        self.location_name = ""
        self.confidence = config.DEFAULT_CONFIDENCE
        self.move_cm = config.DRONE_MOVE_CM          # up / down / left / right
        self.forward_cm = config.DRONE_FORWARD_CM    # forward / back

        self._reset_mission()

    def _reset_mission(self) -> None:
        self.detecting = False
        self.water = "OFF"
        self.display_status = None
        self.votes = deque(maxlen=config.VOTE_WINDOW)
        self.aggregator = DetectionAggregator()
        self.report_note = "Detection is off. Press I to start AI detection."
        self.evidence_note = ""
        self.last_evidence = {}
        self.error = ""

    @property
    def connected(self) -> bool:
        return self.running

    def set_target(self, location_id: int, location_name: str, confidence: float) -> None:
        self.location_id, self.location_name, self.confidence = location_id, location_name, confidence

    def set_move_distances(self, move_cm: int, forward_cm: int) -> None:
        clamp = lambda v: int(min(max(v, config.DRONE_MIN_MOVE_CM), config.DRONE_MAX_MOVE_CM))
        self.move_cm, self.forward_cm = clamp(move_cm), clamp(forward_cm)

    # -------- connect / disconnect
    def connect(self, detector) -> tuple[bool, str]:
        with self._lock:
            if self.running:
                return True, "Drone already connected."
            self.detector = detector
            link = TelloLink(self.test_mode)
            try:
                link.start()
            except OSError as exc:
                link.stop()
                return False, f"Could not open the drone ports (UDP 8890/9000): {exc}"

            if self.test_mode:
                cap = open_camera(config.CAMERA_INDEX)
            else:
                if link.send("command") != "ok":
                    link.stop()
                    return False, ("No reply from the Tello. Connect this computer to the "
                                   "drone's TELLO-XXXXXX Wi-Fi and try again.")
                link.send(f"speed {config.DRONE_SPEED_CM_S}")
                battery = link.send("battery?")
                if battery.isdigit():
                    link.battery = battery
                link.send("streamoff")
                link.send("streamon")
                time.sleep(2)
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "fflags;nobuffer|flags;low_delay"
                cap = cv2.VideoCapture(config.TELLO_VIDEO_URL, cv2.CAP_FFMPEG)
                if not cap.isOpened():
                    cap.release()
                    cap = None

            if cap is None:
                if not self.test_mode:
                    link.send("streamoff")
                link.stop()
                return False, ("No video received. Allow Python through Windows Firewall "
                               "(UDP port 11111) and try again.")

            self.link, self.cap = link, cap
            self.frame, self.frame_id, self.dets = None, 0, []
            self._reset_mission()
            self._leds_off()
            self.running = True
            self.threads = []
            for target in (self._reader_loop, self._ai_loop):
                t = threading.Thread(target=target, daemon=True)
                t.start()
                self.threads.append(t)
            # Object detection runs as soon as the video is on (press I to pause it).
            self.start_detection()
            return True, "Drone connected - object detection running."

    def disconnect(self, force: bool = False) -> tuple[bool, str]:
        """Close the connection. Refuses while flying (no automatic landing),
        unless force=True, which is only used when the app itself shuts down."""
        with self._lock:
            if not self.running and self.link is None:
                return True, "Not connected."
            link = self.link
            if link is not None and link.flying and not force:
                link.last = "Land the drone before disconnecting"
                return False, link.last
            self.running = False
            self.detecting = False
            if link is not None:
                link.rc()
                self._leds_off()
                if not self.test_mode:
                    link.send("streamoff", 3)
            for t in self.threads:
                t.join(timeout=3)
            if self.cap is not None:
                self.cap.release()
            if link is not None:
                link.stop()
            self.link, self.cap, self.frame, self.dets = None, None, None, []
            return True, "Disconnected."

    # -------- detection on / off
    def start_detection(self) -> None:
        if not self.running or self.detecting:
            return
        self.votes.clear()
        self.aggregator = DetectionAggregator()
        self.last_evidence = {}
        self.water = "SCANNING"
        self.report_note = "Detection started. Waiting for the first reporting window."
        self.detecting = True
        self._show_status("SCANNING")

    def stop_detection(self) -> None:
        self.detecting = False
        self.dets = []
        self.water = "OFF"
        self.report_note = "Detection is off. Press I to start AI detection."
        self._leds_off()

    # -------- controls
    def command(self, action: str) -> str:
        """Take off (T), Land (G), Hover (H) and Emergency stop (X X)."""
        link = self.link
        if link is None:
            return "Drone not connected."
        if action == "takeoff":
            if link.flying:
                link.last = "Already flying."
                return link.last
            if link.busy:
                link.last = "Busy - wait for the current command"
                return link.last
            if link.battery.isdigit() and int(link.battery) < config.DRONE_MIN_BATTERY:
                link.last = f"Battery {link.battery}% - needs {config.DRONE_MIN_BATTERY}% or more to fly"
                return link.last
            tilt = max(abs(link.pitch or 0), abs(link.roll or 0))
            if tilt > config.MAX_TILT_BEFORE_TAKEOFF:
                link.last = "Drone is tilted - place it on a flat surface"
                return link.last
            link.do("Take off", "takeoff")
        elif action == "land":
            link.land()
        elif action == "hover":
            link.hover()
        elif action == "emergency":
            link.emergency()
        else:
            return "Unknown command."
        return link.last

    # Keyboard key -> (SDK command, label, uses_distance)
    KEY_MOVES = {
        "ArrowUp": ("up", "Up", True),
        "ArrowDown": ("down", "Down", True),
        "ArrowLeft": ("left", "Left", True),
        "ArrowRight": ("right", "Right", True),
        "w": ("forward", "Forward", True),
        "s": ("back", "Back", True),
        "q": ("ccw", "Turn left", False),
        "e": ("cw", "Turn right", False),
    }

    def key_move(self, key: str, cm: int | None = None) -> str:
        """Keyboard flight. Arrow keys use the page distance; W/S use the cm typed in the prompt."""
        link = self.link
        if link is None:
            return "Drone not connected."
        if key not in self.KEY_MOVES:
            return "Unknown key."
        if not link.flying:
            link.last = "Take off first - keyboard control is locked while landed"
            return link.last

        sdk, label, uses_distance = self.KEY_MOVES[key]
        if not uses_distance:
            cmd = f"{sdk} {config.DRONE_TURN_DEGREES}"
        else:
            distance = cm if key in ("w", "s") else self.move_cm
            if distance is None:
                distance = self.forward_cm
            distance = int(distance)
            if not config.DRONE_MIN_MOVE_CM <= distance <= config.DRONE_MAX_MOVE_CM:
                link.last = (f"Distance must be {config.DRONE_MIN_MOVE_CM}-"
                             f"{config.DRONE_MAX_MOVE_CM} cm")
                return link.last
            if key in ("w", "s"):
                self.forward_cm = distance   # remembered as the next prompt's default
            cmd = f"{sdk} {distance}"
            label = f"{label} {distance} cm"

        safe, reason = self._forward_is_safe(cmd)
        if not safe:
            link.last = reason
            return reason
        link.do(label, cmd)
        return link.last

    def _forward_is_safe(self, cmd: str) -> tuple[bool, str]:
        """Distance Sensing Module check before any forward move."""
        if not cmd.startswith("forward") or self.link.tof_status != "Measured":
            return True, ""
        step = int(cmd.split()[1])
        distance = self.link.distance_cm
        if distance is not None and distance < step + config.SAFE_DISTANCE_CM:
            return False, f"Obstacle {distance} cm ahead - forward move blocked"
        return True, ""

    # -------- status for the UI
    def status(self) -> dict:
        link = self.link
        if link is None:
            return {}
        tof = link.tof_status
        if tof == "Measured":
            distance = f"{link.distance_cm} cm"
        elif tof == "Clear":
            distance = "Clear (>120 cm)"
        elif tof == "Waiting":
            distance = "Reading..."
        else:
            distance = "Not available"
        battery_ok = link.battery.isdigit()
        battery = "Test mode" if self.test_mode else (f"{link.battery}%" if battery_ok else "-")
        low_battery = (not self.test_mode and battery_ok
                       and int(link.battery) <= config.DRONE_LOW_BATTERY_WARNING)
        return {
            "battery": battery,
            "low_battery": low_battery,
            "height": "-" if self.test_mode else f"{link.height} cm",
            "distance": distance,
            "obstacle": tof == "Measured" and link.distance_cm is not None
                        and link.distance_cm < config.SAFE_DISTANCE_CM,
            "flying": link.flying,
            "busy": link.busy,
            "detecting": self.detecting,
            "water": self.water,
            "last": link.last,
            "report_note": self.report_note,
            "evidence_note": self.evidence_note,
            "error": self.error,
        }

    # -------- background loops
    def _reader_loop(self) -> None:
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.01)
                continue
            self.frame = cv2.resize(frame, config.DRONE_FRAME_SIZE)
            self.frame_id += 1

    def _ai_loop(self) -> None:
        last = -1
        while self.running:
            if not self.detecting:
                time.sleep(0.05)
                continue
            frame, fid = self.frame, self.frame_id
            if frame is None or fid == last:
                time.sleep(0.01)
                continue
            started, last = time.time(), fid
            try:
                _, dets = self.detector.detect(frame, self.confidence, annotate=False)
                if self.detecting:  # may have been stopped during inference
                    self.dets = dets
                    self._update(dets, frame)
                self.error = ""
            except Exception as exc:  # keep the loop alive; show the error in the UI
                self.error = str(exc)
            time.sleep(max(0.0, 1 / config.AI_FPS - (time.time() - started)))

    def _update(self, dets: list[dict], frame) -> None:
        now = time.time()
        if self.link.busy:  # frames are blurry while the drone is moving
            return

        # 5 of the last 8 frames must agree before the water status changes
        self.votes.append({d["class_name"] for d in dets})
        confirmed = lambda c: sum(c in labels for labels in self.votes) >= config.VOTES_NEEDED
        self.water = next((name for cls, name in WATER_PRIORITY if confirmed(cls)), "SCANNING")

        display = ("POLLUTION" if self.water in ALERT_WATER
                   else "CLEAR" if self.water == "CLEAN" else "SCANNING")
        if display != self.display_status:
            self._show_status(display)

        # Evidence photo for every confirmed class (one per class per cooldown)
        due = {
            d["class_name"] for d in dets
            if confirmed(d["class_name"])
            and now - self.last_evidence.get(d["class_name"], 0) >= config.EVIDENCE_COOLDOWN_SECONDS
        }
        if due:
            try:
                paths = save_evidence(frame, dets, self.location_name or "Unknown",
                                      "Drone", classes=due)
                for class_name in due:
                    self.last_evidence[class_name] = now
                if paths:
                    self.evidence_note = (f"Evidence saved at {time.strftime('%H:%M:%S')}: "
                                          + ", ".join(p.name for p in paths))
            except OSError as exc:
                self.error = f"Could not save evidence: {exc}"

        # Location-based reporting (one database write per window)
        self.aggregator.add_frame(dets)
        if self.aggregator.ready():
            summary = self.aggregator.flush()
            if summary and self.location_id:
                result = record_detections(self.location_id, summary, source="Drone Camera")
                pub = result.get("pub")
                pub_text = f" PUB: {pub['status']}." if pub else ""
                self.report_note = (f"{self.location_name} report updated at "
                                    f"{result['timestamp'][11:]}: {result['summary']}.{pub_text}")
            elif not summary:
                self.report_note = "No stable detections in the last window. Nothing saved."

    def _show_status(self, status: str) -> None:
        """Top LED colour + Dot-Matrix icon."""
        self.display_status = status
        if self.link is not None:
            self.link.set_top_led(LED_COLOURS[status])
            self.link.set_matrix(MATRIX_ICONS[status])

    def _leds_off(self) -> None:
        self.display_status = None
        if self.link is not None:
            self.link.set_top_led(LED_OFF)
            self.link.raw("EXT mled g " + "0" * 64)
