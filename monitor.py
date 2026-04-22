import json
import logging
import os
import time

import paho.mqtt.client as mqtt
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

def require_env(key):
    value = os.environ.get(key)
    if not value:
        raise EnvironmentError(f"Channels2MQTT: Required environment variable '{key}' is not set.")
    return value

# --- Config from environment variables ---
CHANNELS_HOST = require_env("CHANNELS_HOST")
CHANNELS_PORT = os.environ.get("CHANNELS_PORT", "8089")
MQTT_HOST     = require_env("MQTT_HOST")
MQTT_PORT     = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER     = require_env("MQTT_USER")
MQTT_PASS     = require_env("MQTT_PASS")
MQTT_TOPIC    = os.environ.get("MQTT_TOPIC", "channels2mqtt/latest_recording")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))

CHANNELS_API    = f"http://{CHANNELS_HOST}:{CHANNELS_PORT}/api/v1/all?order=desc&watched=false"
DISCOVERY_TOPIC = "homeassistant/sensor/channels2mqtt_latest_recording/config"


def publish_discovery(client):
    """Publish MQTT discovery config so HA auto-creates the sensor."""
    discovery_payload = {
        "name": "Latest Recording",
        "unique_id": "channels2mqtt_latest_recording",
        "state_topic": MQTT_TOPIC,
        "value_template": "{{ value_json.title }}",
        "json_attributes_topic": MQTT_TOPIC,
        "icon": "mdi:television-play",
        "device": {
            "identifiers": ["channels2mqtt"],
            "name": "Channels2MQTT",
            "model": "Channels DVR Server",
            "manufacturer": "Fancy Bits"
        }
    }
    client.publish(DISCOVERY_TOPIC, json.dumps(discovery_payload), retain=True)
    log.info("Channels2MQTT: Published MQTT discovery config for Home Assistant")


def get_latest_recording():
    try:
        response = requests.get(CHANNELS_API, timeout=10)
        response.raise_for_status()
        recordings = response.json()
        if recordings:
            return recordings[0]  # Most recent first
    except requests.RequestException as e:
        log.error(f"Channels2MQTT: Failed to fetch recordings: {e}")
    return None


def build_payload(recording):
    """Extract the fields we care about into a clean dict."""
    duration_mins = round(recording.get("duration", 0) / 60)
    return {
        "id":             recording.get("id", ""),
        "title":          recording.get("title", ""),
        "episode":        recording.get("episode_title", ""),
        "season":         recording.get("season_number", ""),
        "episode_number": recording.get("episode_number", ""),
        "channel":        recording.get("channel", ""),
        "duration_mins":  duration_mins,
        "genres":         recording.get("genres", []),
        "summary":        recording.get("summary", ""),
        "image_url":      recording.get("image_url", ""),
        "thumbnail_url":  recording.get("thumbnail_url", ""),
        "completed":      recording.get("completed", False),
        "corrupted":      recording.get("corrupted", False),
        "watched":        recording.get("watched", False),
        "created_at":     recording.get("created_at", ""),
    }


def main():
    log.info("Channels2MQTT starting...")

    # Set up MQTT client
    client = mqtt.Client(client_id="channels2mqtt")
    client.username_pw_set(MQTT_USER, MQTT_PASS)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    log.info(f"Channels2MQTT: Connected to MQTT at {MQTT_HOST}:{MQTT_PORT}")

    # Auto-register sensor in Home Assistant via MQTT Discovery
    publish_discovery(client)

    last_id = None

    while True:
        recording = get_latest_recording()

        if recording:
            current_id = recording.get("id")

            if current_id != last_id:
                payload = build_payload(recording)
                message = json.dumps(payload)
                client.publish(MQTT_TOPIC, message, retain=True)
                log.info(f"Channels2MQTT: New recording detected: {payload['title']} - {payload['episode']}")
                last_id = current_id
            else:
                log.debug("Channels2MQTT: No new recording detected.")
        else:
            log.warning("Channels2MQTT: No recordings returned from Channels DVR.")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
