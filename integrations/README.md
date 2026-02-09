# GridWatch Integrations Guide (v2.1)

This folder contains specialized scripts for **Proxmox**, **Foreman**, and **HiveOS**.

## Security Warning
**NEVER hardcode your API keys into these scripts.**
These scripts are designed to look for credentials in your System Environment Variables. This prevents accidental leakage if you share your code.

---

## 1. Proxmox (Homelab / AI / Rendering)
**File:** `proxmox_trigger.py`
**Method:** Graceful Shutdown (SIGTERM) & Smart Resume.

### Tag-Based Discovery
Instead of editing a list of VM IDs in the code, this script scans your Proxmox node for any VM or LXC container with the tag `gridwatch`.
1.  Log into Proxmox.
2.  Select a VM/Container > **Tags** > Add `gridwatch`.
3.  That's it. The script will now manage that asset.

### Required Environment Variables
| Variable | Description |
| :--- | :--- |
| `PROXMOX_HOST` | IP Address of your Proxmox Node (e.g., `192.168.1.50`) |
| `PROXMOX_USER` | User (e.g., `root@pam`) |
| `PROXMOX_PASSWORD` | Your Proxmox Password |
| `PROXMOX_TARGET_TAG` | (Optional) Defaults to `gridwatch` |

---

## 2. Foreman (ASIC Mining)
**File:** `foreman_trigger.py`
**Method:** API Command (`stop`/`start`).

### Configuration
Set these variables before running:
* `FOREMAN_API_TOKEN`: Your Foreman API Access Token.
* `FOREMAN_MINER_IDS`: A comma-separated list of Miner IDs to control (no spaces).
    * *Example:* `export FOREMAN_MINER_IDS="104,205,309"`

---

## 3. HiveOS (GPU Mining)
**File:** `hiveos_trigger.py`
**Method:** API Command (`miner start`/`miner stop`).

### Configuration
Set these variables before running:
* `HIVE_API_TOKEN`: Your HiveOS Personal API Token.
* `HIVE_FARM_ID`: The ID of your Farm.
* `HIVE_WORKER_IDS`: A comma-separated list of Worker IDs.
    * *Example:* `export HIVE_WORKER_IDS="112233,445566"`

---

## Logic Thresholds (Global)
All scripts respect these global tuning variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GW_PRICE_CAP` | `200.0` | **Shut down** if Grid Price > $200/MWh. |
| `GW_STRESS_CAP` | `90.0` | **Shut down** if Grid Utilization > 90%. |
| `GW_DISPATCH_FLOOR`| `0.0` | **Resume/Start** if Grid Price <= $0.00 (Negative pricing). |
| `GW_SIMULATION_MODE`| `False`| If `True`, prints actions to console but does not execute them. |
