# TTS-V2-API-Server Project Summary

## Overview

This is a Text-to-Speech API server using the Kokoro TTS model (hexgrad/Kokoro-82M). It provides an OpenAI-compatible API for speech synthesis with support for multiple voices.

**Repository:** `https://github.com/jim0237/TTS-V2-API-Server` (forked from `bmv234/TTS-V2-API-Server`)

---

## Key Files

| File | Purpose |
|------|---------|
| `main-ui.py` | Main application (Docker entrypoint runs this) |
| `main.py` | Duplicate of main-ui.py (kept for compatibility) |
| `Dockerfile` | Container build with NVIDIA CUDA base |
| `entrypoint.sh` | Container startup script |
| `requirements.txt` | Python dependencies |
| `docker-compose.caal-test.yml` | Compose file for HTTP mode testing |
| `.github/workflows/docker-build.yml` | GitHub Actions for GHCR publishing |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI interface |
| `/tts` | POST | Simple TTS (query params: `text`, `voice`) |
| `/v1/audio/speech` | POST | OpenAI-compatible TTS (JSON body) |
| `/v1/audio/voices` | GET | List available voices |
| `/v1/models` | GET | List available models |

### /v1/audio/speech Request Format
```json
{
  "model": "kokoro",
  "input": "Text to speak",
  "voice": "am_puck",
  "speed": 1.0
}
```

---

## Available Voices

| Voice ID | Description | Language |
|----------|-------------|----------|
| `af_bella` | American Female - Bella | en-US |
| `af_sarah` | American Female - Sarah | en-US |
| `af_nicole` | American Female - Nicole (ASMR) | en-US |
| `am_adam` | American Male - Adam | en-US |
| `am_michael` | American Male - Michael | en-US |
| `am_puck` | American Male - Puck | en-US |
| `bf_emma` | British Female - Emma | en-GB |
| `bf_isabella` | British Female - Isabella | en-GB |
| `bm_george` | British Male - George | en-GB |
| `bm_lewis` | British Male - Lewis | en-GB |

OpenAI voice names (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`) are also supported and mapped to Kokoro voices.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TTS_USE_HTTPS` | `true` | Set to `false` for HTTP mode |

### Ports

- Internal: `8000`
- Production (HTTPS): typically `8055`
- CAAL Test (HTTP): `8056`

---

## CAAL Compatibility Changes

Changes made to support the CAAL virtual assistant project:

1. **HTTP Mode** - Added `TTS_USE_HTTPS=false` environment variable
2. **Voice `am_puck`** - Added to voice list
3. **Direct Voice IDs** - Accept Kokoro voice IDs directly (e.g., `am_puck`) in addition to OpenAI names
4. **Voice Discovery** - Added `GET /v1/audio/voices` endpoint
5. **Pinned kokoro** - `kokoro==0.7.15` for model compatibility

### Docker Healthcheck Issue

The Dockerfile has an HTTPS healthcheck baked in:
```dockerfile
HEALTHCHECK ... CMD curl -k -f https://localhost:8000/ || exit 1
```

When running in HTTP mode, this causes "Invalid HTTP request received" warnings and marks the container as "unhealthy". The solution is to override the healthcheck in the compose file:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/v1/models"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

---

## Deployment Architecture Options

### Option 1: GHCR Pull (Recommended)

**How it works:**
- GitHub Actions builds the Docker image on push to main
- Image is published to GitHub Container Registry (GHCR)
- Server pulls pre-built image

**Compose file (current production):**
```yaml
services:
  tts-api:
    image: ghcr.io/bmv234/tts-v2-api-server:latest
    # ...
```

**To use your fork:**
```yaml
services:
  tts-api:
    image: ghcr.io/jim0237/tts-v2-api-server:latest
    # ...
```

**Pros:**
- Clean separation of build and deploy
- No source code on server
- Easy rollback (change image tag)
- Works across multiple servers
- CI/CD handles builds

**Cons:**
- Requires GitHub Actions workflow to be configured
- Need to wait for CI build after code changes

### Option 2: Local Build (Current CAAL Test Setup)

**How it works:**
- Clone repo to server
- Build image locally with `docker compose build`
- Run with `docker compose up`

**Compose file:**
```yaml
services:
  tts-api:
    build:
      context: .
      dockerfile: Dockerfile
    # ...
```

**Pros:**
- Immediate builds after code changes
- No external dependencies (GHCR)
- Good for development/testing

**Cons:**
- Source code on server
- Must have build dependencies on server
- Slower deployments
- Harder to manage across multiple servers

---

## Current Server Setup

### Production TTS (port 8055)
- **Location:** `~/ai-toolbox-container-deployment/stacks/tts-v2-service/`
- **Image:** `ghcr.io/bmv234/tts-v2-api-server:latest` (original fork)
- **Mode:** HTTPS
- **Status:** Healthy, running for 6 months

### CAAL Test TTS (port 8056)
- **Location:** `~/ai-toolbox-container-deployment/stacks/tts-v2-caal-test/`
- **Image:** Local build from `jim0237/TTS-V2-API-Server` feature branch
- **Mode:** HTTP (`TTS_USE_HTTPS=false`)
- **Status:** Healthy after healthcheck fix

---

## GitHub Actions Workflow

The repo has `.github/workflows/docker-build.yml` that:
1. Triggers on push to main
2. Builds Docker image
3. Pushes to GHCR

**Current issue:** The workflow may still be configured to push to `bmv234`'s GHCR, not `jim0237`'s. Need to verify and update if necessary.

---

## Next Steps for Production Deployment

1. **Verify GitHub Actions** - Check workflow pushes to `ghcr.io/jim0237/tts-v2-api-server`
2. **Trigger build** - Push to main to trigger image build
3. **Update production compose** - Change image from `bmv234` to `jim0237`
4. **Down + Up** in Dockge to pull new image

---

## Testing Commands

```bash
# Voice discovery
curl http://localhost:8056/v1/audio/voices

# TTS with CAAL format
curl -X POST http://localhost:8056/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"Hello world","voice":"am_puck"}' \
  --output test.wav

# Check healthcheck config
docker inspect <container-name> --format='{{json .Config.Healthcheck}}'
```

---

## Related Documentation

- `docs/CAAL_COMPATIBILITY_PLAN.md` - Detailed implementation plan
- `EXTERNAL_SERVICES_REQUIREMENTS.md` - CAAL project requirements (source of TTS requirements)
