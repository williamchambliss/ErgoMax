import time
from datetime import datetime
from enum import Enum
import db

class PostureState(Enum):
    GOOD_ALIGNMENT = "Good Alignment"
    ACTIVE_REST = "Active Rest (Forward Lean)"
    SLOUCHED_SHOULDERS = "Slouched Shoulders"
    BOTTOM_FORWARD = "Bottom Too Far Forward"
    LEFT_TILT = "Left-Leaning Tilt"
    RIGHT_TILT = "Right-Leaning Tilt"
    IMPROPER_SITTING = "Improper Sitting"
    AWAY = "Away"

class DifficultyMode(Enum):
    NOVICE = "Novice"          # 90s bad posture limit, 60 min sitting limit
    INTERMEDIATE = "Intermediate"  # 60s bad posture limit, 55 min sitting limit
    ADVANCED = "Advanced"      # 45s bad posture limit, 50 min sitting limit

class PostureLogicEngine:
    def __init__(self, haptic_callback=None, break_callback=None):
        self.haptic_callback = haptic_callback  # Function(command_type) to send BLE commands
        self.break_callback = break_callback    # Function(bool_started) to trigger UI overlays
        
        # Calibration baseline values (raw 0-255)
        self.calibration_baselines = {"L": 0, "MB": 0, "UB_L": 0, "UB_R": 0}
        self.tolerance = 30  # Default raw sensor trigger threshold above calibration

        self.is_calibrated = False
        
        # Calibration wizard variables
        self.calibration_samples = []
        self.is_calibrating = False
        self.calibration_start_time = 0
        
        # State tracking
        self.current_state = PostureState.AWAY
        self.last_active_time = time.time()  # Tracked from mouse/keyboard events
        
        # Timers (in seconds)
        self.bad_posture_duration = 0
        self.continuous_sitting_duration = 0
        self.seconds_since_last_contact = 0
        
        # Standing/Break Mode state
        self.standing_break_active = False
        self.standing_break_duration = 0  # Seconds spent standing during active break
        self.standing_break_target = 180  # Must stand for 3 minutes (180s)
        
        # Haptic correction stats
        self.haptic_triggered_time = None
        
        # Difficulty defaults (starts at Novice)
        self.difficulty = DifficultyMode.NOVICE
        self.bad_posture_limit = 90
        self.sitting_limit = 3600  # 60 minutes
        
        # Load difficulty from db if possible
        self._load_difficulty_from_history()

    def _load_difficulty_from_history(self):
        # Examine history to auto-adapt difficulty:
        # Novice -> Intermediate after 3 consecutive days with score > 75
        # Intermediate -> Advanced after 7 consecutive days with score > 85
        history = db.load_history()
        sorted_dates = sorted(history.keys(), reverse=True)
        
        consec_75 = 0
        consec_85 = 0
        
        for date_str in sorted_dates:
            score = history[date_str].get("daily_score", 0)
            if score > 85:
                consec_85 += 1
                consec_75 += 1
            elif score > 75:
                consec_75 += 1
                consec_85 = 0
            else:
                break
                
        if consec_85 >= 7:
            self.set_difficulty(DifficultyMode.ADVANCED)
        elif consec_75 >= 3:
            self.set_difficulty(DifficultyMode.INTERMEDIATE)
        else:
            self.set_difficulty(DifficultyMode.NOVICE)

    def set_difficulty(self, mode):
        self.difficulty = mode
        if mode == DifficultyMode.NOVICE:
            self.bad_posture_limit = 90
            self.sitting_limit = 3600 # 60 mins
        elif mode == DifficultyMode.INTERMEDIATE:
            self.bad_posture_limit = 60
            self.sitting_limit = 3300 # 55 mins
        elif mode == DifficultyMode.ADVANCED:
            self.bad_posture_limit = 45
            self.sitting_limit = 3000 # 50 mins

    def update_activity_timestamp(self):
        """Called by mouse/keyboard input hooks in main.py"""
        self.last_active_time = time.time()

    def start_calibration(self):
        self.calibration_samples = []
        self.is_calibrating = True
        self.calibration_start_time = time.time()

    def process_calibration_tick(self, packet):
        if not self.is_calibrating:
            return False
            
        elapsed = time.time() - self.calibration_start_time
        if elapsed <= 5.0:
            self.calibration_samples.append(packet)
            return True
        else:
            # Complete calibration: average the samples to find baseline zero
            if len(self.calibration_samples) > 0:
                for key in self.calibration_baselines:
                    vals = [s.get(key, 0) for s in self.calibration_samples]
                    self.calibration_baselines[key] = int(sum(vals) / len(vals))
                self.is_calibrated = True
            self.is_calibrating = False
            return False

    def update(self, packet):
        """
        Processes a sensor data packet (run once per second).
        packet format: {"L": int, "MB": int, "UB_L": int, "UB_R": int}
        """
        # 1. If currently in the calibration wizard, don't update state
        if self.is_calibrating:
            self.process_calibration_tick(packet)
            self.current_state = PostureState.AWAY
            return
            
        # If not calibrated yet, treat everything as AWAY
        if not self.is_calibrated:
            self.current_state = PostureState.AWAY
            return

        # 2. Check which sensors are ACTIVE based on thresholds
        # Active if raw value > calibration baseline + tolerance
        active = {}
        for k in ["L", "MB", "UB_L", "UB_R"]:
            val = packet.get(k, 0)
            base = self.calibration_baselines.get(k, 0)
            active[k] = val > (base + self.tolerance)

        # 3. Classify User State
        has_any_contact = any(active.values())
        user_is_active_on_pc = (time.time() - self.last_active_time) < 10.0 # Active in last 10s
        
        new_state = PostureState.AWAY
        
        if has_any_contact:
            # Sitting in chair
            self.seconds_since_last_contact = 0
            
            # Posture rules
            if active["MB"] and active["L"] and not active["UB_L"] and not active["UB_R"]:
                new_state = PostureState.SLOUCHED_SHOULDERS
            elif not active["L"] and (active["MB"] or active["UB_L"] or active["UB_R"]):
                new_state = PostureState.BOTTOM_FORWARD
            elif active["UB_L"] and not active["UB_R"]:
                new_state = PostureState.LEFT_TILT
            elif active["UB_R"] and not active["UB_L"]:
                new_state = PostureState.RIGHT_TILT
            else:
                # Includes case where L, MB, and both UB sensors are active (Good posture)
                # Or other combinations not flagged as bad
                new_state = PostureState.GOOD_ALIGNMENT
        else:
            # No contact with backrest
            self.seconds_since_last_contact += 1
            
            if user_is_active_on_pc:
                if self.seconds_since_last_contact <= 300: # 5 minutes
                    new_state = PostureState.ACTIVE_REST
                else:
                    new_state = PostureState.IMPROPER_SITTING
            else:
                new_state = PostureState.AWAY

        # 4. Handle State Transitions & Timers
        self._update_timers(new_state, active)
        self.current_state = new_state
        
        # 5. Log metrics to database (every second is 1/60th of a minute)
        self._log_second_to_db(active)

    def _update_timers(self, new_state, active):
        # Standing Break State Machine
        has_any_contact = any(active.values())
        
        if self.standing_break_active:
            if not has_any_contact:
                self.standing_break_duration += 1
                if self.standing_break_duration >= self.standing_break_target:
                    # Break successfully completed!
                    self._complete_standing_break()
            else:
                # User sat back down, reset stand duration
                self.standing_break_duration = 0
            return

        # Regular monitoring
        if has_any_contact:
            # Accumulate continuous sitting time
            self.continuous_sitting_duration += 1
            
            # Check for Standing Break Trigger
            if self.continuous_sitting_duration >= self.sitting_limit:
                self._trigger_standing_break()
                return
        else:
            # If away from chair, we slowly decay sitting duration
            # (must stand for at least 3 minutes to count as a complete break)
            # but if they just step away for a few seconds, it doesn't reset the sitting clock
            pass

        # Bad Posture alerting timer
        is_bad_posture = new_state in [
            PostureState.SLOUCHED_SHOULDERS,
            PostureState.BOTTOM_FORWARD,
            PostureState.LEFT_TILT,
            PostureState.RIGHT_TILT,
            PostureState.IMPROPER_SITTING
        ]

        if is_bad_posture:
            self.bad_posture_duration += 1
            if self.bad_posture_duration >= self.bad_posture_limit:
                self._trigger_haptic_wave()
                # Hold accumulator so we don't spam commands every second
                self.bad_posture_duration = 0 
        else:
            # If posture corrected, log correction speed
            if self.bad_posture_duration > 0 and self.haptic_triggered_time is not None:
                speed = time.time() - self.haptic_triggered_time
                self._log_correction_speed(speed)
                self.haptic_triggered_time = None
            self.bad_posture_duration = 0

    def _trigger_haptic_wave(self):
        self.haptic_triggered_time = time.time()
        # Increment cue counter
        today = datetime.now().strftime("%Y-%m-%d")
        rec = db.get_day_record(today)
        rec["cues_sent"] += 1
        db.save_day_record(today, rec)
        
        if self.haptic_callback:
            self.haptic_callback("WAVE")

    def _trigger_standing_break(self):
        self.standing_break_active = True
        self.standing_break_duration = 0
        
        if self.haptic_callback:
            self.haptic_callback("PULSE_5")
            
        if self.break_callback:
            self.break_callback(True) # Notify UI that break started

    def _complete_standing_break(self):
        self.standing_break_active = False
        self.continuous_sitting_duration = 0
        self.standing_break_duration = 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        rec = db.get_day_record(today)
        rec["breaks_completed"] += 1
        db.save_day_record(today, rec)
        db.update_daily_score(today)
        
        if self.break_callback:
            self.break_callback(False) # Notify UI that break is finished

    def _log_correction_speed(self, speed_seconds):
        today = datetime.now().strftime("%Y-%m-%d")
        rec = db.get_day_record(today)
        rec["total_correction_speed_secs"] += speed_seconds
        db.save_day_record(today, rec)
        db.update_daily_score(today)

    def _log_second_to_db(self, active):
        today = datetime.now().strftime("%Y-%m-%d")
        rec = db.get_day_record(today)
        
        inc = 1.0 / 60.0 # increment of minutes
        
        # Log specific state time
        if self.current_state == PostureState.GOOD_ALIGNMENT:
            rec["good_alignment_mins"] += inc
        elif self.current_state == PostureState.ACTIVE_REST:
            rec["active_rest_mins"] += inc
        elif self.current_state in [
            PostureState.SLOUCHED_SHOULDERS,
            PostureState.BOTTOM_FORWARD,
            PostureState.LEFT_TILT,
            PostureState.RIGHT_TILT,
            PostureState.IMPROPER_SITTING
        ]:
            rec["bad_posture_mins"] += inc
            
        # Track continuous sitting (longest stretch)
        has_any_contact = any(active.values())
        if has_any_contact:
            rec["current_sitting_streak_mins"] += inc
            if rec["current_sitting_streak_mins"] > rec["sedentary_stretch_mins"]:
                rec["sedentary_stretch_mins"] = round(rec["current_sitting_streak_mins"], 1)
        else:
            # If they stand for > 3 minutes, their sitting streak resets
            if self.seconds_since_last_contact >= 180:
                rec["current_sitting_streak_mins"] = 0.0
                self.continuous_sitting_duration = 0
                
        # Track shoulder symmetry index minutes
        if active["UB_L"]:
            rec["symmetry_ub_l_mins"] += inc
        if active["UB_R"]:
            rec["symmetry_ub_r_mins"] += inc
            
        db.save_day_record(today, rec)
        db.update_daily_score(today)
