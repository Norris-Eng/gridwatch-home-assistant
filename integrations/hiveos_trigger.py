import requests
import time
import datetime
import os
import sys

# ---------------------------------------------------------
# GRIDWATCH v2.1 - HIVEOS INTEGRATION (SECURE)
# ---------------------------------------------------------

# --- CONFIGURATION (ENV VARS) ---
RAPIDAPI_KEY = os.environ.get("GRIDWATCH_API_KEY", "")
REGION = os.environ.get("GRIDWATCH_REGION", "ERCOT")

# HIVEOS SPECIFIC
HIVE_API_TOKEN = os.environ.get("HIVE_API_TOKEN", "")
HIVE_FARM_ID = os.environ.get("HIVE_FARM_ID", "")
# Expects CSV string: "112233,445566"
_worker_ids_str = os.environ.get("HIVE_WORKER_IDS", "")
HIVE_WORKER_IDS = [int(x.strip()) for x in _worker_ids_str.split(',')] if _worker_ids_str else []

# THRESHOLDS
PRICE_CAP = float(os.environ.get("GW_PRICE_CAP", 200.0))
STRESS_CAP = float(os.environ.get("GW_STRESS_CAP", 90.0))
DISPATCH_FLOOR = float(os.environ.get("GW_DISPATCH_FLOOR", 0.0))

# INTERNAL STATE
CURRENT_STATE = "NORMAL"
LAST_STATE_CHANGE = datetime.datetime.now()
COOLDOWN_MINUTES = 15
SIMULATION_MODE = os.environ.get("GW_SIMULATION_MODE", "False").lower() == "true"

def validate_config():
    errors = []
    if not RAPIDAPI_KEY: errors.append("Missing GRIDWATCH_API_KEY")
    if not HIVE_API_TOKEN: errors.append("Missing HIVE_API_TOKEN")
    if not HIVE_FARM_ID: errors.append("Missing HIVE_FARM_ID")
    if not HIVE_WORKER_IDS: errors.append("Missing HIVE_WORKER_IDS")

    if errors:
        print("\n\033[91m[FATAL] CONFIGURATION ERROR(S):\033[0m")
        for e in errors: print(f" - {e}")
        print("\nPlease set these environment variables before running.")
        sys.exit(1)

# ---------------------------------------------------------
# ACTION HANDLERS
# ---------------------------------------------------------
def hive_command(action):
    """
    Sends commands to HiveOS API.
    action: 'start' (miner start) or 'stop' (miner stop)
    """
    label = "SHUTDOWN" if action == 'stop' else "RESUME"
    print(f"   [ACTION] INITIATING HIVEOS {label} ({len(HIVE_WORKER_IDS)} Workers)...")

    if SIMULATION_MODE:
        print(f"      [SIMULATION] HiveOS '{action}' would be sent to Farm {HIVE_FARM_ID}")
        return

    try:
        url = f"https://api2.hiveos.farm/api/v2/farms/{HIVE_FARM_ID}/workers/command"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {HIVE_API_TOKEN}"
        }

        # HiveOS 'miner' command handles the mining process specifically
        # 'stop' stops hashing, 'start' resumes hashing.
        # (Safer than a full rig reboot/shutdown)
        payload = {
            "worker_ids": HIVE_WORKER_IDS,
            "data": {
                "command": "miner",
                "data": { "action": action }
            }
        }

        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            print(f"      \033[92m-> SUCCESS: HiveOS command accepted.\033[0m")
        else:
            print(f"      \033[91m-> FAIL {r.status_code}: {r.text}\033[0m")
    except Exception as e:
        print(f"      \033[91m-> CONNECTION ERROR: {e}\033[0m")

# ---------------------------------------------------------
# LOGIC ENGINE
# ---------------------------------------------------------
def check_grid_logic():
    global CURRENT_STATE, LAST_STATE_CHANGE

    url = "https://gridwatch-us-telemetry.p.rapidapi.com/api/curtailment"
    qs = {"region": REGION, "price_cap": str(PRICE_CAP), "stress_cap": str(STRESS_CAP)}
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "gridwatch-us-telemetry.p.rapidapi.com"}

    try:
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        sys.stdout.write(f"\r[{now_str}] Monitoring {REGION} | State: {CURRENT_STATE} | P: ... ")
        sys.stdout.flush()

        r = requests.get(url, headers=headers, params=qs, timeout=10)
        if r.status_code != 200: return

        data = r.json()
        price = data['metrics'].get('price_usd', 9999.0) or 9999.0
        stress = data['metrics'].get('utilization_pct', 0)

        # 1. CRITICAL
        if (price > PRICE_CAP) or (stress > STRESS_CAP):
            if CURRENT_STATE != "CURTAILED":
                print(f"\n\n[{now_str}] \033[41m\033[37m CRITICAL EVENT \033[0m Price ${price:.2f}")
                hive_command('stop')
                CURRENT_STATE = "CURTAILED"
                LAST_STATE_CHANGE = datetime.datetime.now()
            else:
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 2. DISPATCH
        elif (price <= DISPATCH_FLOOR):
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()
            if CURRENT_STATE == "CURTAILED" and time_since < (COOLDOWN_MINUTES * 60):
                pass # Wait
            elif CURRENT_STATE != "DISPATCHED":
                print(f"\n\n[{now_str}] \033[42m\033[30m DISPATCH EVENT \033[0m Price ${price:.2f}")
                hive_command('start')
                CURRENT_STATE = "DISPATCHED"
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 3. NORMAL
        else:
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()
            if CURRENT_STATE == "CURTAILED":
                remaining = (COOLDOWN_MINUTES * 60) - time_since
                if remaining <= 0:
                    print(f"\n\n[{now_str}] \033[92m RECOVERY \033[0m Resuming Hashing.")
                    hive_command('start')
                    CURRENT_STATE = "NORMAL"
                    LAST_STATE_CHANGE = datetime.datetime.now()
            elif CURRENT_STATE == "DISPATCHED":
                 if time_since > 300:
                     print(f"\n\n[{now_str}] \033[92m STABILIZED \033[0m Price Normalized.")
                     CURRENT_STATE = "NORMAL"
                     LAST_STATE_CHANGE = datetime.datetime.now()

    except Exception as e:
        print(f"\n[EXCEPTION] {e}")

if __name__ == "__main__":
    validate_config()
    print(f"--- GridWatch v2.1 (HiveOS Integration) ---")
    print(f"Region: {REGION}")
    print(f"Stop:   >${PRICE_CAP} or >{STRESS_CAP}%")
    print(f"Farm:   {HIVE_FARM_ID} ({len(HIVE_WORKER_IDS)} Workers)")
    print("-------------------------------------------")
    while True:
        check_grid_logic()
        time.sleep(300)
