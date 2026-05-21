# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Carter Island Web is a full-stack dashboard for an Autonomous Underwater Vehicle (AUV/ROV). It displays live video streams, water quality telemetry, fish detection results, and mission recordings. The system consists of a Next.js 15 frontend and a Python FastAPI backend that communicates with physical ROV hardware.

## Commands

### Frontend (Next.js)

```bash
npm run dev       # Development server with Turbopack at http://localhost:3000
npm run build     # Production build with Turbopack
npm run start     # Start production server
npm run lint      # ESLint check
```

### Backend (FastAPI)

The backend lives in `src/backend/`. Run from that directory:

```bash
cd src/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Database

```bash
npm run db:seed   # Seed MySQL database (runs prisma/seed.ts via tsx)
# OR directly:
cd src/backend && python seed.py
```

## Architecture

### Two-Service System

The app requires both services running simultaneously:
- **Frontend** — Next.js on port 3000
- **Backend** — FastAPI on port 8000 (configured via `NEXT_PUBLIC_BACKEND_URL`)

Additionally, `mediamtx.exe` (root directory) must run for RTSP video relay when using live streaming.

### Frontend Structure

**App Router layout** (`src/app/`):
- `/` redirects to `/auth/login`
- `/auth/login` — unauthenticated entry point
- `/dashboard/*` — all protected routes, wrapped in `src/app/dashboard/layout.tsx` which calls `requireAuth()`

**Authentication** is JWT-based using cookies. The key utilities are:
- `src/lib/auth-utils.ts` — `requireAuth()` (server-side redirect), `requireAdmin()`, `hasRole()`, JWT decoding from `access_token` cookie
- `src/lib/api-client.ts` — centralized fetch wrapper that injects `Authorization: Bearer <token>` on all requests

**Data fetching pattern**: Server components use `requireAuth()` then pass the session to client components. Client components use SWR with the API client for live data.

**Role-based UI**: The Sidebar (`src/components/layout/Sidebar.tsx`) filters navigation items based on role. The Users section is ADMIN-only.

### Backend Structure

`src/backend/` is a standalone FastAPI application:

```
main.py           # App entry, CORS config, router registration, APScheduler lifespan
config.py         # All env vars loaded here (DATABASE_URL, JWT_SECRET, RTSP settings, sync config)
database/
  models.py       # SQLAlchemy ORM models (source of truth for DB schema)
  connection.py   # Engine + session factory
  crud/           # Database operations
routers/          # One file per domain (auth, users, telemetry, auv_status, detections,
                  # recordings, analytics, sessions, fish_counts, sync)
schemas/          # Pydantic DTOs for request/response validation
models/
  yolo_detector.py  # YOLOv8 wrapper loading 16sept.pt (custom fish detection model)
video/            # Recording lifecycle and frame-level detection tracking
webrtc/           # WebRTC peer connection offer/answer handling
```

### Database Models (MySQL via SQLAlchemy)

Core entities and their relationships:
- `User` → has role `USER` or `ADMIN`
- `MonitoringSession` → belongs to User; status is `Running`, `Completed`, or `Aborted`
- `Telemetry` → per-session rows with pH, TDS, dissolved_oxygen, water_temp, depth, is_synced
- `AUVStatus` → per-session ROV attitude (roll, pitch, yaw, heading, gyroscope, accelerometer, magnetometer)
- `Detection` → per-session fish detections with species_name, confidence, depth_at_detection, frame_number, is_synced
- `FishCount` → per-session species aggregate counts
- `VideoPath` → file metadata for recorded videos
- `VideoStream` → WebRTC session config

### Environment Variables

Required in `.env` at project root:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | MySQL connection string (`mysql://user:pass@host:port/db`) |
| `JWT_SECRET` / `JWT_SECRET_KEY` | JWT signing (both must match) |
| `NEXT_PUBLIC_BACKEND_URL` | FastAPI URL used by browser (`http://localhost:8000`) |
| `NEXT_PUBLIC_API_URL` | Same as above |

Optional backend-only variables (RTSP stream, YOLO thresholds, sync config) are documented in `src/backend/config.py`.

### SPPI Sync Protocol

`src/backend/routers/sync.py` implements SPPI 45-47 — a protocol for pushing ROV telemetry and detections from the ROV station to a remote Base Station. Rows with `is_synced=False` are queued and sent via `BASE_STATION_URL` using `BASE_STATION_SYNC_TOKEN`. Background sync runs on `SYNC_INTERVAL_SECONDS` via APScheduler.

### Adding shadcn/ui Components

This project uses shadcn/ui with the `new-york` style, `zinc` base color, and CSS variables. Add components with:

```bash
npx shadcn@latest add <component-name>
```

Components land in `src/components/ui/`.

## Rules

- Gunakan Bahasa Indonesia Untuk percakapan disini
- Setiap perubahan kode harus konfirmasi ke saya terlebih dahulu sebelum dieksekusi
- Setiap commit harus konfirmasi ke saya terlebih dahulu
- Jika ada pertanyaan terkait UI/UX, jawab dari perspektif sebagai user/pengguna
- Untuk UI/UX jangan diubah dulu untuk sekarang rapihkan Backend nya saja dulukerjain yang backn