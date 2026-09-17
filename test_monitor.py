import importlib
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

ENV_DEFAULTS = {
    "CHANNELS_HOST": "localhost",
    "CHANNELS_PORT": "8089",
    "MQTT_HOST": "mqtt.local",
    "MQTT_PORT": "1883",
    "MQTT_USER": "user",
    "MQTT_PASS": "pass",
}


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    for k, v in ENV_DEFAULTS.items():
        monkeypatch.setenv(k, v)


@pytest.fixture()
def monitor():
    import monitor as mod

    return importlib.reload(mod)


# --- require_env / get_bool_env ---


class TestRequireEnv:
    def test_returns_value(self, monitor):
        assert monitor.require_env("CHANNELS_HOST") == "localhost"

    def test_raises_on_missing(self, monitor, monkeypatch):
        monkeypatch.delenv("CHANNELS_HOST", raising=False)
        with pytest.raises(EnvironmentError, match="CHANNELS_HOST"):
            monitor.require_env("CHANNELS_HOST")

    def test_raises_on_empty(self, monitor, monkeypatch):
        monkeypatch.setenv("CHANNELS_HOST", "")
        with pytest.raises(EnvironmentError):
            monitor.require_env("CHANNELS_HOST")


class TestGetBoolEnv:
    @pytest.mark.parametrize("val", ["true", "True", "1", "yes", "YES"])
    def test_truthy(self, monitor, monkeypatch, val):
        monkeypatch.setenv("TEST_FLAG", val)
        assert monitor.get_bool_env("TEST_FLAG") is True

    @pytest.mark.parametrize("val", ["false", "0", "no", ""])
    def test_falsy(self, monitor, monkeypatch, val):
        monkeypatch.setenv("TEST_FLAG", val)
        assert monitor.get_bool_env("TEST_FLAG") is False

    def test_default_false(self, monitor, monkeypatch):
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert monitor.get_bool_env("TEST_FLAG") is False

    def test_default_true(self, monitor, monkeypatch):
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert monitor.get_bool_env("TEST_FLAG", default=True) is True


# --- build_recording_payload ---


SAMPLE_RECORDING = {
    "id": "rec-1",
    "title": "Seinfeld",
    "episode_title": "The Contest",
    "season_number": 4,
    "episode_number": 11,
    "channel": "TBS",
    "duration": 1800,
    "genres": ["Comedy"],
    "summary": "A bet.",
    "image_url": "http://img/1",
    "thumbnail_url": "http://thumb/1",
    "completed": True,
    "corrupted": False,
    "watched": False,
    "created_at": "2025-01-01T00:00:00Z",
}


class TestBuildRecordingPayload:
    def test_full_recording(self, monitor):
        result = monitor.build_recording_payload(SAMPLE_RECORDING)
        assert result["id"] == "rec-1"
        assert result["title"] == "Seinfeld"
        assert result["episode"] == "The Contest"
        assert result["season"] == 4
        assert result["episode_number"] == 11
        assert result["channel"] == "TBS"
        assert result["duration_mins"] == 30
        assert result["genres"] == ["Comedy"]
        assert result["completed"] is True

    def test_empty_recording(self, monitor):
        result = monitor.build_recording_payload({})
        assert result["id"] == ""
        assert result["title"] == ""
        assert result["duration_mins"] == 0
        assert result["genres"] == []
        assert result["completed"] is False

    def test_duration_rounding(self, monitor):
        result = monitor.build_recording_payload({"duration": 5555})
        assert result["duration_mins"] == 93


# --- build_upcoming_payload ---


SAMPLE_JOB = {
    "id": "job-1",
    "name": "The News",
    "start_time": 1700000000,
    "end_time": 1700003600,
    "duration": 3600,
    "channels": ["CNN"],
    "skipped": False,
    "failed": False,
    "item": {
        "episode_title": "Evening Edition",
        "season_number": 1,
        "episode_number": 100,
        "summary": "News summary",
        "image_url": "http://img/2",
        "genres": ["News"],
        "cast": ["Anchor"],
        "content_rating": "TV-G",
        "original_air_date": "2025-11-14",
        "tags": ["live"],
    },
}


class TestBuildUpcomingPayload:
    def test_full_job(self, monitor):
        result = monitor.build_upcoming_payload(SAMPLE_JOB)
        assert result["id"] == "job-1"
        assert result["title"] == "The News"
        assert result["episode"] == "Evening Edition"
        assert result["duration_mins"] == 60
        assert result["channels"] == ["CNN"]
        expected_start = datetime.fromtimestamp(1700000000, tz=timezone.utc).isoformat()
        assert result["start_time"] == expected_start

    def test_missing_item_fields(self, monitor):
        minimal = {
            "id": "j2",
            "name": "X",
            "start_time": 0,
            "end_time": 0,
            "duration": 0,
            "item": {},
        }
        result = monitor.build_upcoming_payload(minimal)
        assert result["episode"] == ""
        assert result["summary"] == ""
        assert result["genres"] == []


# --- API fetch functions (mocked requests) ---


