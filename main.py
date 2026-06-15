import os
import sys
import time
import winreg
import threading
import webview
from plyer import notification
from PIL import Image, ImageDraw

# Import local modules
import db
import logic
from ble_manager import BLEManager
from mock_ble import MockBLEManager

# DEV TOGGLE: Set to True to test without physical Arduino BLE. Set to False to use physical Arduino BLE
MOCK_BLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

# Global variables
window = None
ble_manager = None
logic_engine = None
tray_icon = None
app_is_running = True
window_is_visible = True


def get_tray_image():
    logo_path = os.path.join(BASE_DIR, "gui", "logo.png")
    if os.path.exists(logo_path):
        try:
            image = Image.open(logo_path)
            return image.resize((64, 64))
        except Exception as e:
            print(f"Error loading logo.png for tray: {e}")
            
    # Generate a simple 64x64 icon fallback (Teal Circle)
    image = Image.new('RGB', (64, 64), (15, 30, 45))
    draw = ImageDraw.Draw(image)
    draw.ellipse([8, 8, 56, 56], fill=(0, 168, 150), outline=(255, 255, 255), width=2)
    return image

# Windows registry startup utility
def set_startup(enabled):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "PostureMax"
    executable = sys.executable
    cmd = f'"{executable}" "{os.path.join(BASE_DIR, "main.py")}"'
    
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Error setting registry startup: {e}")

# Activity Hook via pynput to determine if user is on PC
def start_activity_listener(engine):
    from pynput import mouse, keyboard
    
    def on_activity(*args):
        engine.update_activity_timestamp()

    mouse_listener = mouse.Listener(on_move=on_activity, on_click=on_activity, on_scroll=on_activity)
    keyboard_listener = keyboard.Listener(on_press=on_activity)
    
    mouse_listener.start()
    keyboard_listener.start()

# JS to Python API Bridge
class JsApi:
    def __init__(self):
        self.settings = db.load_json_file(SETTINGS_FILE, {
            "startup_launch": True,
            "haptic_intensity": 128,
            "haptic_mode": "wave"
        })

    def get_settings(self):
        return self.settings

    def calibrate_baseline(self):
        if logic_engine:
            logic_engine.start_calibration()
            return "Calibration started"
        return "Logic engine not ready"

    def set_haptic_intensity(self, val):
        val = int(val)
        self.settings["haptic_intensity"] = val
        db.save_json_file(SETTINGS_FILE, self.settings)
        # Send a brief 0.2s test pulse so the user feels the adjustment
        def test_pulse():
            if ble_manager:
                ble_manager.send_haptic_command(bytes([val, val, val, val]))
                time.sleep(0.2)
                ble_manager.send_haptic_command(bytes([0, 0, 0, 0]))
        threading.Thread(target=test_pulse, daemon=True).start()
        return "Intensity set"


    def set_haptic_mode(self, mode):
        self.settings["haptic_mode"] = mode
        db.save_json_file(SETTINGS_FILE, self.settings)
        return "Haptic mode set"

    def toggle_startup_setting(self, active):
        self.settings["startup_launch"] = active
        db.save_json_file(SETTINGS_FILE, self.settings)
        set_startup(active)
        return f"Startup set to {active}"

    def get_coach_resources(self):
        return db.load_coach_resources()

    def get_historical_chart_data(self):
        return db.get_historical_chart_data()

    def get_dashboard_data(self):
        if not logic_engine or not ble_manager:
            return None

        today = datetime_str()
        rec = db.get_day_record(today)
        
        # Pull dynamic encouragement message
        score = rec.get("daily_score", 0)
        enc_msg = get_encouragement_message(score)

        return {
            "ble_status": ble_manager.connection_status,
            "current_state": logic_engine.current_state.value,
            "difficulty_mode": logic_engine.difficulty.value,
            "daily_score": score,
            "encouragement_msg": enc_msg,
            "sitting_seconds_elapsed": logic_engine.continuous_sitting_duration if not logic_engine.standing_break_active else logic_engine.standing_break_duration,
            "sitting_limit_seconds": logic_engine.sitting_limit,
            "is_standing_break": logic_engine.standing_break_active,
            "active_sensors": {
                "L": logic_engine.calibration_baselines["L"] + logic_engine.tolerance < last_sensor_packet.get("L", 0) if logic_engine.is_calibrated else False,
                "MB": logic_engine.calibration_baselines["MB"] + logic_engine.tolerance < last_sensor_packet.get("MB", 0) if logic_engine.is_calibrated else False,
                "UB_L": logic_engine.calibration_baselines["UB_L"] + logic_engine.tolerance < last_sensor_packet.get("UB_L", 0) if logic_engine.is_calibrated else False,
                "UB_R": logic_engine.calibration_baselines["UB_R"] + logic_engine.tolerance < last_sensor_packet.get("UB_R", 0) if logic_engine.is_calibrated else False
            },
            "history_stats": {
                "sedentary_stretch_mins": rec.get("sedentary_stretch_mins", 0.0),
                "symmetry_index": rec.get("symmetry_index", 50),
                "average_correction_speed_secs": rec.get("average_correction_speed_secs", 0.0)
            }
        }

