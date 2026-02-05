import requests
import time
import datetime
import os

# ---------------------------------------------------------
# GRIDWATCH v2.0 - GENERIC CLIENT
# ---------------------------------------------------------

# --- CONFIGURATION ---
RAPIDAPI_KEY = "YOUR_RAPIDAPI_KEY_HERE"
REGION = "ERCOT"

# --- THRESHOLDS ---
PRICE_CAP = 200.0
DISPATCH_FLOOR = 0.0
STRESS_CAP = 90.0

# --- HYSTERESIS ---
COOLDOWN_MINUTES = 15

# --- STATE TRACKING ---
CURRENT_STATE = "NORMAL"
LAST_STATE_CHANGE = datetime.datetime.now()
SIMULATION_MODE = True

# ---------------------------------------------------------
# USER ACTIONS (EDIT THESE)
# ---------------------------------------------------------
def perform_action(action_type):
    """
    action_type: 'STOP', 'RESUME', 'DISPATCH'
    """
    prefix = "[SIMULATION]" if SIMULATION_MODE else "[ACTION]"
    print(f"   {prefix} EXECUTING: {action_type}")

    if SIMULATION_MODE: return

    # --- YOUR CUSTOM LOGIC HERE ---
    if action_type == "STOP":
        # e.g., GPIO.output(18, GPIO.LOW)
        pass
    elif action_type == "RESUME":
        # e.g., GPIO.output(18, GPIO.HIGH)
        pass
    elif action_type == "DISPATCH":
        # e.g., Trigger high-load processes
        pass

# ---------------------------------------------------------
# LOGIC ENGINE
# ---------------------------------------------------------
def check_grid_logic():
    global CURRENT_STATE, LAST_STATE_CHANGE

    url = "https://gridwatch-us-telemetry.p.rapidapi.com/api/curtailment"
    querystring = {"region": REGION, "price_cap": str(PRICE_CAP), "stress_cap": str(STRESS_CAP)}
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "gridwatch-us-telemetry.p.rapidapi.com"}

    try:
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now_str}] Polling {REGION}...", end="\r")

        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code != 200: return

        data = response.json()
        price = data['metrics'].get('price_usd', 9999.0)
        stress = data['metrics'].get('utilization_pct', 0)
        if price is None: price = 9999.0

        # 1. CRITICAL
        if (price > PRICE_CAP) or (stress > STRESS_CAP):
            if CURRENT_STATE != "CURTAILED":
                print(f"\n[{now_str}] [CRITICAL] CRITICAL: Price ${price}")
                perform_action('STOP')
                CURRENT_STATE = "CURTAILED"
                LAST_STATE_CHANGE = datetime.datetime.now()
            else:
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 2. DISPATCH
        elif (price <= DISPATCH_FLOOR):
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()

            if CURRENT_STATE == "CURTAILED" and time_since < (COOLDOWN_MINUTES * 60):
                 print(f"\r[{now_str}] [WAITING] COOLDOWN... ({int((COOLDOWN_MINUTES*60)-time_since)}s)", end="")
            elif CURRENT_STATE != "DISPATCHED":
                print(f"\n[{now_str}] [DISPATCH] OPPORTUNITY: Price ${price}")
                perform_action('DISPATCH')
                CURRENT_STATE = "DISPATCHED"
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 3. NORMAL
        else:
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()
            if CURRENT_STATE == "CURTAILED":
                remaining = (COOLDOWN_MINUTES * 60) - time_since
                if remaining <= 0:
                    print(f"\n[{now_str}] [ OK ] RECOVERY. Resuming.")
                    perform_action('RESUME')
                    CURRENT_STATE = "NORMAL"
                    LAST_STATE_CHANGE = datetime.datetime.now()
            elif CURRENT_STATE == "DISPATCHED":
                 if time_since > 300:
                     print(f"\n[{now_str}] [ OK ] NORMALIZING.")
                     CURRENT_STATE = "NORMAL"
                     LAST_STATE_CHANGE = datetime.datetime.now()

    except Exception as e:
        print(f"\n[EXCEPTION] {e}")

if __name__ == "__main__":
    print(f"--- GridWatch v2.0 (Generic) ---")
    while True:
        check_grid_logic()
        time.sleep(300)
