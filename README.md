# Remote Desktop Monitoring System (RDM)

A Production-Grade Remote Desktop Monitoring Platform for Enterprise Windows Environments.
Built for organizations managing 50–100 endpoints, RDM delivers real-time screen visibility, centralized device control, policy-based monitoring, intelligent alerting, and low-latency remote stream relay through a scalable, secure architecture.
---

## 1) Project Overview

RDM consists of five coordinated layers:

1. **Desktop Agent (Windows, C++)**
	- Captures screen frames (DXGI, GDI fallback)
	- Sends heartbeat + activity logs
	- Participates in signaling/WebRTC flows

2. **Signaling Server (Node.js)**
	- WebSocket signaling broker for device-viewer communication
	- TURN credential endpoint with JWT auth
	- Per-IP connection limiting + ping/pong health

3. **Backend API (FastAPI)**
	- Authentication, RBAC, devices, logs, alerts, users, webhooks
	- SSE streaming for live alert/device updates
	- Prometheus metrics endpoint

4. **Frontend Dashboard (React + Vite)**
	- Role-aware monitoring dashboard
	- Alert center + live badge/toast updates via SSE
	- Device watch flow + admin pages

5. **Infrastructure (Docker Compose + Nginx + PostgreSQL + TURN + Monitoring)**
	- Reverse proxy, TLS, security headers, rate limiting
	- PostgreSQL persistence
	- Prometheus + Grafana observability

---

## 2) Architecture Explanation

```text
Agent (Windows PCs)
  ├─ HTTPS heartbeat/logs ─────────────► Backend API (FastAPI)
  └─ WSS signaling stream ─────────────► Signaling Server (Node)

Frontend Dashboard (React)
  ├─ REST API calls ───────────────────► Backend API
  ├─ SSE (/stream/*) ─────────────────► Backend API
  └─ WSS viewer channel ───────────────► Signaling Server

Signaling Server
  └─ TURN credentials (JWT protected) ─► coturn

Backend API
  ├─ PostgreSQL (devices/logs/alerts/users)
  ├─ Webhook delivery
  └─ Prometheus metrics

Nginx
  ├─ TLS termination
  ├─ reverse proxy to frontend/backend/signaling/grafana
  └─ request rate limiting + security headers
```

---

## 3) Full Project Structure

```text
Desktop Monitoring System/
├─ .env
├─ .github/
│  └─ workflows/
│     └─ ci.yml
├─ agent/
│  ├─ CMakeLists.txt
│  ├─ build.bat
│  ├─ rdm-agent.toml.example
│  ├─ installer.nsi
│  ├─ install-service.ps1
│  ├─ Enroll-RDMAgents.ps1
│  ├─ ops.ps1
│  ├─ pcs.csv.example
│  ├─ vcpkg.json
│  └─ src/
│     ├─ main.cpp
│     ├─ config.cpp
│     ├─ identity.cpp
│     ├─ capture/
│     ├─ encoder/
│     ├─ webrtc/
│     ├─ activity/
│     ├─ heartbeat/
│     └─ service/
├─ signaling-server/
│  ├─ Dockerfile
│  ├─ package.json
│  ├─ src/
│  │  ├─ index.js
│  │  ├─ auth.js
│  │  ├─ signaling.js
│  │  ├─ deviceManager.js
│  │  ├─ rateLimit.js
│  │  └─ turnCredentials.js
│  └─ tests/
├─ backend-api/
│  ├─ .env
│  ├─ Dockerfile
│  ├─ requirements.txt
│  ├─ pyproject.toml
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ config.py
│  │  ├─ db.py
│  │  ├─ models.py
│  │  ├─ middleware/
│  │  ├─ routes/
│  │  └─ services/
│  └─ tests/
├─ frontend/
│  ├─ Dockerfile
│  ├─ package.json
│  ├─ playwright.config.js
│  ├─ eslint.config.js
│  ├─ tailwind.config.js
│  ├─ src/
│  └─ e2e/
├─ infra/
│  ├─ docker-compose.yml
│  ├─ setup-server.sh
│  ├─ nginx/
│  ├─ postgres/
│  ├─ coturn/
│  ├─ prometheus/
│  └─ grafana/
└─ README.md
```

---

## 4) Setup Instructions (Step-by-Step)

### 4.1 Prerequisites

- Docker + Docker Compose v2
- Node.js 20+
- Python 3.12+
- (Agent build) Visual Studio 2022, CMake 3.20+, vcpkg

### 4.2 Create Environment File

1. Create `.env` in the project root and fill it with your deployment values.