# Helper to format date
def datetime_str():
    return time.strftime("%Y-%m-%d")

# Select dynamic text from encouragements DB
def get_encouragement_message(score):
    enc_db = db.load_encouragements()
    brackets = enc_db.get("score_brackets", {})
    
    if score >= 85:
        messages = brackets.get("excellent", {}).get("messages", [])
    elif score >= 70:
        messages = brackets.get("good", {}).get("messages", [])
    elif score >= 50:
        messages = brackets.get("moderate", {}).get("messages", [])
    else:
        messages = brackets.get("needs_work", {}).get("messages", [])

    if messages:
        # Choose message based on day index to cycle them
        day_idx = int(time.time() / 86400) % len(messages)
        return messages[day_idx]
    return "Keep maintaining a healthy spinal posture."

# Sensor notification callback
last_sensor_packet = {"L": 0, "MB": 0, "UB_L": 0, "UB_R": 0}
def handle_sensor_data(packet):
    global last_sensor_packet
    last_sensor_packet = packet
    if logic_engine:
        logic_engine.update(packet)

# BLE status update callback
def handle_ble_status(status):
    print(f"[BLE Status]: {status}")
    if status.startswith("Disconnected"):
        # Post desktop notification alert
        notification.notify(
            title="PostureMax Connection Alert",
            message="Ergomax_Node disconnected. Reposition chair and reconnect.",
            app_name="PostureMax",
            timeout=5
        )

def _execute_haptic_sequence(cmd_type, intensity, mode):
    if not ble_manager:
        return
    try:
        if cmd_type == "WAVE":
            if mode == "wave":
                # L -> MB -> UB cascade
                # Step 1: L only
                ble_manager.send_haptic_command(bytes([intensity, 0, 0, 0]))
                time.sleep(0.4)
                # Step 2: MB only
                ble_manager.send_haptic_command(bytes([0, intensity, 0, 0]))
                time.sleep(0.4)
                # Step 3: UB_L and UB_R
                ble_manager.send_haptic_command(bytes([0, 0, intensity, intensity]))
                time.sleep(0.4)
                # Step 4: Turn off
                ble_manager.send_haptic_command(bytes([0, 0, 0, 0]))
            else:
                # Standard pulse mode: turn on all zones for 3 seconds
                ble_manager.send_haptic_command(bytes([intensity, intensity, intensity, intensity]))
                time.sleep(3.0)
                ble_manager.send_haptic_command(bytes([0, 0, 0, 0]))
        elif cmd_type == "PULSE_5":
            # Pulse break reminder: pulse all haptics on and off for 5 seconds
            for _ in range(3):
                ble_manager.send_haptic_command(bytes([intensity, intensity, intensity, intensity]))
                time.sleep(1.0)
                ble_manager.send_haptic_command(bytes([0, 0, 0, 0]))
                time.sleep(0.6)
    except Exception as e:
        print(f"Error in haptic sequence execution: {e}")

