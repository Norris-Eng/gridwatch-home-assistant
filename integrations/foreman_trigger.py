import requests
import time
import datetime
import os

# ---------------------------------------------------------
# GRIDWATCH v2.0 - FOREMAN INTEGRATION
# ---------------------------------------------------------

# --- CONFIGURATION ---
RAPIDAPI_KEY = "YOUR_RAPIDAPI_KEY_HERE"
REGION = "ERCOT"

# --- THRESHOLDS ---
PRICE_CAP = 200.0       # STOP if Price > $200/MWh
DISPATCH_FLOOR = 0.0    # START/BOOST if Price <= $0/MWh
STRESS_CAP = 90.0       # STOP if Grid Stress > 90%

# --- HYSTERESIS ---
COOLDOWN_MINUTES = 15   # Safety cooldown after a Curtailment

# --- FOREMAN CONFIGURATION ---
FOREMAN_ENABLED = True
FOREMAN_API_TOKEN = "YOUR_FOREMAN_TOKEN"
FOREMAN_MINER_IDS = [123, 456]

# --- STATE TRACKING ---
# States: NORMAL, CURTAILED, DISPATCHED
CURRENT_STATE = "NORMAL"
LAST_STATE_CHANGE = datetime.datetime.now()

# Simulation Mode
SIMULATION_MODE = True

# ---------------------------------------------------------
# ACTION HANDLERS
# ---------------------------------------------------------
def foreman_command(command_type):
    """
    Sends commands to Foreman API.
    command_type: 'stop' or 'start'
    """
    if not FOREMAN_ENABLED: return

    action_label = "SHUTDOWN" if command_type == 'stop' else "RESUME/DISPATCH"
    print(f"   [ACTION] INITIATING FOREMAN {action_label}...")

    if SIMULATION_MODE:
        print(f"      [SIMULATION] Foreman '{command_type}' command would be sent.")
        return

    try:
        url = "https://api.foreman.mn/api/v2/miners/command"
        headers = {"Authorization": f"Token {FOREMAN_API_TOKEN}"}
        payload = {"command": command_type, "miner_ids": FOREMAN_MINER_IDS}

        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            print(f"      -> Foreman: {command_type} command sent successfully.")
        else:
            print(f"      -> Foreman Error {r.status_code}: {r.text}")
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
        if response.status_code != 200:
            print(f"\n[ERROR] API {response.status_code}")
            return

        data = response.json()
        price = data['metrics'].get('price_usd')
        stress = data['metrics'].get('utilization_pct', 0)

        # Guard against None
        if price is None: price = 9999.0

        # --- STATE MACHINE ---

        # 1. CRITICAL (Safety Stop)
        if (price > PRICE_CAP) or (stress > STRESS_CAP):
            if CURRENT_STATE != "CURTAILED":
                print(f"\n[{now_str}] [CRITICAL] CRITICAL: Price ${price} | Stress {stress}%")
                foreman_command('stop')
                CURRENT_STATE = "CURTAILED"
                LAST_STATE_CHANGE = datetime.datetime.now()
            else:
                # Reset cooldown timer if conditions remain bad
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 2. DISPATCH (Opportunity Start)
        elif (price <= DISPATCH_FLOOR):
            # If already curtailed, check cooldown first
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()

            if CURRENT_STATE == "CURTAILED" and time_since < (COOLDOWN_MINUTES * 60):
                 print(f"\r[{now_str}] [WAITING] COOLDOWN: Waiting for safety... ({int((COOLDOWN_MINUTES*60)-time_since)}s)", end="")

            elif CURRENT_STATE != "DISPATCHED":
                print(f"\n[{now_str}] [DISPATCH] OPPORTUNITY: Price ${price} <= Floor ${DISPATCH_FLOOR}")
                # Dispatch = Ensure Running (Start)
                foreman_command('start')
                CURRENT_STATE = "DISPATCHED"
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 3. NORMAL (Recovery)
        else:
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()

            if CURRENT_STATE == "CURTAILED":
                remaining = (COOLDOWN_MINUTES * 60) - time_since
                if remaining <= 0:
                    print(f"\n[{now_str}] [ OK ] RECOVERY: Grid Normal. Resuming.")
                    foreman_command('start')
                    CURRENT_STATE = "NORMAL"
                    LAST_STATE_CHANGE = datetime.datetime.now()
                else:
                    print(f"\r[{now_str}] [WAITING] COOLDOWN: {int(remaining)}s remaining...", end="")

            elif CURRENT_STATE == "DISPATCHED":
                 # Price rose above floor, return to normal (Keep running)
                 if time_since > 300: # Debounce 5 mins
                     print(f"\n[{now_str}] [ OK ] NORMALIZING: Price ${price} > Floor.")
                     CURRENT_STATE = "NORMAL"
                     LAST_STATE_CHANGE = datetime.datetime.now()

    except Exception as e:
        print(f"\n[EXCEPTION] {e}")

if __name__ == "__main__":
    print(f"--- GridWatch v2.0 (Foreman) ---")
    print(f"Region: {REGION} | Stop > ${PRICE_CAP} | Dispatch < ${DISPATCH_FLOOR}")
    while True:
        check_grid_logic()
        time.sleep(300)
