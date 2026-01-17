# AI Toolbox Container Deployment

## Purpose

A Docker-based deployment system for AI/ML microservices managed via Dockge (a Docker Compose UI). Provides speech processing, translation, LLM inference, and monitoring capabilities with GPU acceleration.

## Architecture

```
ai-toolbox-container-deployment/
├── dockge/                      # Container manager UI (port 5001)
│   └── docker-compose.yml
├── stacks/                      # Individual service stacks (managed by Dockge)
│   ├── ollama/                  # Local LLM inference
│   ├── open-webui/              # Web UI for Ollama
│   ├── stt-service/             # Speech-to-Text API
│   ├── translate-service/       # Multi-language translation API
│   ├── tts-v2-service/          # Text-to-Speech API
│   ├── uptime-kuma/             # Service monitoring
│   └── voice-llama/             # Voice-enabled chat interface
└── scripts/                     # Utility scripts
    └── uptime-kuma-init/        # Auto-configures monitoring
```

## Service Reference

| Stack | Image | Port | Health Endpoint |
|-------|-------|------|-----------------|
| ollama | `ollama/ollama` | 11434 | `/api/health` |
| open-webui | `ghcr.io/open-webui/open-webui:cuda` | 3000 | `/health` |
| stt-service | Custom build (STT-API-Server fork) | 8060 | `/health` (HTTPS) |
| tts-v2-service | `ghcr.io/bmv234/tts-v2-api-server:latest` | 8055 | `/health` (HTTPS) |
| translate-service | `ghcr.io/bmv234/translate-api-server:latest` | 8070 | `/health` (HTTPS) |
| voice-llama | `ghcr.io/bmv234/voice-llama:latest` | 8443 | `/health` |
| uptime-kuma | `louislam/uptime-kuma:1` | 3001 | N/A |

## Compose File Conventions

### GPU Support (Required for AI services)

All AI/ML services must include NVIDIA GPU reservation:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: 1
          capabilities: [gpu]
```

### Volume Naming Pattern

Services use named volumes for persistence:
- `{service}_data` - Primary data storage
- `{service}_models` - ML model cache
- `{service}_cache` - Runtime cache

Example:
```yaml
volumes:
  tts_models:
  tts_cache:
```

### Port Mapping

Internal services typically run on port 8000; external ports are mapped uniquely:
- AI APIs: 8055-8070 range
- Web UIs: 3000-3001, 5001

### Restart Policy

All services use:
```yaml
restart: unless-stopped
```

### Container Naming

Containers are explicitly named matching their stack:
```yaml
container_name: tts-v2-service
```

## Adding a New Service

1. Create directory: `stacks/{service-name}/`
2. Create `compose.yaml` with:
   - Explicit `container_name`
   - Named volumes (not bind mounts, except for host data sharing)
   - GPU support if ML-based
   - `restart: unless-stopped`
   - Health endpoint if possible
3. Add monitor to `scripts/uptime-kuma-init/init.py` if service has health check

## Example Compose Template

```yaml
services:
  my-service:
    image: ghcr.io/org/my-service:latest
    container_name: my-service
    ports:
      - "8080:8000"
    volumes:
      - my_service_data:/app/data
      - my_service_models:/app/models
    environment:
      - LOG_LEVEL=info
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  my_service_data:
  my_service_models:
```

## Key Implementation Details

- **Dockge** manages stacks by scanning the `stacks/` directory
- **STT service** builds from a forked repo (not pre-built image) with modular frontend support
- **Voice notes** use host mount (`/home/agnes/voice-notes`) for external access
- **HTTPS services** (STT, TTS, Translation) use self-signed certificates
- **Uptime-Kuma** monitors all services with 30-second intervals; SSL verification disabled for self-signed certs

## Network

Services communicate via Docker's default bridge network. No custom networks are defined; services reference each other by container name when needed.
