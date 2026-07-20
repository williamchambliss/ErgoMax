# PostureMax Desktop Companion Specification & Instructions

This document provides a comprehensive, agent-ready specification for building the **PostureMax Desktop Companion Application**. PostureMax is a Windows-only desktop app that pairs via Bluetooth Low Energy (BLE) with an Arduino-based posture-monitoring kit.

---

## 1. System Overview & Architecture

To achieve a **premium, highly-animated, and modern UI** while retaining direct access to Windows APIs and low-level BLE hardware, the application will use a **hybrid Python-Web architecture**:

```mermaid
graph TD
    subgraph Frontend (HTML/JS/CSS)
        UI[Dashboard UI] -->|Interactions / Config| JS[JS API Bindings]
    end
    subgraph Backend (Python)
        PY[pywebview Bridge] <--> JS
        BLE[Bleak BLE Manager] <-->|Sensor Packets / Haptic Cmds| PY
        ACT[pynput Computer Activity Monitor] -->|User Active Status| LOG[Logic Engine]
        LOG -->|Calibrations & Metrics| DB[Local JSON Database]
        LOG -->|State Updates| PY
    end
    Arduino[Arduino Hardware] <-->|BLE | BLE
```

### Key Libraries
- **GUI Wrapper:** `pywebview` (creates a borderless, modern Windows window hosting a local HTML/JS/CSS page).
- **BLE Communication:** `bleak` (asynchronous Python library for Bluetooth Low Energy).
- **User Activity Detection:** `pynput` (monitors keyboard/mouse movement to detect if the user is at their computer).
- **System Startup:** `winreg` (native Windows library to register the app to run on boot).
- **Local DB:** Python's standard `json` library.

---

## 2. BLE Data Protocol & Hardware Specs

### Sensor Placements
1. **L:** Lower Lumbar (1 pressure sensor)
2. **MB:** Mid Back (1 pressure sensor)
3. **UB_L:** Upper Back / Shoulder Left (1 pressure sensor)
4. **UB_R:** Upper Back / Shoulder Right (1 pressure sensor)
*Each sensor is paired with a adjacent vibration motor.*

### BLE Service & Characteristics
- **Service UUID:** `19B10000-E8F2-537E-4F6C-D104768A1214` (Custom PostureMax Service)
- **Sensor Data Characteristic (Read/Notify):** `19B10001-E8F2-537E-4F6C-D104768A1214`
  - Sends a packet exactly **once per second**.
  - Packet format: Comma-separated raw sensor readings or JSON: `{"L": int, "MB": int, "UB_L": int, "UB_R": int, "batt": int}` (where sensor values are scaled $0-1023$ and battery is percentage).
- **Haptic Command Characteristic (Write):** `19B10002-E8F2-537E-4F6C-D104768A1214`
  - Accepts commands from the desktop app to trigger specific haptic vibration sequences.
  - Commands:
    - `WAVE`: Triggers the sequential bottom-to-top wave (L $\rightarrow$ MB $\rightarrow$ UB).
    - `PULSE_5`: Triggers 5 seconds of pulsing vibration (for Standing/Break Mode alerts).
    - `SET_INTENSITY_[0-255]`: Sets the haptic vibration motor intensity.

---

## 3. Posture Logic Engine & State Machine

The logic engine processes the incoming BLE sensor packet every second and maintains several state variables.

### Calibration
Before evaluating posture, the user runs a **5-second Calibration Wizard** where they sit clear of the chair.
1. The app records the minimum raw pressure value for each sensor ($L_{cal}, MB_{cal}, UB\_L_{cal}, UB\_R_{cal}$) over 5 seconds.
2. An active threshold is defined as: $T_{active} = Base\_Value + Tolerance$.
3. A sensor is considered **Active (pressed)** if $Value_{current} > T_{active}$.

### Posture Classification Matrix

| Upper Back Left (`UB_L`) | Upper Back Right (`UB_R`) | Mid Back (`MB`) | Lower Lumbar (`L`) | Classification | Description / Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Inactive** | **Inactive** | **Active** | **Active** | **Slouched Shoulders** | MB and L have contact, but upper shoulders are hunched forward. |
| **Active / Inactive** | **Active / Inactive** | **Active / Inactive** | **Inactive** | **Bottom Too Far Forward** | Hips slid forward on the seat; lower lumbar lost support. |
| **Active** | **Inactive** | *Any* | *Any* | **Left-Leaning Tilt** | Asymmetric upper back contact (leaning left). |
| **Inactive** | **Active** | *Any* | *Any* | **Right-Leaning Tilt** | Asymmetric upper back contact (leaning right). |
| **Active** | **Active** | **Active** | **Active** | **Good Alignment** | Complete, balanced support across the entire spine. |
| **Inactive** | **Inactive** | **Inactive** | **Inactive** | **No Contact** | See *Computer Activity Logic* below. |

### Computer Activity & Chair Absence Logic
- **Active on Computer:** Detected via `pynput` keyboard/mouse events.
- **State Logic:**
  - If **No Contact** is detected *and* the user is **Active on Computer**:
    - **$\le$ 5 minutes:** Classify as **Active Rest** (good posture; user is sitting upright, engaged, leaning slightly forward without resting on the backrest).
    - **> 5 minutes:** Classify as **Improper Sitting / Away** (user is slouched away from the backrest or sitting in an unsupported posture while typing).
  - If **No Contact** is detected *and* the user is **Inactive on Computer**:
    - Classify as **Away from Desk** (do not penalize, pause all timers).