# Logic engine haptic callbacks
def trigger_haptic_output(cmd_type):
    api = JsApi()
    intensity = int(api.settings.get("haptic_intensity", 128))
    mode = api.settings.get("haptic_mode", "wave")
    # Execute asynchronously on a separate thread to prevent GUI lockup
    t = threading.Thread(target=_execute_haptic_sequence, args=(cmd_type, intensity, mode), daemon=True)
    t.start()


def trigger_break_overlay(started):
    pass # Managed automatically by web polling JS loop

# System Tray Lifecycle thread
def run_system_tray():
    import pystray
    global tray_icon
    
    def on_tray_action(icon, item):
        global window, window_is_visible
        if str(item) == "Open":
            if window:
                window.show()
                window.restore()
                window_is_visible = True

        elif str(item) == "Calibrate":
            if logic_engine:
                logic_engine.start_calibration()
        elif str(item) == "Exit":
            exit_application()

    menu = pystray.Menu(
        pystray.MenuItem("Open", on_tray_action),
        pystray.MenuItem("Calibrate", on_tray_action),
        pystray.MenuItem("Exit", on_tray_action)
    )
    
    tray_icon = pystray.Icon("PostureMax", get_tray_image(), "PostureMax Companion", menu)
    tray_icon.run()

def exit_application():
    global app_is_running, ble_manager, tray_icon
    app_is_running = False
    
    print("Exiting application...")
    if ble_manager:
        ble_manager.stop()
    if tray_icon:
        tray_icon.stop()
        
    # Standard exit
    os._exit(0)

# Window minimize hijack
def on_closed():
    global window_is_visible
    
    # If close is requested when the window is already hidden, this is a Ctrl+C exit signal
    if not window_is_visible:
        print("\nClose event received while window hidden (likely Ctrl+C). Exiting.")
        exit_application()
        return True

    # If app is running, hide window and keep backend alive
    if app_is_running:
        print("Closing window: hiding to system tray.")
        window_is_visible = False
        window.hide()
        notification.notify(
            title="PostureMax Minimized",
            message="PostureMax is running in your system tray to monitor your spine.",
            app_name="PostureMax",
            timeout=3
        )
        return False # Prevents standard process termination


def main():
    global ble_manager, logic_engine, window
    
    # Register Ctrl+C signal handler
    import signal
    def sigint_handler(sig, frame):
        print("\nSIGINT (Ctrl+C) detected, shutting down...")
        exit_application()
    signal.signal(signal.SIGINT, sigint_handler)
    
    # 1. Start logic engine
    logic_engine = logic.PostureLogicEngine(
        haptic_callback=trigger_haptic_output,
        break_callback=trigger_break_overlay
    )
    
    # 2. Start pynput activity listeners
    start_activity_listener(logic_engine)
    
    # 3. Connect to BLE (Mock or Real)
    if MOCK_BLE:
        ble_manager = MockBLEManager(handle_sensor_data, handle_ble_status)
    else:
        ble_manager = BLEManager(handle_sensor_data, handle_ble_status)
    ble_manager.start()
    
    # 4. Start system tray background thread
    tray_thread = threading.Thread(target=run_system_tray, daemon=True)
    tray_thread.start()
    
    # 5. Initialize GUI window
    api = JsApi()
    index_path = os.path.join(BASE_DIR, "gui", "index.html")
    
    window = webview.create_window(
        "PostureMax Companion",
        index_path,
        js_api=api,
        width=1024,
        height=720,
        min_size=(900, 600),
        background_color='#F0F4F8'
    )

    
    # Handle closing callback to hijack close -> minimize to tray
    window.events.closing += on_closed
    
    # Start app thread loop
    webview.start()

if __name__ == "__main__":
    main()
