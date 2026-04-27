# Channels2MQTT

[![Docker Hub](https://img.shields.io/badge/docker-zackwag%2Fchannels2mqtt-blue?style=flat-square&logo=docker)](https://hub.docker.com/r/zackwag/channels2mqtt)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Backend](https://img.shields.io/badge/backend-Python%203.13-3776AB?style=flat-square&logo=python)](https://www.python.org/)

Bridges [Channels DVR](https://getchannels.com/) to Home Assistant via MQTT Discovery — automatically exposing recordings and upcoming scheduled shows as sensors.

## Sensors

Channels2MQTT automatically creates and manages three sensors in Home Assistant:

| Sensor | State | Description |
|---|---|---|
| `sensor.channels_dvr_latest_recording` | Show title | Updates when a new recording is completed |
| `sensor.channels_dvr_all_recordings` | Count | Full recording library with metadata |
| `sensor.channels_dvr_upcoming_recordings` | Count | Scheduled recordings with full program details |

## Requirements

- [Channels DVR Server](https://getchannels.com/)
- MQTT broker (e.g. [Mosquitto](https://mosquitto.org/))
- Home Assistant with MQTT integration enabled

## Quick Start

```yaml
services:
  channels2mqtt:
    image: zackwag/channels2mqtt:latest
    container_name: channels2mqtt
    restart: unless-stopped
    environment:
      - CHANNELS_HOST=192.168.x.x
      - MQTT_HOST=192.168.x.x
      - MQTT_USER=your_mqtt_username
      - MQTT_PASS=your_mqtt_password
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `CHANNELS_HOST` | ✅ | — | Channels DVR server IP address |
| `CHANNELS_PORT` | ❌ | `8089` | Channels DVR server port |
| `MQTT_HOST` | ✅ | — | MQTT broker IP address |
| `MQTT_PORT` | ❌ | `1883` | MQTT broker port |
| `MQTT_USER` | ✅ | — | MQTT broker username |
| `MQTT_PASS` | ✅ | — | MQTT broker password |
| `MQTT_TOPIC` | ❌ | `channels2mqtt/latest_recording` | Topic for latest recording |
| `UPCOMING_TOPIC` | ❌ | `channels2mqtt/upcoming_recordings` | Topic for upcoming recordings |
| `ALL_RECORDINGS_TOPIC` | ❌ | `channels2mqtt/all_recordings` | Topic for all recordings |
| `POLL_INTERVAL` | ❌ | `60` | Poll interval in seconds |
| `LATEST_INCLUDE_WATCHED` | ❌ | `false` | Include watched in latest recording |
| `ALL_INCLUDE_WATCHED` | ❌ | `false` | Include watched in all recordings |
| `LATEST_INCLUDE_IN_PROGRESS` | ❌ | `false` | Include in-progress recordings in latest |

## Home Assistant

Sensors are registered automatically via MQTT Discovery — no changes to `configuration.yaml` required. Once the container starts, the **Channels DVR** device will appear under Settings → Devices & Services → MQTT.

### Example Automation

Notify when a new recording is available:

```yaml
alias: New DVR Recording Notification
triggers:
  - trigger: state
    entity_id: sensor.channels_dvr_latest_recording
conditions:
  - condition: template
    value_template: >
      {{ states('sensor.channels_dvr_latest_recording') not in ['', 'unknown', 'unavailable'] }}
actions:
  - action: notify.your_device
    data:
      title: "📺 New Recording"
      message: >
        {{ state_attr('sensor.channels_dvr_latest_recording', 'title') }} -
        {{ state_attr('sensor.channels_dvr_latest_recording', 'episode') }}
```

## Building Locally

```bash
docker build -t zackwag/channels2mqtt:latest .
```

## Docker Hub

[zackwag/channels2mqtt](https://hub.docker.com/r/zackwag/channels2mqtt)

## License

MIT
