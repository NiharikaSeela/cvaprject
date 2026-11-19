# Smart Water Quality Monitoring System

DJI Tello (RoboMaster TT) + YOLO + Python + Streamlit + SQLite.
The drone camera detects Plastic, Algal Bloom, Polluted Water and Clean Water in real time.
The drone is flown entirely from the keyboard. Results are grouped by location, saved as evidence photos,
shown on the drone's Dot-Matrix Display, and sent to a simulated PUB system.

---

## Step 1 - Project setup (Windows)

1. Install **Python 3.10, 3.11 or 3.12** from python.org (tick "Add Python to PATH").
2. Unzip this folder, for example to:
   `C:\Users\seela\Documents\Term4\water_quality_monitor`
3. Open **Command Prompt** in that folder:

```bat
cd C:\Users\seela\Documents\Term4\water_quality_monitor
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

You should see `(venv)` at the start of the prompt. Activate it again each time you open a new terminal.

## Step 2 - Check the model path

`config.py` points to your weights:

```python
DEFAULT_MODEL_PATH = r"C:\Users\seela\Documents\Term4\water_quality\weights\best.pt"
```

If that file is missing, the app also looks for `weights\best.pt` inside this project folder.
The Water Detection page shows which model file was loaded. Both detection and classification YOLO models work.

## Step 3 - Prepare the drone

1. Attach the **Dot-Matrix Display & Distance Sensing Module** to the RoboMaster TT.
2. Charge the battery (take-off is blocked below 50%).
3. Turn the drone on and connect your laptop to its **TELLO-XXXXXX** Wi-Fi. Close the Tello phone app
   and any other drone script (they use the same ports).
4. The first time, Windows Firewall asks about Python: click **Allow** for private and public networks.
   The app needs incoming UDP on ports **11111** (video), **8890** (telemetry) and **9000** (replies).

## Step 4 - Run

```bat
streamlit run app.py
```

The browser opens at http://localhost:8501. Go to **Water Detection**, choose a location, then press **C**.

**Testing without the drone:** set `DRONE_TEST_MODE = True` in `config.py`. The laptop webcam is used
instead, and flight commands are simulated.

---

## Keyboard controls (Live Camera)

There are no control buttons. The keys work anywhere on the Water Detection page; you do not need to
click the panel first. Keys typed into a text box (for example the location search) are ignored.

| Key | Action | Available |
|---|---|---|
| **C** | Connect to the drone (starts the video and object detection) | When disconnected |
| **T** | Take off | When connected and landed |
| **G** | Land | When flying |
| **H** | Hover (stop and hold position) | When flying |
| **X X** | Emergency stop - motors off, drone drops (press twice within 2 s) | When connected |
| **N N** | Disconnect (press twice within 2 s) | When landed |
| **I** | Pause / resume object detection | When connected |
| **M** | Set the arrow-key distance (cm) | Any time |
| **Arrow Up / Down** | Move up / down by the arrow-key distance | After take-off |
| **Arrow Left / Right** | Move left / right by the arrow-key distance | After take-off |
| **W** | Forward - asks how many cm first | After take-off |
| **S** | Back - asks how many cm first | After take-off |
| **Q / E** | Turn left / right 90 degrees | After take-off |

**Distance prompt (W, S and M).** A box appears in the panel: type the number, press **Enter**.
**Backspace** deletes a digit, **Esc** cancels. Pressing Enter on an empty box uses the value shown
(the last distance you used). Distances must be **20 to 500 cm** (the Tello's limits).

**Controls unlock after take-off.** Before take-off the flight keys are greyed out and pressing them
shows "Take off first (T)". When the drone confirms a successful take-off, the panel switches to
**Flying - controls enabled** by itself and every flight key becomes active. While a move is running the
panel shows **Moving** and extra key presses are ignored, so commands never pile up.

Holding a key down sends **one** command only.

## Nothing automatic

- **No auto-land.** The app never lands the drone by itself: not on low battery (a warning is shown at 20%),
  not when you change pages, not when the app closes. Only **G** or **X X** land it.
  You cannot disconnect (N N) while flying - land first.
  *Note:* the Tello firmware itself lands if it receives no command for 15 seconds. The app sends a
  keep-alive every 5 seconds while connected, so this does not happen during normal use, but it will
  happen if you close the app or lose Wi-Fi while flying. This firmware behaviour cannot be switched off.
- **No auto-start of flight.** The drone never takes off or moves by itself (there is no automatic patrol);
  it only moves when you press a key. Object detection starts together with the video when you press **C**;
  press **I** to pause or resume it.

## Evidence photos

Every detected class is saved as an annotated photo (bounding boxes, class names and confidence):

```
evidence\
  evidence_log.csv                          time, location, class, count, confidence, source, file
  Marina_Reservoir\
    Plastic\        20261119_141502_Drone_87.jpg
    Algal_Bloom\    20261119_141530_Drone_74.jpg
    Clean_Water\    20261119_141611_Image_91.jpg
