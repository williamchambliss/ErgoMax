import os
import json
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
ENCOURAGEMENTS_FILE = os.path.join(BASE_DIR, "encouragements.json")
COACH_FILE = os.path.join(BASE_DIR, "coach_resources.json")

def load_json_file(filepath, default_value=None):
    if default_value is None:
        default_value = {}
    if not os.path.exists(filepath):
        return default_value
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return default_value

def save_json_file(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False

def load_history():
    return load_json_file(HISTORY_FILE, {})

def save_history(history):
    return save_json_file(HISTORY_FILE, history)

def get_default_day_record():
    return {
        "good_alignment_mins": 0.0,
        "active_rest_mins": 0.0,
        "bad_posture_mins": 0.0,
        "sedentary_stretch_mins": 0.0,
        "current_sitting_streak_mins": 0.0, # Helper for calculating max stretch
        "symmetry_ub_l_mins": 0.0,
        "symmetry_ub_r_mins": 0.0,
        "cues_sent": 0,
        "total_correction_speed_secs": 0.0,  # Accumulator to calculate average
        "average_correction_speed_secs": 0.0,
        "breaks_completed": 0,
        "breaks_target": 8,
        "daily_score": 0
    }

def get_day_record(date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    history = load_history()
    if date_str not in history:
        history[date_str] = get_default_day_record()
        save_history(history)
    return history[date_str]

def save_day_record(date_str, record):
    history = load_history()
    history[date_str] = record
    save_history(history)

def load_encouragements():
    return load_json_file(ENCOURAGEMENTS_FILE, {"score_brackets": {}, "comparative": {}, "targeted_feedback": {}})

def load_coach_resources():
    return load_json_file(COACH_FILE, {"desk_stretches": [], "core_activation": [], "ergonomic_setup": [], "micro_routines": []})

def get_historical_chart_data():
    """
    Returns scores for the last 28 days (4 weeks) as list of dicts: [{'day': 'Mon', 'score': 85}, ...]
    If no record exists, score is 0.
    """
    history = load_history()
    chart_data = []
    today = datetime.now()
    
    # Generate dates for the last 28 days
    for i in range(27, -1, -1):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        day_label = target_date.strftime("%a %d") # E.g. "Mon 15"
        
        score = 0
        if date_str in history:
            score = history[date_str].get("daily_score", 0)
            
        chart_data.append({
            "date": date_str,
            "label": day_label,
            "score": score
        })
    return chart_data

def update_daily_score(date_str=None):
    """
    Recalculates the Daily Posture Score (0-100) using:
    Score = 0.6 * ((Good + ActiveRest) / TotalSitting) * 100 + 40 * (CompletedBreaks / TargetBreaks)
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    history = load_history()
    if date_str not in history:
        return 0
        
    rec = history[date_str]
    good = rec.get("good_alignment_mins", 0.0)
    active_rest = rec.get("active_rest_mins", 0.0)
    bad = rec.get("bad_posture_mins", 0.0)
    
    total_sitting = good + active_rest + bad
    
    # Ratio of good posture (good + active rest / total sitting)
    if total_sitting > 0:
        alignment_ratio = (good + active_rest) / total_sitting
    else:
        alignment_ratio = 1.0 # Default if they didn't sit at all
        
    completed_breaks = rec.get("breaks_completed", 0)
    target_breaks = rec.get("breaks_target", 8)
    
    break_ratio = completed_breaks / target_breaks if target_breaks > 0 else 1.0
    if break_ratio > 1.0:
        break_ratio = 1.0
        
    score = (0.6 * alignment_ratio * 100) + (0.4 * break_ratio * 100)
    rec["daily_score"] = round(score)
    
    # Re-calculate average correction speed
    cues = rec.get("cues_sent", 0)
    total_speed = rec.get("total_correction_speed_secs", 0.0)
    if cues > 0:
        rec["average_correction_speed_secs"] = round(total_speed / cues, 1)
    else:
        rec["average_correction_speed_secs"] = 0.0
        
    # Re-calculate symmetry index
    ub_l = rec.get("symmetry_ub_l_mins", 0.0)
    ub_r = rec.get("symmetry_ub_r_mins", 0.0)
    total_ub = ub_l + ub_r
    if total_ub > 0:
        rec["symmetry_index"] = round((ub_l / total_ub) * 100)
    else:
        rec["symmetry_index"] = 50 # Balanced by default
        
    history[date_str] = rec
    save_history(history)
    return rec["daily_score"]
