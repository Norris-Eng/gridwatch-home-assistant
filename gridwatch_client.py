import requests
import time
import datetime
import os
import sys

# ---------------------------------------------------------
# GRIDWATCH v2.1 - VISUAL DASHBOARD CLIENT
# ---------------------------------------------------------

# --- CONFIGURATION (ENV VARS > HARDCODED) ---
# SECURITY BEST PRACTICE: Set these in your OS or .env file.
# Fallback to empty string if not found (it will prompt you).
RAPIDAPI_KEY = os.environ.get("GRIDWATCH_API_KEY", "YOUR_RAPIDAPI_KEY_HERE")
REGION = os.environ.get("GRIDWATCH_REGION", "ERCOT")

# THRESHOLDS
PRICE_CAP = float(os.environ.get("GW_PRICE_CAP", 200.0))
STRESS_CAP = float(os.environ.get("GW_STRESS_CAP", 90.0))
DISPATCH_FLOOR = float(os.environ.get("GW_DISPATCH_FLOOR", 0.0))

# INTERNAL STATE
CURRENT_STATE = "NORMAL"
LAST_STATE_CHANGE = datetime.datetime.now()
COOLDOWN_MINUTES = 15
ACTION_LOG = [] # Store last 5 actions for display

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def log_action(action_type, details=""):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {action_type}: {details}"
    ACTION_LOG.append(entry)
    if len(ACTION_LOG) > 8: ACTION_LOG.pop(0)

def render_dashboard(price, stress, status_msg):
    clear_screen()

    # ANSI Colors
    C_RESET = "\033[0m"
    C_RED = "\033[41m\033[37m"     # Red Background
    C_GREEN = "\033[42m\033[30m"   # Green Background
    C_YELLOW = "\033[43m\033[30m"  # Yellow Background
    C_BLUE = "\033[44m\033[37m"    # Blue Background
    C_BOLD = "\033[1m"

    # Header
    print(f"{C_BOLD}╔══════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_BOLD}║           GRIDWATCH v2.1 // LIVE TELEMETRY           ║{C_RESET}")
    print(f"{C_BOLD}╚══════════════════════════════════════════════════════╝{C_RESET}")
    print(f" Region: {C_BLUE} {REGION} {C_RESET}  |  API Key: ...{RAPIDAPI_KEY[-4:] if len(RAPIDAPI_KEY)>4 else '****'}")
    print("-" * 56)

    # Big Metrics
    p_color = C_RED if price > PRICE_CAP else C_GREEN if price <= DISPATCH_FLOOR else C_RESET
    s_color = C_RED if stress > STRESS_CAP else C_GREEN

    print(f" PRICE:  {p_color} ${price:.2f} / MWh {C_RESET}")
    print(f" STRESS: {s_color} {stress}% Capacity {C_RESET}")
    print("-" * 56)

    # Status Banner
    if CURRENT_STATE == "CURTAILED":
        state_color = C_RED
        state_text = " !! CURTAILMENT ACTIVE !! "
    elif CURRENT_STATE == "DISPATCHED":
        state_color = C_YELLOW
        state_text = " $$ ECONOMIC DISPATCH $$ "
    else:
        state_color = C_GREEN
        state_text = " -- NORMAL OPERATION -- "

    print(f" STATUS: {state_color}{state_text}{C_RESET}")
    print(f" MSG:    {status_msg}")
    print("-" * 56)

    # Action Log
    print(f"{C_BOLD}RECENT ACTIONS:{C_RESET}")
    for log in ACTION_LOG:
        print(f" {log}")
    print("\n(Press Ctrl+C to Quit)")

def perform_action(action_type):
    # REPLACE THIS WITH YOUR HARDWARE CODE (GPIO, ETC)
    log_action("HARDWARE", f"Executing {action_type} sequence...")

def check_grid_logic():
    global CURRENT_STATE, LAST_STATE_CHANGE

    url = "https://gridwatch-us-telemetry.p.rapidapi.com/api/curtailment"
    qs = {"region": REGION, "price_cap": str(PRICE_CAP), "stress_cap": str(STRESS_CAP)}
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "gridwatch-us-telemetry.p.rapidapi.com"}

    try:
        r = requests.get(url, headers=headers, params=qs, timeout=10)
        if r.status_code != 200:
            render_dashboard(0, 0, f"API ERROR {r.status_code}")
            return

        data = r.json()
        price = data['metrics'].get('price_usd', 9999.0) or 9999.0
        stress = data['metrics'].get('utilization_pct', 0)

        status_msg = "Monitoring..."

        # Logic Engine
        if (price > PRICE_CAP) or (stress > STRESS_CAP):
            if CURRENT_STATE != "CURTAILED":
                perform_action('STOP')
                log_action("STATE", f"Normal -> CURTAILED (P:${price} S:{stress}%)")
                CURRENT_STATE = "CURTAILED"
                LAST_STATE_CHANGE = datetime.datetime.now()
            else:
                status_msg = "Waiting for Grid Recovery..."
                LAST_STATE_CHANGE = datetime.datetime.now()

        elif (price <= DISPATCH_FLOOR):
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()
            if CURRENT_STATE == "CURTAILED" and time_since < (COOLDOWN_MINUTES * 60):
                remaining = int((COOLDOWN_MINUTES*60) - time_since)
                status_msg = f"Cooldown Active ({remaining}s)"
            elif CURRENT_STATE != "DISPATCHED":
                perform_action('DISPATCH')
                log_action("STATE", f"Normal -> DISPATCHED (Opportunity Price ${price})")
                CURRENT_STATE = "DISPATCHED"
                LAST_STATE_CHANGE = datetime.datetime.now()

        else: # Normal
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()
            if CURRENT_STATE == "CURTAILED":
                remaining = int((COOLDOWN_MINUTES*60) - time_since)
                if remaining <= 0:
                    perform_action('RESUME')
                    log_action("STATE", "CURTAILED -> Normal")
                    CURRENT_STATE = "NORMAL"
                    LAST_STATE_CHANGE = datetime.datetime.now()
                else:
                    status_msg = f"Cooldown Active ({remaining}s)"
            elif CURRENT_STATE == "DISPATCHED":
                 if time_since > 300:
                     log_action("STATE", "DISPATCHED -> Normal")
                     CURRENT_STATE = "NORMAL"
                     LAST_STATE_CHANGE = datetime.datetime.now()

        render_dashboard(price, stress, status_msg)

    except Exception as e:
        render_dashboard(0, 0, f"EXCEPTION: {str(e)[:20]}")

if __name__ == "__main__":
    if "YOUR_RAPIDAPI_KEY" in RAPIDAPI_KEY:
        print("ERROR: Please set GRIDWATCH_API_KEY environment variable.")
        sys.exit(1)

    while True:
        check_grid_logic()
        time.sleep(300)
