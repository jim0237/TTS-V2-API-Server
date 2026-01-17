# Deployment Differences: STT-API-Server vs TTS-V2-API-Server

## Executive Summary

| Aspect | STT-API-Server | TTS-V2-API-Server |
|--------|----------------|-------------------|
| **Source Code Location** | Cloned locally on server (`~/STT-API-Server/`) | Not on server (pulled from GHCR) |
| **Build Method** | Local Docker build from source | Pre-built image from GHCR |
| **Update Workflow** | `git pull` + `docker compose build` | Change image tag + `docker compose up` |
| **Compose File Location** | `~/ai-toolbox-container-deployment/stacks/stt-service/compose.yaml` | `~/ai-toolbox-container-deployment/stacks/tts-v2-service/` |
| **Image Source** | Built locally from Dockerfile | `ghcr.io/bmv234/tts-v2-api-server:latest` (or `jim0237` fork) |
| **GitHub Actions** | None (local build only) | Yes - auto-publishes to GHCR on push |

**Key Difference**: STT uses a **local build workflow** (source code on server), while TTS uses a **GHCR pull workflow** (pre-built images, no source on server).

---

## Detailed Comparison

### 1. Where Files Live

#### STT-API-Server

| File Type | Location |
|-----------|----------|
| Source Code | **On server**: `~/STT-API-Server/` (cloned from GitHub) |
| Dockge Compose File | `~/ai-toolbox-container-deployment/stacks/stt-service/compose.yaml` |
| Local Compose File | `~/STT-API-Server/docker-compose.yml` (exists but NOT used by Dockge) |
| Dockerfile | `~/STT-API-Server/Dockerfile` |

#### TTS-V2-API-Server

| File Type | Location |
|-----------|----------|
| Source Code | **NOT on server** - only exists in GitHub repo |
| Dockge Compose File | `~/ai-toolbox-container-deployment/stacks/tts-v2-service/` |
| CAAL Test Compose | `~/ai-toolbox-container-deployment/stacks/tts-v2-caal-test/` |
| Local Compose File | In GitHub repo only (`docker-compose.caal-test.yml`) |
| Dockerfile | In GitHub repo only - used by GitHub Actions to build GHCR image |

---

### 2. How Images Are Built/Obtained

#### STT-API-Server (Local Build)

```
GitHub Repo ──git clone──> ~/STT-API-Server/ ──docker build──> Local Image ──run──> Container
                                    │
                             (git pull for updates)
```

- The Dockge `compose.yaml` uses `build:` directive with relative path to source:
  ```yaml
  services:
    stt-api:
      build:
        context: ../../../STT-API-Server
        dockerfile: Dockerfile
  ```
- Image is built on the server from local source code
- No external image registry involved

#### TTS-V2-API-Server (GHCR Pull)

```
GitHub Repo ──push to main──> GitHub Actions ──build & push──> GHCR ──docker pull──> Server Container
```

- The compose file uses `image:` directive pointing to GHCR:
  ```yaml
  services:
    tts-api:
      image: ghcr.io/bmv234/tts-v2-api-server:latest
  ```
- Image is pre-built by GitHub Actions and stored in GitHub Container Registry
- Server pulls pre-built image (no local build required)

---

### 3. Update Workflows

#### Updating STT-API-Server

```bash
# Step 1: Pull latest code from GitHub
cd ~/STT-API-Server
git pull origin main

# Step 2: Rebuild container (source changed locally)
cd ~/ai-toolbox-container-deployment/stacks/stt-service
docker compose build --no-cache stt-api

# Step 3: Restart with new build
docker compose up -d stt-api
```

**Key points:**
- Must SSH to server
- Must run `git pull` to get code changes
- Must rebuild image locally
- `--no-cache` flag needed to ensure fresh build

#### Updating TTS-V2-API-Server

