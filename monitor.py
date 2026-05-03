import json
import logging
import os
import time
from datetime import datetime, timezone

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


def get_bool_env(key, default=False):
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


# --- Config from environment variables ---
CHANNELS_HOST          = require_env("CHANNELS_HOST")
CHANNELS_PORT          = os.environ.get("CHANNELS_PORT", "8089")
MQTT_HOST              = require_env("MQTT_HOST")
MQTT_PORT              = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER              = require_env("MQTT_USER")
MQTT_PASS              = require_env("MQTT_PASS")
MQTT_TOPIC             = os.environ.get("MQTT_TOPIC", "channels2mqtt/latest_recording")
UPCOMING_TOPIC         = os.environ.get("UPCOMING_TOPIC", "channels2mqtt/upcoming_recordings")
ALL_RECORDINGS_TOPIC   = os.environ.get("ALL_RECORDINGS_TOPIC", "channels2mqtt/all_recordings")
POLL_INTERVAL          = int(os.environ.get("POLL_INTERVAL", "60"))
LATEST_INCLUDE_WATCHED = get_bool_env("LATEST_INCLUDE_WATCHED", False)
ALL_INCLUDE_WATCHED    = get_bool_env("ALL_INCLUDE_WATCHED", False)
LATEST_INCLUDE_IN_PROGRESS = get_bool_env("LATEST_INCLUDE_IN_PROGRESS", False)

BASE_API       = f"http://{CHANNELS_HOST}:{CHANNELS_PORT}/api/v1/all?order=desc"
RECORDINGS_API = BASE_API if LATEST_INCLUDE_WATCHED else f"{BASE_API}&watched=false"
ALL_API        = BASE_API if ALL_INCLUDE_WATCHED    else f"{BASE_API}&watched=false"
UPCOMING_API   = f"http://{CHANNELS_HOST}:{CHANNELS_PORT}/api/v1/jobs"

DEVICE = {
    "identifiers": ["channels_dvr"],
    "name": "Channels DVR",
    "model": "Channels DVR Server",
    "manufacturer": "Fancy Bits"
}


# --- Latest Recording ---

def publish_recording_discovery(client):
    discovery_payload = {
        "name": "Latest Recording",
        "unique_id": "latest_recording",
        "state_topic": MQTT_TOPIC,
        "value_template": "{{ value_json.title }}",
        "json_attributes_topic": MQTT_TOPIC,
        "icon": "mdi:television-play",
        "device": DEVICE
    }
    client.publish(
        "homeassistant/sensor/channels_dvr_latest_recording/config",
        json.dumps(discovery_payload),
        retain=True
    )
    log.info("Channels2MQTT: Published latest recording discovery config")


def get_latest_recording():
    try:
        response = requests.get(RECORDINGS_API, timeout=10)
        response.raise_for_status()
        recordings = response.json()
        if not LATEST_INCLUDE_IN_PROGRESS:
            recordings = [r for r in recordings if r.get("completed", False)]
        if recordings:
            return recordings[0]
    except requests.RequestException as e:
        log.error(f"Channels2MQTT: Failed to fetch latest recording: {e}")
    return None


def build_recording_payload(recording):
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


# --- All Recordings ---

def publish_all_recordings_discovery(client):
    discovery_payload = {
        "name": "All Recordings",
        "unique_id": "all_recordings",
        "state_topic": ALL_RECORDINGS_TOPIC,
        "value_template": "{{ value_json.count }}",
        "json_attributes_topic": ALL_RECORDINGS_TOPIC,
        "icon": "mdi:television-pause",
        "unit_of_measurement": "recordings",
        "device": DEVICE
    }
    client.publish(
        "homeassistant/sensor/channels_dvr_all_recordings/config",
        json.dumps(discovery_payload),
        retain=True
    )
    log.info("Channels2MQTT: Published all recordings discovery config")


