# GridWatch Client Tools v2.1

![Version](https://img.shields.io/badge/version-2.1-brightgreen)
![Security](https://img.shields.io/badge/security-env__vars-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Turn your "Dumb" Home or Farm into a Smart Grid Asset.**

[Live Dashboard](https://gridwatch.live/)

This repository contains the client-side tools for the **GridWatch Telemetry System**. These scripts interface with the API to monitor real-time US Power Grid conditions (ERCOT, PJM, MISO, etc.) and automate high-load devices during grid instability or price spikes.

---

## v2.1 Features
* **Visual Dashboard:** The generic client now features a retro-style ANSI terminal dashboard for real-time monitoring.
* **Secure Auth:** **NO HARDCODED KEYS.** All scripts now strictly use Environment Variables for security.
* **Tag-Based Discovery (Proxmox):** No more managing lists of VM IDs. Just tag your VMs `gridwatch` in the Proxmox GUI.
* **Smart Resume:** Built-in hysteresis prevents "flapping" (rapid on/off cycling) to protect hardware.

---

## Quick Start

### 1. Installation
Clone the repo and install dependencies:
```bash
git clone [https://github.com/Norris-Eng/gridwatch-home-assistant.git](https://github.com/Norris-Eng/gridwatch-home-assistant.git)
cd gridwatch-home-assistant
pip install -r requirements.txt
```

### 2. Configuration (The Secure Way)
**DO NOT edit the scripts directly.** Set your API key and preferences via Environment Variables.

**Linux/Mac:**
```bash
export GRIDWATCH_API_KEY="YOUR_RAPIDAPI_KEY"
export GRIDWATCH_REGION="ERCOT"
export GW_PRICE_CAP="200"  # Shut down if price > $200
```

**Windows (PowerShell):**
```powershell
$env:GRIDWATCH_API_KEY="YOUR_RAPIDAPI_KEY"
$env:GRIDWATCH_REGION="PJM"
```

*(Advanced users: You can use a `.env` file loader if you prefer.)*

### 3. Run the Client
```bash
# Launches the Visual Dashboard (Generic Client)
python gridwatch_client.py
```

---

## Modules

| File | Use Case |
| :--- | :--- |
| `gridwatch_client.py` | **General Purpose.** Visual dashboard. Good for Raspberry Pis, GPIO control, or monitoring. |
| `integrations/proxmox_trigger.py` | **Homelab / AI.** Pauses/Resumes VMs and LXC containers automatically using Proxmox Tags. |
| `integrations/foreman_trigger.py` | **Mining.** Controls ASIC fleets via Foreman API. |
| `integrations/hiveos_trigger.py` | **Mining.** Controls GPU rigs via HiveOS API. |
| `home_assistant/` | YAML configuration for Home Assistant (HA) integration. |

---

## Resources
* **Get API Key:** [RapidAPI GridWatch Telemetry](https://rapidapi.com/cnorris1316/api/gridwatch-us-telemetry)
* **Documentation:** [View Integrations README](./integrations/README.md)