```

- **Drone feed:** a photo is saved when a class is confirmed (5 of the last 8 frames), then at most once every
  6 seconds per class (`EVIDENCE_COOLDOWN_SECONDS` in `config.py`) so the folder does not fill up.
- **Image upload:** one photo per detected class, saved once per image.
- The file name ends with the highest confidence, e.g. `_87` = 87%.

## Other features

**Dot-Matrix Display.** While detection is on, the top LED and 8x8 matrix follow the confirmed water status:
red with an exclamation mark for any alert, green with a tick for clean water, blue with a circle while scanning.
They switch off when detection is off.

**Distance Sensing Module.** The front ToF sensor is read twice per second (range about 120 cm). The distance
is shown in the telemetry row (red when an obstacle is within 50 cm), and a forward move is blocked if it would
bring the drone closer than 50 cm to an obstacle.

**Take-off checks** (from your controller script): battery at least 50%, and the drone must be level
(tilted less than 10 degrees). Speed is set to 40 cm/s on connect, and the drone pauses briefly after each
move before accepting the next one.

**Reporting.** Detections are written to the selected location's report every 15 seconds, raise alerts, and
are sent to the mock PUB system, exactly as before.

## Folder structure

```
water_quality_monitor/
|-- app.py                  Entry point and sidebar navigation
|-- config.py               All settings (model, drone, distances, evidence)
|-- requirements.txt
|-- .streamlit/config.toml  Theme colours
|-- core/
|   |-- tello_drone.py      Tello link, video, AI voting, Dot-Matrix, ToF, keyboard moves
|   |-- evidence.py         Evidence photos + evidence_log.csv
|   |-- detector.py         YOLO inference and bounding-box drawing
|   |-- database.py         SQLite schema and queries
|   |-- monitoring.py       Location grouping + time-based aggregation
|   |-- pub_service.py      Mock PUB submissions
|   |-- camera.py           Webcam (test mode only)
|   |-- classification.py   Class names, severity levels
|-- ui/
|   |-- keyboard/index.html Keyboard control panel (custom Streamlit component)
|   |-- keyboard_control.py Python side of the keyboard panel
|   |-- styles.py           CSS
|   |-- components.py       Cards, badges, tables, banners
|-- views/
|   |-- dashboard.py
|   |-- detection.py
|   |-- reports.py
|-- data/                   SQLite database (auto-created)
|-- evidence/               Evidence photos (auto-created)
```

## Testing checklist

1. **Test mode first** (`DRONE_TEST_MODE = True`): press **C**, then **T**. The panel changes to
   "Flying - controls enabled". Press **W**, type `50`, press Enter. Press **M**, type `40`, Enter, then an arrow key.
2. Hold a plastic image to the webcam. After a few frames: "Environmental Alert", and a photo
   appears in `evidence\<location>\Plastic\`.
3. **Real drone** (`DRONE_TEST_MODE = False`): press **C**, check battery and height appear, press **T**.
4. Hold your hand 30 cm in front of the drone and press **W** with `50`: the move is blocked.
5. Press **G** to land, then **N N** to disconnect.
6. **Dashboard** and **Monitoring Reports** show the grouped results per location.

**Reset all data:** stop the app, delete `data\water_quality.db` and the `evidence` folder.

## Troubleshooting

| Problem | Fix |
|---|---|
| Keys do nothing | Click an empty part of the page (not a text box), then try again. |
| "No reply from the Tello" | Join the TELLO-XXXXXX Wi-Fi; turn the drone off and on again. |
| "No video received" | Allow Python through Windows Firewall (UDP 11111). Close other Tello apps. |
| Ports 8890/9000 error | Another program (such as your controller script) is using the drone. Close it. |
| "Drone is tilted" | Put the drone on a flat surface before pressing T. |
| Front Distance "Not available" | The Dot-Matrix & Distance Sensing Module is not attached or not detected. |
| Feed is slow | Raise the confidence threshold or install the CUDA build of PyTorch. |
| "Model weights not found" | Check the path in `config.py`. |
