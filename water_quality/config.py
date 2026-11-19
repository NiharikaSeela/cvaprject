"""
Central configuration for the Water Quality Monitoring System.
Change values here instead of editing the individual modules.
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Your trained YOLO weights. You can override this without editing the file:
#   set WQM_MODEL_PATH=D:\some\other\best.pt   (Windows Command Prompt)
DEFAULT_MODEL_PATH = r"C:\Users\seela\Documents\Term4\water_quality\weights\best.pt"

# Searched in this order; the first file that exists is used.
MODEL_CANDIDATES = [
    os.environ.get("WQM_MODEL_PATH", ""),
    DEFAULT_MODEL_PATH,
    str(BASE_DIR / "weights" / "best.pt"),     # weights folder inside this project
    str(BASE_DIR / "best.pt"),
]
MODEL_PATH = next((Path(p) for p in MODEL_CANDIDATES if p and Path(p).is_file()),
                  Path(DEFAULT_MODEL_PATH))

DB_PATH = BASE_DIR / "data" / "water_quality.db"

# Evidence photos: evidence/<Location>/<Class>/<time>_<source>_<confidence>.jpg
EVIDENCE_DIR = BASE_DIR / "evidence"
# Minimum gap between two drone evidence photos of the same class
EVIDENCE_COOLDOWN_SECONDS = 6

# ---------------------------------------------------------------------------
# Model classes (must match the order used during training)
# ---------------------------------------------------------------------------
CLASS_NAMES = {
    0: "Plastic",
    1: "algal_bloom",
    2: "clean_water",
    3: "polluted_water",
}

DISPLAY_NAMES = {
    "Plastic": "Plastic",
    "algal_bloom": "Algal Bloom",
    "clean_water": "Clean Water",
    "polluted_water": "Polluted Water",
}

ALERT_CLASSES = {"Plastic", "algal_bloom", "polluted_water"}
HEALTHY_CLASS = "clean_water"

# Box colours for OpenCV (BGR order)
CLASS_COLORS_BGR = {
    "Plastic": (58, 72, 180),         # muted red
    "algal_bloom": (43, 130, 183),    # amber
    "polluted_water": (60, 60, 140),  # deep red
    "clean_water": (61, 90, 45),      # forest green
}

# ---------------------------------------------------------------------------
# Detection settings
# ---------------------------------------------------------------------------
DEFAULT_CONFIDENCE = 0.45
IMG_SIZE = 640
AI_FPS = 10                 # how many frames per second the drone feed is analysed
VOTE_WINDOW = 8             # water status needs VOTES_NEEDED of the last VOTE_WINDOW frames
VOTES_NEEDED = 5

# ---------------------------------------------------------------------------
# DJI Tello / RoboMaster TT drone
# ---------------------------------------------------------------------------
# True = use the laptop webcam instead of the drone (for testing without flying).
# Flight commands are simulated in test mode.
DRONE_TEST_MODE = False

TELLO_ADDRESS = ("192.168.10.1", 8889)
TELLO_LOCAL_PORT = 9000
TELLO_STATE_PORT = 8890
TELLO_VIDEO_URL = "udp://@0.0.0.0:11111?overrun_nonfatal=1&fifo_size=50000000"
DRONE_FRAME_SIZE = (960, 720)

# Default movement distances (adjustable on the Water Detection page).
# The Tello accepts 20 to 500 cm per command.
DRONE_MOVE_CM = 30          # Up / Down / Left / Right
DRONE_FORWARD_CM = 30       # default shown in the W / S distance prompt
DRONE_MIN_MOVE_CM = 20
DRONE_MAX_MOVE_CM = 500
DRONE_TURN_DEGREES = 90
DRONE_SPEED_CM_S = 40       # flight speed set when connecting
MOVE_SETTLE_SECONDS = 0.8   # pause after each move before the next key is accepted
TAKEOFF_SETTLE_SECONDS = 3.0
KEEPALIVE_SECONDS = 5       # the Tello lands itself after ~15 s without a command
MAX_TILT_BEFORE_TAKEOFF = 10  # degrees; take-off is blocked if the drone is not level
DRONE_MIN_BATTERY = 50      # take-off is blocked below this battery level
DRONE_LOW_BATTERY_WARNING = 20   # shows a warning only; the drone does NOT land automatically

# Distance Sensing Module (front ToF sensor, range about 120 cm)
TOF_POLL_SECONDS = 0.5
SAFE_DISTANCE_CM = 50       # forward moves are blocked if an obstacle is this close after moving

# Webcam (used only when DRONE_TEST_MODE = True)
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# ---------------------------------------------------------------------------
# Location-based aggregation (prevents the live camera from flooding the DB)
# ---------------------------------------------------------------------------
# Live detections are buffered in memory and written once per window.
AGGREGATION_WINDOW_SECONDS = 15
# A class must appear in at least this many frames inside one window to be
# recorded. This filters out single-frame flicker.
MIN_FRAMES_PER_WINDOW = 3

# Severity levels based on the cumulative detection count at a location
MODERATE_LEVEL_THRESHOLD = 3
HIGH_LEVEL_THRESHOLD = 10

# ---------------------------------------------------------------------------
# Mock PUB integration
# ---------------------------------------------------------------------------
# Do not resend an unchanged report to PUB within this period.
PUB_RESUBMIT_SECONDS = 30 * 60
# After a failed submission, wait this long before retrying automatically.
PUB_RETRY_SECONDS = 60
# Probability that the mock endpoint "fails" (to demonstrate the Failed status)
PUB_FAILURE_RATE = 0.10
PUB_SIMULATED_LATENCY_SECONDS = 0.3

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
DEFAULT_LOCATIONS = [
    ("Marina Reservoir", "Central"),
    ("MacRitchie Reservoir", "Central"),
    ("Bedok Reservoir", "East"),
    ("Lower Seletar Reservoir", "North"),
    ("Pandan Reservoir", "West"),
]