2. Fill required values in `.env`:

- `JWT_SECRET` (>= 32 chars)
- `DEVICE_TOKEN_SECRET` (>= 32 chars)
- `POSTGRES_PASSWORD`
- `TURN_SECRET`
- `GRAFANA_PASSWORD`
- `DOMAIN` and `CERTBOT_EMAIL` for production TLS

Secure key generator example:

```bash
python -c "import secrets; print(secrets.token_hex(64))"
```

### 4.3 Option A (Recommended): Run Full Stack with Docker

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
```

Verify:

```bash
docker compose -f infra/docker-compose.yml ps
```

Expected endpoints:

- `https://<DOMAIN>/` (frontend)
- `https://<DOMAIN>/api/health`
- `https://<DOMAIN>/signaling/health`
- `https://<DOMAIN>/grafana/`

### 4.4 Option B: Run Services Locally (Dev)

#### PostgreSQL + infra pieces

```bash
docker compose -f infra/docker-compose.yml --env-file .env up -d postgres coturn prometheus grafana
```

#### Backend API

```bash
cd backend-api
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
# configure backend-api/.env for local backend settings
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Signaling Server

```bash
cd signaling-server
npm install
set JWT_SECRET=<same_secret_as_backend>   # PowerShell: $env:JWT_SECRET="..."
node src/index.js
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 5) Run Commands

### Docker Operations

```bash
# Start all
docker compose -f infra/docker-compose.yml --env-file .env up -d

# Rebuild + restart all
docker compose -f infra/docker-compose.yml --env-file .env up -d --build

# Stop all
docker compose -f infra/docker-compose.yml down

# View logs
docker compose -f infra/docker-compose.yml logs -f backend-api
docker compose -f infra/docker-compose.yml logs -f signaling-server
docker compose -f infra/docker-compose.yml logs -f nginx
```

### Tests

```bash
# Backend tests
cd backend-api
pytest -v

# Signaling tests
cd signaling-server
npm test

# Frontend e2e
cd frontend
npm run e2e
```

---

## 6) How to Add New Features Later

Use this extension-friendly flow:

1. **Define API contract first**
	- Add request/response models in backend route module
	- Add validation + RBAC rule

2. **Add persistence**
	- Update SQLAlchemy model + migration SQL
	- Add indexes for query paths

3. **Add service logic**
	- Keep side effects in `app/services/*`
	- Keep route handlers thin

4. **Expose to frontend**
	- Add API call in frontend data layer
	- Add page/component + role checks

5. **Real-time if needed**
	- Use SSE (`/stream/*`) for dashboard updates
	- Keep payload schema stable and versioned

6. **Tests + CI**
	- Backend pytest coverage for happy/error/RBAC paths
	- Add/extend Jest and Playwright tests
	- Ensure CI passes before merge

7. **Ops and docs**
	- Update `.env`
	- Update README sections: config, runbook, troubleshooting

---

## 7) Troubleshooting Guide

### App does not start after `docker compose up`

- Check required `.env` values are set (especially secrets)
- Check logs:
  - `docker compose -f infra/docker-compose.yml logs -f backend-api`
  - `docker compose -f infra/docker-compose.yml logs -f signaling-server`

### `JWT_SECRET must be at least 32 characters`

- Backend hard-enforces this.
- Regenerate and update both backend + signaling env.

### Frontend redirects to login repeatedly

- Ensure backend is reachable at `/api` (or `VITE_API_URL`)
- Confirm login response includes valid `token` and `user`

### Device heartbeat/log ingestion returns 401/403

- Use **device token**, not human JWT
- Ensure token `device_id` matches path/body device ID

### Signaling WebSocket not connecting

- Verify Nginx route and WS upgrade headers
- Verify `WS_MAX_CONNS_PER_IP` is not too low
- Check signaling health endpoint `/signaling/health`

### TURN credentials return 401/503

- 401: viewer token invalid/expired
- 503: missing or invalid `TURN_SECRET`

### CI fails on Node dependency step

- Run local `npm install` in `frontend` and `signaling-server`
- Commit updated package metadata if changed

---

## 8) Contributors

Primary GitHub profile for this project:

- MRLAGEND09: https://github.com/MRLAGEND09

---

## 9) Future Roadmap

This section lists the next major product and engineering milestones planned for RDM.

### 9.1 Agent Roadmap

- Add adaptive frame-rate control based on CPU, network quality, and user activity.
- Add incremental screen region updates so idle desktops do not resend full frames.
- Add application allowlist/blocklist policy enforcement pushed from the backend.
- Add offline queueing for heartbeat and activity logs when the endpoint loses connectivity.
- Add silent auto-update support for Windows agents with rollback protection.
- Add signed agent enrollment flow with device fingerprint validation.

