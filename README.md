# kermi2mqtt

[![Tests](https://github.com/jr42/kermi2mqtt/actions/workflows/test.yml/badge.svg)](https://github.com/jr42/kermi2mqtt/actions/workflows/test.yml)
[![Docker](https://github.com/jr42/kermi2mqtt/actions/workflows/docker.yaml/badge.svg)](https://github.com/jr42/kermi2mqtt/actions/workflows/docker.yaml)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

Modbus-to-MQTT bridge for Kermi heat pumps with Home Assistant auto-discovery.

## Features

- **Full monitoring** - All heat pump sensors published via MQTT
- **Bidirectional control** - Change settings (mode, preset, DHW temp) via MQTT
- **Home Assistant integration** - Zero-config auto-discovery with climate & water_heater entities
- **Unified device** - All entities grouped under single "Kermi X-Center" device in HA
- **Safety-first** - Only exposes user-safe controls with validation
- **Kubernetes ready** - Helm chart included for easy deployment
- **Async/efficient** - Low resource usage (<50MB RAM)

## Quick Start

### Prerequisites

- Kermi heat pump with Modbus TCP/RTU interface
- MQTT broker (Mosquitto, Home Assistant, etc.)
- Python 3.12+ or Docker

### Installation

#### Option 1: Docker (Recommended)

```bash
# Create config file
cp config.example.yaml config.yaml
# Edit config.yaml with your Modbus and MQTT settings

# Build and run
docker build -t kermi2mqtt .
docker run -d --name kermi2mqtt \
  -v $(pwd)/config.yaml:/config/config.yaml:ro \
  kermi2mqtt
```

Or with Docker Compose:

```bash
docker-compose up -d
```

#### Option 2: Kubernetes (Helm)

```bash
# Add your values
cat > my-values.yaml << EOF
config:
  modbus:
    host: "xcenter.local"
    port: 502
  mqtt:
    host: "mqtt.local"
    port: 8883
    tlsEnabled: true
mqttAuth:
  username: "kermi"
  password: "your-password"
EOF

# Install
helm install kermi2mqtt ./charts/kermi2mqtt -f my-values.yaml
```

See [charts/kermi2mqtt/values.yaml](charts/kermi2mqtt/values.yaml) for all options.

#### Option 3: Python Package

```bash
# Install from PyPI
pip install kermi2mqtt

# Or install from source
git clone https://github.com/jr42/kermi2mqtt
cd kermi2mqtt
pip install -e .
```

### Configuration

1. Copy `config.example.yaml` to `config.yaml`
2. Configure your Modbus connection:
   ```yaml
   modbus:
     host: 192.168.1.100  # Your heat pump IP
     port: 502
     mode: tcp
   ```
3. Configure your MQTT broker:
   ```yaml
   mqtt:
     host: localhost
     port: 1883
   ```
4. Set device ID (or leave blank for auto-detection):
   ```yaml
   integration:
     device_id: my_heat_pump
     poll_interval: 30.0
   ```

### Running

#### Docker

```bash
docker-compose up -d
docker-compose logs -f kermi2mqtt
```

#### Python

```bash
python -m kermi2mqtt --config config.yaml
```

#### Systemd Service

```bash
# Copy service file
sudo cp kermi2mqtt.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable kermi2mqtt
sudo systemctl start kermi2mqtt

# Check status
sudo systemctl status kermi2mqtt
```

## MQTT Topics

### State Topics (Published by kermi2mqtt)

```
kermi/{device_id}/sensors/outdoor_temp          → Outdoor temperature
kermi/{device_id}/sensors/supply_temp           → Supply temperature
kermi/{device_id}/sensors/cop                   → Coefficient of Performance
kermi/{device_id}/sensors/power_total           → Thermal power output
kermi/{device_id}/sensors/power_electrical      → Electrical power consumption

kermi/{device_id}/heating/actual                → Current heating temperature
kermi/{device_id}/heating/setpoint              → Heating setpoint
kermi/{device_id}/heating/circuit_status        → Heating circuit status

kermi/{device_id}/water_heater/actual           → DHW actual temperature
kermi/{device_id}/water_heater/setpoint         → DHW setpoint
kermi/{device_id}/water_heater/single_charge    → One-time heating active

kermi/{device_id}/availability                  → online/offline
```

### Command Topics (Subscribe with MQTT client)

```bash
# Monitor all topics
mosquitto_sub -h localhost -t 'kermi/#' -v

# Monitor specific sensor
mosquitto_sub -h localhost -t 'kermi/my_heat_pump/sensors/outdoor_temp'
```

## Home Assistant Integration

Entities automatically appear in Home Assistant with appropriate types:

- **Climate** entities for heating/cooling control
- **Water Heater** entities for domestic hot water
- **Sensor** entities for temperature, power, COP readings
- **Switch** entities for on/off controls
- **Binary Sensor** entities for status indicators

All entities are grouped under a single **Device** in Home Assistant.

## Architecture

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Kermi Heat     │ Modbus  │  kermi2mqtt  │  MQTT   │  Home Assistant │
│  Pump (x-center)│◄───────►│   Bridge     │◄───────►│  / MQTT Clients │
└─────────────────┘         └──────────────┘         └─────────────────┘
                                    │
                            ┌───────▼────────┐
                            │ py-kermi-xcenter│
                            │  (Modbus lib)   │
                            └─────────────────┘
```

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/jr42/kermi2mqtt
cd kermi2mqtt

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows

# Install with dev dependencies
pip install -e ".[dev]"
```

### Testing

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=src/kermi2mqtt --cov-report=html

# Run linters
ruff check src/ tests/
mypy src/kermi2mqtt/
black --check src/ tests/
```

### Project Structure

```
kermi2mqtt/
├── src/kermi2mqtt/           # Main package
│   ├── __main__.py           # Entry point
│   ├── config.py             # Configuration loading
│   ├── modbus_client.py      # Modbus wrapper
│   ├── mqtt_client.py        # MQTT wrapper
│   ├── bridge.py             # Main bridge logic
│   ├── safety.py             # Safety validation
│   ├── ha_discovery.py       # HA discovery payloads
│   ├── mappings.py           # Attribute definitions
│   └── models/               # Data models
├── charts/kermi2mqtt/        # Helm chart for Kubernetes
├── tests/                    # Test suite
├── Dockerfile                # Container image
└── config.example.yaml       # Example configuration
```

## Safety

This integration only exposes **user-safe controls** equivalent to the heat pump's physical interface:

✅ **Safe to modify:**
- Temperature setpoints (40-60°C for DHW)
- Operating modes (heating/cooling)
- One-time water heating
- Heating schedules

❌ **Not exposed (hardware safety):**
- Compressor controls
- Refrigerant valve positions
- System pressure
- Low-level firmware parameters

See [specs/001-modbus-mqtt/safety.md](specs/001-modbus-mqtt/safety.md) for detailed safety documentation.

## Troubleshooting

### Connection Issues

```bash
# Test Modbus connection
python -c "from kermi_xcenter import KermiModbusClient, HeatPump; import asyncio; asyncio.run(test())"

# Check MQTT broker
mosquitto_sub -h localhost -t '#' -v
```

### Logs

```bash
# Docker logs
docker-compose logs -f kermi2mqtt

# Systemd logs
journalctl -u kermi2mqtt -f

# Increase log verbosity in config.yaml
logging:
  level: DEBUG
```

### Common Issues

1. **"No response from heat pump"**
   - Check network connectivity: `ping <heat_pump_ip>`
   - Verify Modbus port 502 is accessible
   - Check firewall rules

2. **"MQTT connection failed"**
   - Verify broker is running: `systemctl status mosquitto`
   - Test broker: `mosquitto_sub -h localhost -t test`
   - Check credentials in config.yaml

3. **"Entities not appearing in Home Assistant"**
   - Check MQTT discovery prefix matches HA config (default: `homeassistant`)
   - Verify kermi2mqtt is publishing: `mosquitto_sub -t 'homeassistant/#'`
   - Restart Home Assistant after first discovery

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run linters and tests
5. Submit a pull request

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Credits

- Built with [py-kermi-xcenter](https://github.com/jr42/py-kermi-xcenter) by @jr42
- Uses [aiomqtt](https://github.com/sbtinstruments/aiomqtt) for async MQTT
- Designed for [Home Assistant](https://www.home-assistant.io/)

## Disclaimer

This software is not affiliated with or endorsed by Kermi. Use at your own risk. Always ensure changes are safe for your equipment.