def get_all_recordings():
    try:
        response = requests.get(ALL_API, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        log.error(f"Channels2MQTT: Failed to fetch all recordings: {e}")
    return []


def process_all_recordings(client):
    recordings = get_all_recordings()
    payload = {
        "count":      len(recordings),
        "recordings": [build_recording_payload(r) for r in recordings]
    }
    client.publish(ALL_RECORDINGS_TOPIC, json.dumps(payload), retain=True)
    log.info(f"Channels2MQTT: {len(recordings)} total recording(s) published")


# --- Upcoming Recordings ---

def publish_upcoming_discovery(client):
    discovery_payload = {
        "name": "Upcoming Recordings",
        "unique_id": "upcoming_recordings",
        "state_topic": UPCOMING_TOPIC,
        "value_template": "{{ value_json.count }}",
        "json_attributes_topic": UPCOMING_TOPIC,
        "icon": "mdi:television-guide",
        "unit_of_measurement": "recordings",
        "device": DEVICE
    }
    client.publish(
        "homeassistant/sensor/channels_dvr_upcoming_recordings/config",
        json.dumps(discovery_payload),
        retain=True
    )
    log.info("Channels2MQTT: Published upcoming recordings discovery config")


def build_upcoming_payload(job):
    item = job.get("item", {})
    start_dt      = datetime.fromtimestamp(job["start_time"], tz=timezone.utc).isoformat()
    end_dt        = datetime.fromtimestamp(job["end_time"],   tz=timezone.utc).isoformat()
    duration_mins = round(job.get("duration", 0) / 60)
    return {
        "id":                job.get("id", ""),
        "title":             job.get("name", ""),
        "episode":           item.get("episode_title", ""),
        "season":            item.get("season_number", ""),
        "episode_number":    item.get("episode_number", ""),
        "channels":          job.get("channels", []),
        "start_time":        start_dt,
        "end_time":          end_dt,
        "duration_mins":     duration_mins,
        "summary":           item.get("summary", ""),
        "image_url":         item.get("image_url", ""),
        "genres":            item.get("genres", []),
        "cast":              item.get("cast", []),
        "content_rating":    item.get("content_rating", ""),
        "original_air_date": item.get("original_air_date", ""),
        "tags":              item.get("tags", []),
        "skipped":           job.get("skipped", False),
        "failed":            job.get("failed", False),
    }


def get_upcoming_jobs():
    try:
        response = requests.get(UPCOMING_API, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        log.error(f"Channels2MQTT: Failed to fetch upcoming jobs: {e}")
    return []


def process_upcoming(client):
    now  = datetime.now(tz=timezone.utc).timestamp()
    jobs = get_upcoming_jobs()

    upcoming = [
        build_upcoming_payload(job)
        for job in jobs
        if job.get("start_time", 0) >= now
    ]

    payload = {
        "count":      len(upcoming),
        "recordings": upcoming
    }

    client.publish(UPCOMING_TOPIC, json.dumps(payload), retain=True)
    log.info(f"Channels2MQTT: {len(upcoming)} upcoming recording(s) published")


# --- Main ---

def main():
    log.info("Channels2MQTT starting...")

    client = mqtt.Client(client_id="channels2mqtt")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    log.info(f"Channels2MQTT: Connected to MQTT at {MQTT_HOST}:{MQTT_PORT}")

    publish_recording_discovery(client)
    publish_upcoming_discovery(client)
    publish_all_recordings_discovery(client)

    # Seed seen IDs from all currently known recordings so we don't
    # fire spurious notifications for pre-existing recordings on startup.
    seen_recording_ids = set()
    for r in get_all_recordings():
        seen_recording_ids.add(r.get("id"))
    log.info(f"Channels2MQTT: Seeded {len(seen_recording_ids)} existing recording ID(s)")

    while True:
        # Latest recording
        recording = get_latest_recording()
        if recording:
            current_id = recording.get("id")
            if current_id not in seen_recording_ids:
                payload = build_recording_payload(recording)
                client.publish(MQTT_TOPIC, json.dumps(payload), retain=True)
                log.info(f"Channels2MQTT: New recording detected: {payload['title']} - {payload['episode']}")
                seen_recording_ids.add(current_id)
            else:
                log.debug("Channels2MQTT: No new recording detected.")
        else:
            log.warning("Channels2MQTT: No recordings returned from Channels DVR.")

        # Upcoming recordings
        process_upcoming(client)

        # All recordings
        process_all_recordings(client)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
