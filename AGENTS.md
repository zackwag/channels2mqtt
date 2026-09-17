# AGENTS.md

## Project overview

channels2mqtt bridges a Channels DVR server to Home Assistant via MQTT Discovery, publishing recordings and upcoming scheduled shows as sensors. Single-file Python 3 script, runs as a Docker container.

## Setup

```bash
pip install -r requirements.txt
pip install pytest   # test-only dependency, not in requirements.txt
```

## Build / Run

```bash
docker build -t channels2mqtt .
python monitor.py     # requires CHANNELS_HOST, CHANNELS_PORT, MQTT_HOST, MQTT_PORT env vars
```

## Test

```bash
pytest
```

`test_monitor.py` covers `monitor.py` with mocked HTTP/MQTT calls. Not currently run in CI — only `conventional-commits.yml` exists under `.github/workflows/`.

## Repository structure

- `monitor.py` — the entire bridge: polls Channels DVR, publishes MQTT Discovery sensors
- `test_monitor.py` — pytest suite for `monitor.py`
- `Dockerfile` — container build definition

## Commit and PR conventions

- Commit messages and PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `build:`, `perf:`, `style:`, `revert:`), optionally with a scope, e.g. `fix(api): handle null response`.
- This repo squash-merges pull requests only; the PR title becomes the final commit message on `main`.
- A "Conventional Commits" CI check enforces this on both PR titles and direct-push commit messages.
- Branch protection on `main`: no force-pushes, no branch deletion, required status checks must pass.
