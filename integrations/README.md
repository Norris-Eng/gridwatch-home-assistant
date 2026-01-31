# GridWatch Controller: Proxmox & Integrations

![Version](https://img.shields.io/badge/version-1.1-brightgreen)
![Python](https://img.shields.io/badge/python-3.9+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A robust, autonomous grid logic controller for **Homelabs (Proxmox), Bitcoin Mining, and High-Performance Computing.**

[Live Dashboard](https://gridwatch.live/)

This client interfaces with the **GridWatch API** to monitor real-time power grid conditions (LMP Settlements, Stress Index) across US ISOs (ERCOT, PJM, SPP, NYISO, MISO, CAISO and ISONE). It automatically curtails power during volatility and crucially **safely restores power** when conditions normalize. [Get API Key Here](https://rapidapi.com/cnorris1316/api/gridwatch-us-telemetry)

## What's New in v1.1: "Smart Resume"
* **Auto-Resume (Smart Recovery):** The script no longer requires human intervention to restart. It detects when pricing returns to safe levels and automatically sends "Resume" commands to your fleet.
* **15-Minute Hardware Debounce:** To protect Power Supply Units (PSUs) and sensitive compute hardware from rapid cycling (flapping), the grid must remain in a "Normal" state for a defined cooldown period before a restart is authorized.
* **State Awareness:** The client tracks local state to prevent API spam. It will not send repeated "Stop" commands to a facility that is already curtailed.

---

## Features
* **Ultra-Low Latency:** Polls 5-minute settlement intervals with <50ms API response time.
* **Multi-ISO Support:** Native support for ERCOT, PJM, NYISO, MISO, SPP, CAISO and ISONE.
* **Agnostic Integration:**
    * **Foreman / HiveOS:** Native handlers for mining fleet management.
    * **Proxmox (AI/HPC):** Graceful shutdown (ACPI) signals to protect filesystem integrity during power events.
    * **Webhooks / SSH:** Generic triggers for Building Management Systems (BMS) or custom SCADA.
    * **Local Shell Scripts:** Direct GPIO/PDU control for homelabs.

---

## Logic Flow (v1.1)

The client operates on a continuous loop (5-minute polling interval):

1.  **Poll GridWatch API:** Retrieves latest LMP and Grid Stress metrics.
2.  **Evaluate Thresholds:** Compares current price/stress index against your `PRICE_CAP` and/or `STRESS_CAP`.
3.  **Action Decision:**
    * **🔴 CRITICAL EVENT:** If Price > Cap and/or Stress > Cap:
        * *Action:* Send **STOP** command immediately.
        * *State:* Mark facility as `CURTAILED`.
    * **🟢 RECOVERY EVENT:** If Price < Cap and/or Stress < Cap:
        * *Check:* Has the grid been normal for `COOLDOWN_MINUTES`?
        * *Action:* If YES, send **START/RESUME** command.
        * *State:* Mark facility as `RUNNING`.

---

## Configuration

This client is designed as a **standalone script** for maximum reliability. You configure it by editing the variables at the top of the `.py` file directly.

### Standard Setup
Open `gridwatch_client.py` and edit the **Configuration** section:

```python
# --- CONFIGURATION ---
RAPIDAPI_KEY = "YOUR_RAPIDAPI_KEY_HERE"  # Get this from RapidAPI
REGION = "ERCOT"       # Options: PJM, MISO, ERCOT, SPP, NYISO, ISONE, CAISO

# Safety Thresholds
PRICE_CAP = 200        # Shut down if price > $200/MWh
STRESS_CAP = 90        # Shut down if grid stress > 90%
COOLDOWN_MINUTES = 15  # Minutes grid must be NORMAL before resuming
```

### Enterprise Integrations
If you use a management platform, use the specific script found in the `integrations/` folder.

#### 1. Foreman Users (Miners)
Use `integrations/foreman_trigger.py`:
```python
FOREMAN_ENABLED = True
FOREMAN_API_TOKEN = "YOUR_FOREMAN_TOKEN"
FOREMAN_MINER_IDS = [123, 456] # List of Miner IDs to control
```

#### 2. HiveOS Users (Miners)
Use `integrations/hiveos_trigger.py`:
```python
HIVE_ENABLED = True
HIVE_TOKEN = "YOUR_HIVE_API_TOKEN"
HIVE_FARM_ID = 123456
HIVE_WORKER_IDS = [112233, 445566]
```

#### 3. Proxmox Users (AI / HPC)
Use `integrations/proxmox_trigger.py`.
*Note: This executes a "Graceful Shutdown" (SIGTERM) to prevent data corruption.*
```python
PROXMOX_ENABLED = True
PROXMOX_HOST = "192.168.1.X"      # IP of Proxmox Server
PROXMOX_USER = "root@pam"
PROXMOX_PASSWORD = "YOUR_PASSWORD"
PROXMOX_NODE = "pve"              # Node name
TARGET_VMS = [100, 101, 102]      # List of VM IDs to manage
```

---

## Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/Norris-Eng/gridwatch-home-assistant](https://github.com/Norris-Eng/gridwatch-home-assistant)
   cd gridwatch-home-assistant
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the script:**
   Open the script matching your use case (e.g., `gridwatch_client.py` or `integrations/proxmox_trigger.py`) in a text editor and paste your API keys.

4. **Run the client:**
   ```bash
   # For generic usage:
   python gridwatch_client.py

   # For Foreman users:
   python integrations/foreman_trigger.py

   # For Proxmox users:
   python integrations/proxmox_trigger.py
   ```

---

## Disclaimer
**Use at your own risk.** This software is designed to automate load shedding based on public telemetry. The author handles no liability for lost revenue, hardware damage, or failed curtailment events due to network connectivity issues or API changes. Always test with a single unit before deploying to a full facility.
