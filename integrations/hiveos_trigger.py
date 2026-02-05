import requests
import time
import datetime
import os

# ---------------------------------------------------------
# GRIDWATCH v2.0 - HIVEOS INTEGRATION
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

# --- HIVEOS CONFIGURATION ---
HIVE_ENABLED = True
HIVE_TOKEN = "YOUR_HIVE_API_TOKEN"
HIVE_FARM_ID = 123456
HIVE_WORKER_IDS = [112233, 445566]

# --- STATE TRACKING ---
CURRENT_STATE = "NORMAL"
LAST_STATE_CHANGE = datetime.datetime.now()

SIMULATION_MODE = True

# ---------------------------------------------------------
# ACTION HANDLERS
# ---------------------------------------------------------
def hive_command(action):
    """
    Sends commands to HiveOS API.
    action: 'start' or 'stop'
    """
    if not HIVE_ENABLED: return

    print(f"   [ACTION] HIVEOS COMMAND: {action.upper()}...")

    if SIMULATION_MODE:
        print(f"      [SIMULATION] HiveOS '{action}' would execute.")
        return

    try:
        url = f"https://api2.hiveos.farm/api/v2/farms/{HIVE_FARM_ID}/workers/command"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {HIVE_TOKEN}"
        }
        payload = {
            "worker_ids": HIVE_WORKER_IDS,
            "data": {
                "command": "miner",
                "data": { "action": action }
            }
        }
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            print(f"      -> HiveOS: {action} sent.")
        else:
            print(f"      -> HiveOS Error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"      -> Connection Error: {e}")

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
                hive_command('stop')
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
                hive_command('start')
                CURRENT_STATE = "DISPATCHED"
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 3. NORMAL
        else:
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()
            if CURRENT_STATE == "CURTAILED":
                remaining = (COOLDOWN_MINUTES * 60) - time_since
                if remaining <= 0:
                    print(f"\n[{now_str}] [ OK ] RECOVERY. Resuming.")
                    hive_command('start')
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
    print(f"--- GridWatch v2.0 (HiveOS) ---")
    while True:
        check_grid_logic()
        time.sleep(300)
