import requests
import time
import datetime
import urllib3
import os
from proxmoxer import ProxmoxAPI

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------
# GRIDWATCH v2.0 - PROXMOX "SMART FLEET" CONTROLLER
# ---------------------------------------------------------

# --- USER CONFIGURATION (EDIT THIS) ---
RAPIDAPI_KEY = "YOUR_RAPIDAPI_KEY_HERE"
REGION = "ERCOT"  # Options: PJM, MISO, SPP, NYISO, ISONE, CAISO, ERCOT

# THRESHOLDS
PRICE_CAP = 200.0       # STOP if Price > $200/MWh
STRESS_CAP = 90.0       # STOP if Grid Stress > 90%
DISPATCH_FLOOR = 0.0    # START if Price <= $0/MWh (Negative/Free)

# HYSTERESIS
COOLDOWN_MINUTES = 15   # Time grid must be safe before auto-resume

# PROXMOX CONFIG
# TIP: Add the tag 'gridwatch' to any VM or LXC in Proxmox to control it.
PROXMOX_ENABLED = True
PROXMOX_HOST = "192.168.1.X"
PROXMOX_USER = "root@pam"
PROXMOX_PASSWORD = "YOUR_PASSWORD"
PROXMOX_TARGET_TAG = "gridwatch"

# --- INTERNAL STATE (DO NOT EDIT) ---
CURRENT_STATE = "NORMAL"
LAST_STATE_CHANGE = datetime.datetime.now()
SIMULATION_MODE = False  # Set to True to test without actually stopping VMs

# ---------------------------------------------------------
# PROXMOX HANDLERS
# ---------------------------------------------------------
def get_proxmox():
    try:
        return ProxmoxAPI(PROXMOX_HOST, user=PROXMOX_USER, password=PROXMOX_PASSWORD, verify_ssl=False)
    except Exception as e:
        print(f"!! Proxmox Connection Failed: {e}")
        return None

def set_fleet_state(target_action):
    """
    target_action: 'stopped' (Shutdown) or 'running' (Start)
    """
    if not PROXMOX_ENABLED: return

    label = "SHUTDOWN" if target_action == 'stopped' else "RESUME/START"
    prefix = "[SIMULATION]" if SIMULATION_MODE else "[ACTION]"
    print(f"   {prefix} EXECUTING FLEET {label} (Tag: {PROXMOX_TARGET_TAG})")

    if SIMULATION_MODE: return

    pve = get_proxmox()
    if not pve: return

    # Iterate all nodes in the cluster
    for node in pve.nodes.get():
        node_name = node['node']
        try:
            # 1. Scan QEMU (VMs)
            for vm in pve.nodes(node_name).qemu.get():
                if PROXMOX_TARGET_TAG in vm.get('tags', ''):
                    handle_resource(pve, node_name, vm['vmid'], 'qemu', vm['status'], target_action)

            # 2. Scan LXC (Containers)
            for lxc in pve.nodes(node_name).lxc.get():
                if PROXMOX_TARGET_TAG in lxc.get('tags', ''):
                    handle_resource(pve, node_name, lxc['vmid'], 'lxc', lxc['status'], target_action)
        except Exception as e:
            print(f"   !! Error scanning node {node_name}: {e}")

def handle_resource(pve, node, vmid, r_type, current_status, target_status):
    try:
        if target_status == 'stopped' and current_status == 'running':
            print(f"      - Stopping {r_type.upper()} {vmid}...")
            getattr(pve.nodes(node), r_type)(vmid).status.shutdown.post()

        elif target_status == 'running' and current_status == 'stopped':
            print(f"      - Starting {r_type.upper()} {vmid}...")
            getattr(pve.nodes(node), r_type)(vmid).status.start.post()

        else:
            # No action needed (already in desired state)
            pass
    except Exception as e:
        print(f"      !! Failed to control {vmid}: {e}")

# ---------------------------------------------------------
# LOGIC ENGINE
# ---------------------------------------------------------
def check_grid_logic():
    global CURRENT_STATE, LAST_STATE_CHANGE

    url = "https://gridwatch-us-telemetry.p.rapidapi.com/api/curtailment"
    # Pass caps to the API so it can validate the logic too
    querystring = {"region": REGION, "price_cap": str(PRICE_CAP), "stress_cap": str(STRESS_CAP)}
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "gridwatch-us-telemetry.p.rapidapi.com"}

    try:
        now_str = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now_str}] Polling {REGION}...", end="\r")

        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code != 200:
            print(f"[{now_str}] API Error: {response.status_code}")
            return

        data = response.json()
        price = data['metrics'].get('price_usd', 9999.0)
        stress = data['metrics'].get('utilization_pct', 0)

        # FAIL-SAFE: If price is missing, assume worst case (9999) to trigger safety stop
        if price is None: price = 9999.0

        # --- STATE MACHINE ---

        # 1. CRITICAL (Safety Stop)
        if (price > PRICE_CAP) or (stress > STRESS_CAP):
            if CURRENT_STATE != "CURTAILED":
                print(f"\n[{now_str}] [CRITICAL] Price ${price} | Stress {stress}%")
                set_fleet_state('stopped')
                CURRENT_STATE = "CURTAILED"
                LAST_STATE_CHANGE = datetime.datetime.now()
            else:
                LAST_STATE_CHANGE = datetime.datetime.now() # Reset timer if still bad

        # 2. DISPATCH (Opportunity Start)
        elif (price <= DISPATCH_FLOOR):
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()

            if CURRENT_STATE == "CURTAILED" and time_since < (COOLDOWN_MINUTES * 60):
                remaining = int((COOLDOWN_MINUTES*60) - time_since)
                print(f"\r[{now_str}] [WAITING] COOLDOWN... ({remaining}s remaining)", end="")

            elif CURRENT_STATE != "DISPATCHED":
                print(f"\n[{now_str}] [DISPATCH] OPPORTUNITY: Price ${price}")
                set_fleet_state('running')
                CURRENT_STATE = "DISPATCHED"
                LAST_STATE_CHANGE = datetime.datetime.now()

        # 3. NORMAL (Recovery)
        else:
            time_since = (datetime.datetime.now() - LAST_STATE_CHANGE).total_seconds()

            if CURRENT_STATE == "CURTAILED":
                remaining = int((COOLDOWN_MINUTES*60) - time_since)
                if remaining <= 0:
                    print(f"\n[{now_str}] [RECOVERY] Grid Normal. Resuming Fleet.")
                    set_fleet_state('running')
                    CURRENT_STATE = "NORMAL"
                    LAST_STATE_CHANGE = datetime.datetime.now()
                else:
                    print(f"\r[{now_str}] [WAITING] COOLDOWN... ({remaining}s remaining)", end="")

            elif CURRENT_STATE == "DISPATCHED":
                 # If price rises above floor but is still safe, keep running (Normal)
                 if time_since > 300: # Debounce 5 mins
                     print(f"\n[{now_str}] [STABLE] Price Normalized.")
                     CURRENT_STATE = "NORMAL"
                     LAST_STATE_CHANGE = datetime.datetime.now()

    except Exception as e:
        print(f"\n[EXCEPTION] {e}")

if __name__ == "__main__":
    print(f"--- GridWatch v2.0 (Proxmox Controller) ---")
    print(f"Monitoring: {REGION} | Tag: '{PROXMOX_TARGET_TAG}'")
    print(f"Stop > ${PRICE_CAP} | Dispatch < ${DISPATCH_FLOOR}")
    while True:
        check_grid_logic()
        time.sleep(300) # Poll every 5 minutes
