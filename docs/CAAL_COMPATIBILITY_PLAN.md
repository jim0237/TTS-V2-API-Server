# CAAL Compatibility Plan for TTS-V2-API-Server

## Overview

Make TTS-V2-API-Server compatible with the CAAL virtual assistant project by addressing protocol requirements and API contract gaps.

---

## Current State Analysis

### What Already Works
- **POST `/v1/audio/speech`** - Endpoint exists with correct path
- **JSON request body** - Already accepts `model`, `input`, `voice`, `speed`
- **WAV audio response** - Returns `audio/wav` stream
- **Kokoro model** - Already using the required TTS engine

### Gaps to Address

| Requirement | Current State | Change Needed |
|-------------|---------------|---------------|
| HTTP protocol | HTTPS only (port 8000 with SSL) | Add HTTP support |
| Voice `am_puck` | Not in voice list | Add voice file + mapping |
| Model name `kokoro` | Only accepts `tts-1`/`tts-1-hd` | Accept `kokoro` as model |
| Direct voice IDs | Only OpenAI voice names (alloy, echo, etc.) | Accept Kokoro voice IDs directly |
| Voice discovery endpoint | Missing | Add `GET /v1/audio/voices` |

---

## Implementation Plan

### Phase 1: Protocol - Add HTTP Support

**File:** `main.py` (lines 266-275)

**Current behavior:** Only runs HTTPS on port 8000 with SSL certificates.

**Change:** Modify startup to support HTTP mode via environment variable or command-line flag.

**Options:**
1. Environment variable `TTS_USE_HTTPS=false` to run HTTP on port 8000
2. Run HTTP on different port (e.g., 8080) alongside HTTPS
3. Remove SSL config entirely when running for CAAL

**Recommendation:** Use environment variable approach - simple and doesn't require code changes to CAAL.

**Testing:**
```bash
# Start server in HTTP mode
TTS_USE_HTTPS=false python main.py

# Verify HTTP works
curl http://localhost:8000/v1/models
```

---

### Phase 2: Add Missing Voice `am_puck`

**Files to modify:**
- `main.py` - Add to `REQUIRED_FILES`, `VOICE_DESCRIPTIONS`

**Steps:**
1. Add `voices/am_puck.pt` to `REQUIRED_FILES` list (line 39-51)
2. Add `am_puck` entry to `VOICE_DESCRIPTIONS` dict (line 64-74)
3. Verify voice file downloads from HuggingFace repo

**Testing:**
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"Hello world","voice":"am_puck"}' \
  --output test_puck.wav

# Play the audio to verify it works
```

---

### Phase 3: Accept `kokoro` as Model Name

**File:** `main.py` - `AudioSpeechRequest` class and `/v1/audio/speech` endpoint

**Current:** Only validates/accepts `tts-1` and `tts-1-hd`

**Change:** Accept `kokoro` as a valid model name (treat same as `tts-1`)

**Location:** Line 25-30 (AudioSpeechRequest class) - no validation change needed since model field accepts any string. The model value is not used in processing.

**Testing:**
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"Test","voice":"am_adam"}' \
  --output test.wav
```

---

### Phase 4: Accept Direct Kokoro Voice IDs

**File:** `main.py` - `/v1/audio/speech` endpoint (lines 193-237)

**Current:** Only accepts OpenAI voice names, maps them to internal Kokoro IDs.

**Change:** Modify voice resolution logic:
1. First check if voice is a valid Kokoro ID (in `VOICE_DESCRIPTIONS`)
2. If not, try to map from OpenAI names
3. If neither, return error with available voices

**Pseudo-logic:**
```
if voice in VOICE_DESCRIPTIONS:
    internal_voice = voice  # Direct Kokoro ID
elif voice in OPENAI_VOICE_MAP:
    internal_voice = OPENAI_VOICE_MAP[voice]  # Mapped OpenAI name
else:
    raise 400 error with available voices
```

**Testing:**
```bash
# Test direct Kokoro voice ID
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"Hello","voice":"af_bella"}' \
  --output test_direct.wav

# Verify OpenAI mapping still works
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"Hello","voice":"alloy"}' \
  --output test_mapped.wav
```

---

### Phase 5: Add Voice Discovery Endpoint

**File:** `main.py` - Add new endpoint

**Endpoint:** `GET /v1/audio/voices`

**Response format (per CAAL requirements):**
```json
{
  "voices": [
    {"id": "am_puck", "name": "American Male - Puck", "language": "en-US"},
    {"id": "af_bella", "name": "American Female - Bella", "language": "en-US"},
    ...
  ]
}
```

**Implementation:** Iterate over `VOICE_DESCRIPTIONS` dict and format response.

**Testing:**
```bash
curl http://localhost:8000/v1/audio/voices

# Expected: JSON list of all available voices
```

---

## End-to-End Verification

After all phases complete, run the exact CAAL test commands from the requirements doc:

```bash
# Test TTS (matches CAAL documentation exactly)
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"kokoro","input":"Hello world","voice":"am_puck"}' \
  --output test.mp3

# Test Voice Discovery
curl http://localhost:8000/v1/audio/voices
```

---

## Files Modified

| File | Changes |
|------|---------|
| `main.py` | HTTP support, voice `am_puck`, accept direct voice IDs, voice discovery endpoint |
| `main-ui.py` | Same changes as main.py (Docker entrypoint runs this file) |
| `requirements.txt` | Pinned `kokoro==0.7.15` for model compatibility |
| `docker-compose.caal-test.yml` | New compose file for CAAL testing with HTTP healthcheck |

---

## Docker Healthcheck Fix

The Dockerfile contains an HTTPS healthcheck that causes "Invalid HTTP request received" warnings when running in HTTP mode. The `docker-compose.caal-test.yml` overrides this with an HTTP healthcheck:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/v1/models"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

**Important:** When using HTTP mode, you must either:
1. Use `docker-compose.caal-test.yml` which includes the healthcheck override
2. Or add a similar healthcheck override to your own compose file

---

## Testing Prerequisites

Testing requires a Python environment with all dependencies installed:

```bash
# Option 1: Local Python environment
pip install -r requirements.txt

# Option 2: Docker (recommended)
docker build -t tts-v2-api-server .
docker run -e TTS_USE_HTTPS=false -p 8000:8000 tts-v2-api-server
```

**Note:** The model files (~500MB) will be downloaded from HuggingFace on first startup.

---

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | HTTP protocol support (`TTS_USE_HTTPS` env var) | Complete |
| 2 | Add `am_puck` voice | Complete |
| 3 | Accept `kokoro` model name | Complete (already works) |
| 4 | Accept direct Kokoro voice IDs | Complete |
| 5 | Voice discovery endpoint (`/v1/audio/voices`) | Complete |

---

## Configuration for CAAL

Once complete, CAAL should be configured with:
```bash
KOKORO_URL=http://<server-ip>:8000
TTS_VOICE=am_puck
```
