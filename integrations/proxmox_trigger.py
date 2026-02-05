import requests
import time
import datetime
import urllib3
from proxmoxer import ProxmoxAPI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# GRIDWATCH v2.0 - PROXMOX INTEGRATION
# ---------------------------------------------------------

# --- CONFIGURATION ---
RAPIDAPI_KEY = "YOUR_RAPIDAPI_KEY_HERE"
REGION = "ERCOT"

# --- THRESHOLDS ---
PRICE_CAP = 200.0
DISPATCH_FLOOR = 0.0    # START VMs if Price <= $0 (Opportunity Compute)
STRESS_CAP = 90.0

# --- HYSTERESIS ---
COOLDOWN_MINUTES = 15

# --- PROXMOX CONFIGURATION ---
PROXMOX_ENABLED = True
PROXMOX_HOST = "192.168.1.X"
PROXMOX_USER = "root@pam"
PROXMOX_PASSWORD = "YOUR_PASSWORD"
PROXMOX_NODE = "pve"
TARGET_VMS = [100, 101, 102]

# --- STATE TRACKING ---
CURRENT_STATE = "NORMAL"
LAST_STATE_CHANGE = datetime.datetime.now()
SIMULATION_MODE = True

# ---------------------------------------------------------
# PROXMOX ACTIONS
# ---------------------------------------------------------
def get_proxmox():
    try:
        return ProxmoxAPI(PROXMOX_HOST, user=PROXMOX_USER, password=PROXMOX_PASSWORD, verify_ssl=False)
    except: return None

def set_vm_state(target_state):
    """
    target_state: 'stopped' (Shutdown) or 'running' (Start)
    """
    if not PROXMOX_ENABLED: return

    label = "SHUTDOWN" if target_state == 'stopped' else "STARTUP"
    print(f"   [ACTION] PROXMOX {label} SEQUENCE...")

    if SIMULATION_MODE:
        print(f"      [SIMULATION] Proxmox VMs would be set to {target_state}.")
        return

    proxmox = get_proxmox()
    if not proxmox: return

    for vmid in TARGET_VMS:
        try:
            current = proxmox.nodes(PROXMOX_NODE).qemu(vmid).status.current.get().get('status')

            if target_state == 'stopped' and current == 'running':
                proxmox.nodes(PROXMOX_NODE).qemu(vmid).status.shutdown.post()
                print(f"      -> VM {vmid}: Shutdown signal sent.")

            elif target_state == 'running' and current == 'stopped':
                proxmox.nodes(PROXMOX_NODE).qemu(vmid).status.start.post()
                print(f"      -> VM {vmid}: Start signal sent.")

            else:
                print(f"      -> VM {vmid}: Already {current}.")
        except Exception as e:
            print(f"      -> VM {vmid} Error: {e}")

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

        # 1. CRITICAL (Shutdown)
        if (price > PRICE_CAP) or (stress > STRESS_CAP):
            if CURRENT_STATE != "CURTAILED":
                print(f"\n[{now_str}] [CRITICAL] CRITICAL: Price ${price}")
                set_vm_state('stopped')
                CURRENT_STATE = "CURTAILED"
                LAST_STATE_CHANGE = datetime.datetime.now()
            else:
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 2. DISPATCH (Start Compute)
        elif (price <= DISPATCH_FLOOR):
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()

            if CURRENT_STATE == "CURTAILED" and time_since < (COOLDOWN_MINUTES * 60):
                 print(f"\r[{now_str}] [WAITING] COOLDOWN... ({int((COOLDOWN_MINUTES*60)-time_since)}s)", end="")
            elif CURRENT_STATE != "DISPATCHED":
                print(f"\n[{now_str}] [DISPATCH] OPPORTUNITY: Price ${price} <= Floor")
                set_vm_state('running')
                CURRENT_STATE = "DISPATCHED"
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 3. NORMAL (Recovery)
        else:
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()
            if CURRENT_STATE == "CURTAILED":
                remaining = (COOLDOWN_MINUTES * 60) - time_since
                if remaining <= 0:
                    print(f"\n[{now_str}] [ OK ] RECOVERY. Resuming Workloads.")
                    set_vm_state('running')
                    CURRENT_STATE = "NORMAL"
                    LAST_STATE_CHANGE = datetime.datetime.now()
            elif CURRENT_STATE == "DISPATCHED":
                 # If price rises above floor, you can either keep running (Normal)
                 # or stop if you ONLY want to run when cheap.
                 # Standard logic is to Keep running (Normal).
                 if time_since > 300:
                     print(f"\n[{now_str}] [ OK ] NORMALIZING.")
                     CURRENT_STATE = "NORMAL"
                     LAST_STATE_CHANGE = datetime.datetime.now()

    except Exception as e:
        print(f"\n[EXCEPTION] {e}")

if __name__ == "__main__":
    print(f"--- GridWatch v2.0 (Proxmox) ---")
    while True:
        check_grid_logic()
        time.sleep(300)