### Triggering Haptic Feedback
- **Bad Posture Accumulator:** If any bad posture classification (Slouched, Bottom Forward, Left/Right Tilt) persists continuously for **60 seconds**, the app sends the `WAVE` haptic command to the Arduino.
- **Auto-Reset:** Once the user corrects their posture, the bad posture timer resets to 0.

---

## 4. Time Management & Gamification

### Macro rest-periods & Standing/Break Mode
- **Sitting Timer:** Accumulates continuous sitting time (whenever any sensor is **Active**).
- **Standing Trigger:** After **50–60 minutes** of continuous sitting, the app enters **Standing/Break Mode**.
  - Sends a `PULSE_5` haptic command (5 seconds of pulsing vibration).
  - Shows a full-screen break overlay on the desktop with a 5-minute countdown.
  - If the user stands up (all sensors read **Inactive**) for at least 3 minutes, they successfully complete the break.
  - **Gamification Reward:** Award the user $+20$ "Posture Points".

### Adaptive Difficulty Algorithm
To prevent user fatigue, the software adapts to the user's current physical capacity:
- **Novice Mode (Default):** Bad posture requires 90 seconds of continuous deviation before a haptic wave is triggered. Sitting timer target is 60 minutes.
- **Intermediate Mode (Achieved after 3 consecutive days with Posture Score > 75):** Bad posture triggers after 60 seconds. Sitting timer target is 55 minutes.
- **Advanced Mode (Achieved after 7 consecutive days with Posture Score > 85):** Bad posture triggers after 45 seconds. Sitting timer target is 50 minutes.

### Metrics & Analytics (Saved to Local JSON)
Every day, the app writes a summary record to `history.json`:
- **Time-in-Zone Duration:**
  - `good_alignment_mins`: Total minutes spent in Good Alignment.
  - `active_rest_mins`: Total minutes in Active Rest (forward lean under 5 minutes).
  - `bad_posture_mins`: Total minutes spent in Slouched, Bottom Forward, or Tilts.
- **Sedentary Stretch Duration:** The maximum continuous sitting time (in minutes) recorded without a standing break.
- **Symmetry Index:** Calculated as:
  $$\text{Symmetry Index} = \frac{UB\_L_{\text{active\_mins}}}{UB\_L_{\text{active\_mins}} + UB\_R_{\text{active\_mins}}} \times 100$$
  *(Target is 50%. A score of 70% indicates heavy left-leaning).*
- **Haptic Correction Rate:**
  - `cues_sent`: Total number of haptic wave alerts triggered.
  - `average_correction_speed_secs`: Average seconds elapsed between the haptic cue and the user returning to "Good Alignment" or "Active Rest".

### Daily Posture Score Calculation
A single score from $0-100$ is calculated at the end of each day:
$$\text{Daily Posture Score} = 0.6 \times \left(\frac{\text{Good Alignment Mins} + \text{Active Rest Mins}}{\text{Total Sitting Mins}}\right) \times 100 + 40 \times \left(\frac{\text{Completed Breaks}}{\text{Target Breaks}}\right)$$
*This score is used to display dynamic supportive callouts on the dashboard:*
- **Example Encouragement:** *"Great job! Your core engagement was 15% more stable today than yesterday!"*

---

## 5. User Interface Specifications

The app UI will be styled as a clean, highly scannable, interactive dashboard using the following color system:
- **Background:** Ultra-light gray-blue (`#F0F4F8`)
- **Text & Structure:** Deep Slate (`#1A2E40`)
- **Encouragement Cards:** Soft Emerald Green (`#D1E7DD` background, `#0F5132` text)
- **Celebration/Highlights:** Electric Teal (`#00A896`)

### Page 1: Dashboard
- **Daily Posture Score Module:** A large circular progress ring displaying the $0-100$ score, paired with a small text area at the bottom showing dynamic, algorithmic encouragements.
- **Break Timer Display:** A non-intrusive circular countdown timer indicating when the next standing break is due.
- **Haptic Control Panel:**
  - Vibration Intensity Slider ($0-255$).
  - Toggle between "Standard Alerts" (instant haptic cue) and "Cascading Wave" mode.

### Page 2: Posture History
- **Macro Metrics Grid:** Cards showing **Sedentary Stretch**, **Symmetry Index**, and **Haptic Correction Rate**.
- **Historical Chart:** A modern 4-week bar chart where each bar represents the Daily Posture Score for a single day.
- **Educational Motivation Banner:** A rotating text card displaying scientific facts on prolonged sitting risks and the benefits of mobility.

### Page 3: Posture Coach
- **Internal Resource Bank:** Collapsible accordion list containing guidelines for "Desk Stretches", "Core Activation", and "Ergonomic Setup".
- **Actionable Routine Cards:** Interactive 60-second cards (e.g., "Sagittal Pelvic Micro-Tilts", "Scapular Resets") that guide the user with a micro-timer.

### Page 4: How to Set Up & Calibration
- **Sensor Placement Diagram:** An SVG illustration of a seated person's back showing red highlight dots on the upper scapulae, mid back, and lumbar.
- **Calibration Wizard Button:** A large button that launches a 5-second countdown to record sensor baseline zero values.
- **Device Status:** Status indicator showing connection state (Connected/Disconnected) and Arduino battery life percentage.

---

## 6. Development Rules & Windows Integration

- **Boot on Startup:** The Python backend must write to the Windows Registry path:
  `Software\Microsoft\Windows\CurrentVersion\Run` to launch the app minimized to the system tray.
- **BLE Disconnect Alert:** If BLE connection drops, the app must immediately post a standard Windows toast notification (e.g., using `plyer.notification`).
- **No Mock Mode:** BLE connectivity must be real. The app should display a prominent "Search & Connect" overlay until a valid PostureMax BLE peripheral is connected.