```bash
# Step 1: Wait for GitHub Actions to build new image (automatic on push to main)

# Step 2: Pull new image and restart
cd ~/ai-toolbox-container-deployment/stacks/tts-v2-service
docker compose pull
docker compose up -d
```

Or in Dockge:
1. Click "Down" on the stack
2. Click "Up" to pull and start new image

**Key points:**
- Code changes trigger GitHub Actions automatically
- Server just pulls the new pre-built image
- No source code on server to manage
- No local build step

---

### 4. Compose File Comparison

#### STT Dockge Compose (`~/ai-toolbox-container-deployment/stacks/stt-service/compose.yaml`)

```yaml
services:
  stt-api:
    build:
      context: ../../../STT-API-Server    # <-- LOCAL SOURCE DIRECTORY
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - 8060:8000
    volumes:
      - stt_models:/app/models
      - stt_cache:/app/cache
      - /home/agnes/voice-notes:/app/vnotes
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities:
                - gpu
```

#### TTS Dockge Compose (Production)

```yaml
services:
  tts-api:
    image: ghcr.io/bmv234/tts-v2-api-server:latest    # <-- GHCR IMAGE
    restart: unless-stopped
    ports:
      - 8055:8000
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities:
                - gpu
```

#### TTS CAAL Test Compose (Local Build for Testing)

```yaml
services:
  tts-api:
    build:
      context: .                           # <-- LOCAL BUILD (testing only)
      dockerfile: Dockerfile
    environment:
      - TTS_USE_HTTPS=false
    ports:
      - 8056:8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/models"]
```

---

### 5. When to Use Each Approach

| Scenario | STT Approach (Local Build) | TTS Approach (GHCR Pull) |
|----------|---------------------------|--------------------------|
| **Single server deployment** | Good | Good |
| **Multi-server deployment** | Harder (must clone to each) | Easier (all pull same image) |
| **Quick development iteration** | Good (immediate rebuild) | Slower (wait for CI) |
| **Production stability** | Riskier (manual builds) | Safer (CI-tested images) |
| **Rollback** | `git checkout <commit>` + rebuild | Change image tag |
| **Server disk space** | More (source + built image) | Less (only image) |
| **Dependencies on server** | Git required | Only Docker required |

---

### 6. Summary Table

| Aspect | STT-API-Server | TTS-V2-API-Server |
|--------|----------------|-------------------|
| **Port** | 8060 | 8055 (prod), 8056 (CAAL test) |
| **Protocol** | HTTPS (self-signed) | HTTPS (prod), HTTP (CAAL test) |
| **GitHub Repo** | `jim0237/STT-API-Server` | `jim0237/TTS-V2-API-Server` (fork of `bmv234`) |
| **GitHub Actions** | No | Yes |
| **GHCR Image** | No | Yes (`ghcr.io/bmv234/tts-v2-api-server`) |
| **Source on Server** | Yes (`~/STT-API-Server/`) | No |
| **Build Location** | Server | GitHub Actions (CI) |
| **Update Trigger** | Manual `git pull` | Push to `main` branch |
| **Dockge Stack Path** | `stacks/stt-service/` | `stacks/tts-v2-service/` |

---

## Recommendations

### If Standardizing on One Approach

**Option A: Use GHCR Pull for Both (Recommended for Production)**
- Add GitHub Actions workflow to STT-API-Server
- Update STT Dockge compose to use `image:` instead of `build:`
- Remove source code from server
- Pros: Consistent, easier multi-server, CI-tested images

**Option B: Use Local Build for Both (Recommended for Development)**
- Clone TTS-API-Server source to server
- Update TTS Dockge compose to use `build:` with local path
- Pros: Immediate iteration, no CI wait time
- Cons: Source code management on server, manual builds

### Current State

The current hybrid approach works but requires different mental models:
- **STT updates**: SSH → git pull → docker build → up
- **TTS updates**: Wait for CI → docker pull → up (or just down/up in Dockge)