### 9.2 Backend Roadmap

- Add Alembic migrations and upgrade/downgrade workflows for production schema changes.
- Add audit log search, retention policies, and export endpoints.
- Add device grouping, tags, and policy assignment APIs.
- Add advanced alert rules based on app usage, idle time, device offline duration, and suspicious behavior.
- Add webhook retry queue with dead-letter handling and delivery history tracking.
- Add REST pagination, filtering, and sorting across heavy list endpoints.
- Add background workers for alert fan-out, report generation, and cleanup jobs.

### 9.3 Frontend Roadmap

- Add live device map and device-health overview widgets.
- Add tenant-ready admin settings pages for policy management.
- Add alert rule builder UI and webhook management dashboard enhancements.
- Add richer device drill-down pages for activity timelines and trend charts.
- Add stream quality controls, session handoff, and view-only vs control permissions.
- Add reporting pages for productivity summaries, risk events, and per-device usage analytics.

### 9.4 Signaling and Streaming Roadmap

- Add horizontal scaling support using shared session coordination.
- Add connection quality telemetry and relay fallback analytics.
- Add stream session recording metadata for compliance workflows.
- Add TURN usage metrics and abuse throttling.
- Add viewer-device session authorization expiry and revalidation during long sessions.

### 9.5 Security Roadmap

- Add MFA for dashboard users.
- Add device certificate-based trust in addition to JWT device tokens.
- Add IP restrictions, session anomaly detection, and forced logout controls.
- Add signed webhook payload versioning and replay protection.
- Add secrets rotation runbooks and admin security audit screens.

### 9.6 Observability and Operations Roadmap

- Add production dashboards for API latency, stream health, device online rate, and alert throughput.
- Add log aggregation support with structured shipping to a central backend.
- Add backup/restore runbooks for PostgreSQL, Grafana, and persistent config.
- Add health probes for agent enrollment, webhook delivery, SSE fan-out, and TURN availability.
- Add release promotion workflow for dev, staging, and production environments.

### 9.7 Team and Collaboration Roadmap

- Add `CONTRIBUTING.md` with branch strategy, coding standards, and review rules.
- Add issue templates for bugs, feature requests, and security reports.
- Add pull request template with testing checklist and rollout notes.
- Add ownership notes for backend, frontend, signaling, infra, and agent surfaces.

### 9.8 Suggested Milestone Sequence

1. Stabilize backend CI until pytest is consistently green.
2. Add migrations and production-safe DB upgrade flow.
3. Add policy management, device grouping, and alert rule builder.
4. Add agent auto-update and secure enrollment hardening.
5. Add advanced dashboards, reports, and long-term observability.

---

## 10) GitHub Commits (Clean, Professional History)

Use this commit sequence:

1. **Initial setup**
	- `chore: initialize repository structure and base configs`

2. **Backend added**
	- `feat(backend): add FastAPI API, auth, RBAC, metrics, and tests`

3. **Frontend added**
	- `feat(frontend): add React dashboard, role-based pages, and e2e tests`

4. **Agent added**
	- `feat(agent): add Windows C++ monitoring agent with capture and signaling`

5. **Docker setup**
	- `chore(infra): add docker-compose stack, nginx, coturn, prometheus, grafana`

6. **README added**
	- `docs: add full project architecture, setup, runbook, and troubleshooting guide`

Example command sequence:

```bash
git add .
git commit -m "chore: initialize repository structure and base configs"

git add backend-api
git commit -m "feat(backend): add FastAPI API, auth, RBAC, metrics, and tests"

git add frontend
git commit -m "feat(frontend): add React dashboard, role-based pages, and e2e tests"

git add agent
git commit -m "feat(agent): add Windows C++ monitoring agent with capture and signaling"

git add infra .env .github/workflows
git commit -m "chore(infra): add docker-compose stack, nginx, coturn, prometheus, grafana"

git add README.md
git commit -m "docs: add full project architecture, setup, runbook, and troubleshooting guide"
```

---

## 11) Production Notes

- Change all default/placeholder secrets before deployment.
- Run behind TLS (Nginx + Certbot already scaffolded).
- Restrict dashboard access by IP/VPN where possible.
- Rotate JWT and TURN secrets on schedule.
- Back up PostgreSQL and Grafana volumes.

RDM is now structured to be run from `.env` configuration and extended incrementally without breaking architecture boundaries.
