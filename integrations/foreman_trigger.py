import requests
import time
import datetime
import os
import sys

# ---------------------------------------------------------
# GRIDWATCH v2.1 - FOREMAN INTEGRATION (SECURE)
# ---------------------------------------------------------

# --- CONFIGURATION (ENV VARS) ---
# LOAD SECRETS FROM ENVIRONMENT
RAPIDAPI_KEY = os.environ.get("GRIDWATCH_API_KEY", "")
REGION = os.environ.get("GRIDWATCH_REGION", "ERCOT")

# FOREMAN SPECIFIC
FOREMAN_API_TOKEN = os.environ.get("FOREMAN_API_TOKEN", "")
FOREMAN_CLIENT_ID = os.environ.get("FOREMAN_CLIENT_ID", "") # Optional depending on API version
# Expects CSV string in Env Var: "123,456,789"
_miner_ids_str = os.environ.get("FOREMAN_MINER_IDS", "")
FOREMAN_MINER_IDS = [int(x.strip()) for x in _miner_ids_str.split(',')] if _miner_ids_str else []

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
    if not FOREMAN_API_TOKEN: errors.append("Missing FOREMAN_API_TOKEN")
    if not FOREMAN_MINER_IDS: errors.append("Missing FOREMAN_MINER_IDS")

    if errors:
        print("\n\033[91m[FATAL] CONFIGURATION ERROR(S):\033[0m")
        for e in errors: print(f" - {e}")
        print("\nPlease set these environment variables before running.")
        sys.exit(1)

# ---------------------------------------------------------
# ACTION HANDLERS
# ---------------------------------------------------------
def foreman_command(command_type):
    """
    Sends commands to Foreman API.
    command_type: 'stop' or 'start' (mapped to Foreman 'shutdown'/'restart' or custom)
    """
    # MAP GridWatch intent to Foreman specific commands
    # Adjust 'command' payload based on specific Foreman API docs/version
    api_cmd = "shutdown" if command_type == 'stop' else "boot"

    label = "SHUTDOWN" if command_type == 'stop' else "RESUME"
    print(f"   [ACTION] INITIATING FOREMAN {label} ({len(FOREMAN_MINER_IDS)} Miners)...")

    if SIMULATION_MODE:
        print(f"      [SIMULATION] Foreman '{api_cmd}' would be sent to IDs: {FOREMAN_MINER_IDS}")
        return

    try:
        url = "https://api.foreman.mn/api/v2/miners/command"
        headers = {
            "Authorization": f"Token {FOREMAN_API_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "command": api_cmd,
            "miner_ids": FOREMAN_MINER_IDS
        }

        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            print(f"      \033[92m-> SUCCESS: Foreman command accepted.\033[0m")
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
        # Overwrite line to show heartbeat
        sys.stdout.write(f"\r[{now_str}] Monitoring {REGION} | State: {CURRENT_STATE} | P: ... ")
        sys.stdout.flush()

        r = requests.get(url, headers=headers, params=qs, timeout=10)
        if r.status_code != 200:
            return

        data = r.json()
        price = data['metrics'].get('price_usd', 9999.0) or 9999.0
        stress = data['metrics'].get('utilization_pct', 0)

        # 1. CRITICAL (Safety Stop)
        if (price > PRICE_CAP) or (stress > STRESS_CAP):
            if CURRENT_STATE != "CURTAILED":
                print(f"\n\n[{now_str}] \033[41m\033[37m CRITICAL EVENT \033[0m Price ${price:.2f} | Stress {stress}%")
                foreman_command('stop')
                CURRENT_STATE = "CURTAILED"
                LAST_STATE_CHANGE = datetime.datetime.now()
            else:
                LAST_STATE_CHANGE = datetime.datetime.now() # Reset cooldown

        # 2. DISPATCH (Opportunity)
        elif (price <= DISPATCH_FLOOR):
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()

            if CURRENT_STATE == "CURTAILED" and time_since < (COOLDOWN_MINUTES * 60):
                remaining = int((COOLDOWN_MINUTES*60) - time_since)
                # No print needed, status bar handles it

            elif CURRENT_STATE != "DISPATCHED":
                print(f"\n\n[{now_str}] \033[42m\033[30m DISPATCH EVENT \033[0m Price ${price:.2f} <= Floor")
                foreman_command('start')
                CURRENT_STATE = "DISPATCHED"
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 3. NORMAL (Recovery)
        else:
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()

            if CURRENT_STATE == "CURTAILED":
                remaining = (COOLDOWN_MINUTES * 60) - time_since
                if remaining <= 0:
                    print(f"\n\n[{now_str}] \033[92m RECOVERY \033[0m Grid Normalized. Resuming Fleet.")
                    foreman_command('start')
                    CURRENT_STATE = "NORMAL"
                    LAST_STATE_CHANGE = datetime.datetime.now()

            elif CURRENT_STATE == "DISPATCHED":
                 if time_since > 300: # 5 min debounce
                     print(f"\n\n[{now_str}] \033[92m STABILIZED \033[0m Price Normalized.")
                     CURRENT_STATE = "NORMAL"
                     LAST_STATE_CHANGE = datetime.datetime.now()

    except Exception as e:
        print(f"\n[EXCEPTION] {e}")

if __name__ == "__main__":
    validate_config()
    print(f"--- GridWatch v2.1 (Foreman Integration) ---")
    print(f"Region: {REGION}")
    print(f"Stop:   >${PRICE_CAP} or >{STRESS_CAP}%")
    print(f"Start:  <${DISPATCH_FLOOR}")
    print(f"Target: {len(FOREMAN_MINER_IDS)} Miners")
    print("--------------------------------------------")
    while True:
        check_grid_logic()
        time.sleep(300)