class TestGetLatestRecording:
    @patch("monitor.requests.get")
    def test_returns_first(self, mock_get, monitor, monkeypatch):
        monkeypatch.setattr(monitor, "LATEST_INCLUDE_IN_PROGRESS", False)
        recs = [{"id": "1", "completed": True}, {"id": "2", "completed": True}]
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=recs))
        assert monitor.get_latest_recording()["id"] == "1"

    @patch("monitor.requests.get")
    def test_filters_in_progress(self, mock_get, monitor, monkeypatch):
        monkeypatch.setattr(monitor, "LATEST_INCLUDE_IN_PROGRESS", False)
        recs = [{"id": "1", "completed": False}, {"id": "2", "completed": True}]
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=recs))
        assert monitor.get_latest_recording()["id"] == "2"

    @patch("monitor.requests.get")
    def test_includes_in_progress(self, mock_get, monitor, monkeypatch):
        monkeypatch.setattr(monitor, "LATEST_INCLUDE_IN_PROGRESS", True)
        recs = [{"id": "1", "completed": False}]
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=recs))
        assert monitor.get_latest_recording()["id"] == "1"

    @patch("monitor.requests.get")
    def test_returns_none_on_empty(self, mock_get, monitor):
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=[]))
        assert monitor.get_latest_recording() is None

    @patch("monitor.requests.get", side_effect=requests.RequestException("timeout"))
    def test_returns_none_on_error(self, mock_get, monitor):
        assert monitor.get_latest_recording() is None


class TestGetAllRecordings:
    @patch("monitor.requests.get")
    def test_returns_list(self, mock_get, monitor):
        recs = [{"id": "1"}, {"id": "2"}]
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=recs))
        assert len(monitor.get_all_recordings()) == 2

    @patch("monitor.requests.get", side_effect=requests.RequestException("err"))
    def test_returns_empty_on_error(self, mock_get, monitor):
        assert monitor.get_all_recordings() == []


class TestGetUpcomingJobs:
    @patch("monitor.requests.get")
    def test_returns_list(self, mock_get, monitor):
        jobs = [{"id": "j1"}]
        mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=jobs))
        assert monitor.get_upcoming_jobs() == jobs

    @patch("monitor.requests.get", side_effect=requests.RequestException("err"))
    def test_returns_empty_on_error(self, mock_get, monitor):
        assert monitor.get_upcoming_jobs() == []


# --- MQTT publish functions ---


class TestPublishDiscovery:
    def test_latest_recording_discovery(self, monitor):
        client = MagicMock()
        monitor.publish_recording_discovery(client)
        client.publish.assert_called_once()
        topic, payload_str, *_ = client.publish.call_args[0]
        assert topic == "homeassistant/sensor/channels_dvr_latest_recording/config"
        payload = json.loads(payload_str)
        assert payload["unique_id"] == "latest_recording"
        assert payload["device"]["name"] == "Channels DVR"

    def test_upcoming_discovery(self, monitor):
        client = MagicMock()
        monitor.publish_upcoming_discovery(client)
        topic = client.publish.call_args[0][0]
        assert topic == "homeassistant/sensor/channels_dvr_upcoming_recordings/config"

    def test_all_recordings_discovery(self, monitor):
        client = MagicMock()
        monitor.publish_all_recordings_discovery(client)
        topic = client.publish.call_args[0][0]
        assert topic == "homeassistant/sensor/channels_dvr_all_recordings/config"


# --- process functions ---


class TestProcessAllRecordings:
    @patch("monitor.get_all_recordings")
    def test_publishes_count(self, mock_fetch, monitor):
        mock_fetch.return_value = [SAMPLE_RECORDING, SAMPLE_RECORDING]
        client = MagicMock()
        monitor.process_all_recordings(client)
        payload = json.loads(client.publish.call_args[0][1])
        assert payload["count"] == 2
        assert len(payload["recordings"]) == 2


class TestProcessUpcoming:
    @patch("monitor.get_upcoming_jobs")
    def test_filters_past_jobs(self, mock_fetch, monitor):
        future_ts = datetime.now(tz=timezone.utc).timestamp() + 10000
        past_ts = 1000
        mock_fetch.return_value = [
            {**SAMPLE_JOB, "start_time": future_ts, "end_time": future_ts + 3600},
            {**SAMPLE_JOB, "start_time": past_ts, "end_time": past_ts + 3600},
        ]
        client = MagicMock()
        monitor.process_upcoming(client)
        payload = json.loads(client.publish.call_args[0][1])
        assert payload["count"] == 1


# --- Config / URL construction ---


class TestConfig:
    def test_default_urls(self, monitor):
        assert "order=desc" in monitor.BASE_API
        assert "localhost" in monitor.BASE_API
        assert "8089" in monitor.BASE_API

    def test_recordings_api_excludes_watched_by_default(self, monitor):
        assert "watched=false" in monitor.RECORDINGS_API

    def test_upcoming_api(self, monitor):
        assert monitor.UPCOMING_API.endswith("/api/v1/jobs")

    def test_custom_port(self, monkeypatch):
        monkeypatch.setenv("CHANNELS_PORT", "9999")
        import monitor as mod

        mod = importlib.reload(mod)
        assert "9999" in mod.BASE_API
