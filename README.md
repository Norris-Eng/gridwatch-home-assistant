# GridWatch: Real-Time Grid Pricing & Health Monitor
**Turn your "Dumb" Home into a Smart Grid Asset.**

[Live Dashboard](https://gridwatch.live/)

This repository contains integrations for **Home Assistant** (Smart Home), **Proxmox** (Homelab), and legacy support for **Industrial Mining**.

---

## 1. Home Assistant Integration (Primary)
**Best for:** Most users. Automate high-load appliances (HVAC, EV Chargers, Pool Pumps, etc.) based on real-time wholesale grid prices and/or stress indices.

### Quick Start
1. Get your free API Key: [GridWatch RapidAPI Link](https://rapidapi.com/cnorris1316/api/gridwatch-us-telemetry)
2. Copy the YAML code from the `home_assistant/` folder:
   **[View configuration.yaml](./home_assistant/configuration.yaml)**
3. Paste it into your Home Assistant `configuration.yaml` file.
4. Restart Home Assistant.

---

## 2. Proxmox & Homelab (Advanced)
**Best for:** SysAdmins and Homelabbers.
Protect your hardware. Automatically trigger a "Graceful Shutdown" (SIGTERM) and Smart Resume of your high-power VMs or LXC containers when grid prices spike or grid stability wavers.

* **Proxmox Integration:** [`integrations/proxmox_trigger.py`](./integrations/proxmox_trigger.py)
    * *Requires `proxmoxer` library.*
* **Standalone Python Client:** [`gridwatch_client.py`](./gridwatch_client.py)
    * *For generic Linux servers, Raspberry Pis, or custom GPIO control.*

**Installation:**
~~~bash
git clone https://github.com/Norris-Eng/gridwatch-home-assistant.git
pip install -r requirements.txt
python integrations/proxmox_trigger.py
~~~

---

## 3. Advanced Integrations (Foreman, HiveOS)
For detailed configuration documentation on the Python Client, including Logic Flow and specific setup guides for Proxmox and Mining:
**[View Integrations Documentation](./integrations/README.md)**
