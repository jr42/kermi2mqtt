# Quickstart Guide

**Feature**: kermi2mqtt Integration
**Date**: 2025-11-25
**Purpose**: Get up and running with Kermi Heat Pump MQTT integration

---

## Prerequisites

- Kermi heat pump with Modbus TCP enabled
- MQTT broker (Mosquitto, Home Assistant built-in, etc.)
- Python 3.14+ **or** Docker
- Network access from host to both heat pump and MQTT broker

---

## Quick Start (Docker - Recommended)

### 1. Create Configuration

```bash
mkdir -p ~/kermi2mqtt
cd ~/kermi2mqtt
nano config.yaml
```

```yaml
# config.yaml
modbus:
  host: "192.168.1.100"       # Your heat pump IP
  port: 502                    # Default Modbus TCP port
  timeout: 10                  # Connection timeout (seconds)

mqtt:
  broker: "192.168.1.50"       # Your MQTT broker IP
  port: 1883                   # Default MQTT port (or 8883 for TLS)
  username: "homeassistant"    # Optional
  password: "secret"           # Optional
  # tls: true                  # Uncomment for TLS
  # ca_cert: "/path/to/ca.crt" # Uncomment for TLS

integration:
  device_name: "main"          # Used if serial number unavailable
  poll_interval: 30            # Seconds between polls
  base_topic: "kermi"          # MQTT base topic
  homeassistant_discovery: true  # Enable HA auto-discovery
```

### 2. Run with Docker

```bash
docker run -d \
  --name kermi2mqtt \
  --restart unless-stopped \
  -v ~/kermi2mqtt/config.yaml:/config/config.yaml:ro \
  ghcr.io/you/kermi2mqtt:latest
```

### 3. Verify

```bash
# Check logs
docker logs -f kermi2mqtt

# Should see:
# INFO: Connected to Kermi heat pump at 192.168.1.100
# INFO: Connected to MQTT broker at 192.168.1.50
# INFO: Publishing Home Assistant discovery messages
# INFO: Device ID: kermi_12345ABC (serial number)
# INFO: Starting poll loop (interval: 30s)
```

### 4. Test MQTT

```bash
# Subscribe to all topics
mosquitto_sub -h 192.168.1.50 -t "kermi/#" -v

# You should see:
# kermi/12345ABC/availability online
# kermi/12345ABC/sensors/outdoor_temp 5.2
# kermi/12345ABC/sensors/cop 4.1
# ...
```

### 5. Check Home Assistant

1. Go to **Settings → Devices & Services**
2. Look for "MQTT" integration
3. Click on it → should see "Kermi Heat Pump" device
4. Click device → see all sensors and controls

**Done!** 🎉

---

## Quick Start (Python)

### 1. Install

```bash
# Create virtual environment
python3.14 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install
pip install kermi2mqtt

# Or from source
git clone https://github.com/you/kermi2mqtt.git
cd kermi2mqtt
pip install -e .
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
nano config.yaml  # Edit as shown above
```

### 3. Run

```bash
# Foreground (for testing)
kermi2mqtt --config config.yaml

# Background (systemd - see below)
```

---

## systemd Service (Linux)

### 1. Create Service File

```bash
sudo nano /etc/systemd/system/kermi2mqtt.service
```

```ini
[Unit]
Description=Kermi Heat Pump to MQTT Bridge
After=network.target

[Service]
Type=simple
User=homeassistant  # Or your user
WorkingDirectory=/home/homeassistant/kermi2mqtt
ExecStart=/home/homeassistant/kermi2mqtt/venv/bin/kermi2mqtt \
  --config /home/homeassistant/kermi2mqtt/config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable kermi2mqtt
sudo systemctl start kermi2mqtt
sudo systemctl status kermi2mqtt
```

### 3. View Logs

```bash
sudo journalctl -u kermi2mqtt -f
```

---

## Configuration Reference

### Minimal Config

```yaml
modbus:
  host: "192.168.1.100"

mqtt:
  broker: "192.168.1.50"
```

### Complete Config

```yaml
modbus:
  host: "192.168.1.100"
  port: 502
  timeout: 10
  retry_interval: 60  # Seconds between reconnection attempts

mqtt:
  broker: "192.168.1.50"
  port: 1883
  username: "user"
  password: "pass"
  tls: false
  ca_cert: null
  client_id: "kermi2mqtt"  # Auto-generated if not specified
  keepalive: 60

integration:
  device_name: "main"  # Fallback if serial unavailable
  poll_interval: 30
  base_topic: "kermi"
  homeassistant_discovery: true
  ha_discovery_prefix: "homeassistant"  # Default HA prefix
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR
```

---

## Troubleshooting

### Cannot Connect to Heat Pump

```bash
# Test Modbus connectivity
pip install pymodbus
python -c "
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('192.168.1.100', port=502)
print('Connected!' if client.connect() else 'Failed to connect')
client.close()
"
```

**Common Issues**:
- Heat pump Modbus not enabled → check heat pump menu
- Wrong IP address → verify with `ping 192.168.1.100`
- Firewall blocking port 502 → check firewall rules
- Network segmentation → ensure host can reach heat pump VLAN

### Cannot Connect to MQTT

```bash
# Test MQTT connectivity
mosquitto_sub -h 192.168.1.50 -t test -v

# In another terminal
mosquitto_pub -h 192.168.1.50 -t test -m "hello"
```

**Common Issues**:
- Wrong broker address
- Authentication required but not configured
- TLS required but not enabled in config
- Broker not running → `sudo systemctl status mosquitto`

### No Data Appearing

```bash
# Check logs for errors
docker logs kermi2mqtt  # Docker
journalctl -u kermi2mqtt -f  # systemd

# Look for:
# - Connection success messages
# - Poll cycle messages
# - Any error/warning messages
```

### Home Assistant Not Discovering

1. **Check MQTT integration installed** in HA
2. **Check discovery prefix** matches (default: `homeassistant`)
3. **Check retained messages**:
   ```bash
   mosquitto_sub -h 192.168.1.50 -t "homeassistant/#" -v
   # Should see discovery payloads
   ```
4. **Restart HA** to force rediscovery
5. **Check HA logs** for MQTT errors

### Values Not Updating

- Check poll interval isn't too long
- Check heat pump is responding (not in error state)
- Check MQTT messages are being published (mosquitto_sub)
- Check HA is subscribed to correct topics

---

## Multi-Instance Setup

Running multiple heat pumps:

```bash
# Instance 1
docker run -d \
  --name kermi2mqtt-main \
  -v ~/kermi-main/config.yaml:/config/config.yaml:ro \
  ghcr.io/you/kermi2mqtt:latest

# Instance 2
docker run -d \
  --name kermi2mqtt-garage \
  -v ~/kermi-garage/config.yaml:/config/config.yaml:ro \
  ghcr.io/you/kermi2mqtt:latest
```

Each config should point to different heat pump IPs. MQTT topics won't conflict (device IDs are unique).

---

## Next Steps

- **Automation**: Create Home Assistant automations using the entities
- **Dashboards**: Add heat pump data to Lovelace dashboards
- **Monitoring**: Set up alerts for errors or offline status
- **Optimization**: Use COP sensor to optimize operation schedules

---

## Support

- **Documentation**: See other .md files in `specs/001-modbus-mqtt/`
- **Issues**: GitHub issues at [repository]
- **Community**: Home Assistant forums, r/homeassistant
