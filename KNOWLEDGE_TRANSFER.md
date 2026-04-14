# Healoncal — Knowledge Transfer

A single document to onboard a new engineer end-to-end: what the system is,
where the code lives, how it's deployed, how a request flows, what the
moving pieces are, what's been tuned, and what's next.

Companion document: `PERFORMANCE_OPTIMIZATIONS.md` (a chronological history
of every latency fix). This file is the "what you need to know to own it"
doc.

---

## 1. What is Healoncal?

A medical-grade skin-analysis booth / web app.

**User flow (happy path):**

1. User opens healoncal.com in a browser.
2. Answers a short onboarding questionnaire.
3. Uses the camera to capture three selfies (**front**, **left**, **right**).
4. Backend analyses the three images, detects skin conditions, generates
   per-disease heatmap overlays on the user's own photos, and produces
   personalised product recommendations.
5. User lands on a report page showing metrics per angle, disease
   confidence, heatmap overlays, and a recommended routine.

Live URL: **https://healoncal.com**

---

## 2. Repos and branches

There are **two** GitHub repos plus a **deploy directory** that lives only
on the production VM.

| Name | Repo | Role | Current working branch |
|---|---|---|---|
| Frontend | `yashch-hoc/hoc-demo` (package name `hoc-booth`) | Vite + React 19 + Tailwind 4 + MediaPipe | `perf-streaming-ui` (PRs into `pihu-ui-fix`) |
| Backend | `yashch-hoc/healoncal-microservices` | FastAPI / Python 3.12 / MySQL / S3 / Gemini | `perf-optimizations` (PRs into `main`) |
| Deploy | **not in git** — lives at `/home/ubuntu/healoncal/deploy/` on the VM | docker-compose, nginx, TLS certs | N/A |

The "hoc-demo" frontend replaced an older "hoc-pod" frontend during the
perf work — the old code is still on disk at `/home/ubuntu/healoncal/hoc-pod/`
as a safety backup. Keep it; don't delete.

On the VM the working trees are:

```
/home/ubuntu/healoncal/
├── deploy/                    # docker-compose + nginx + TLS (NOT in git)
├── healoncal-microservices/   # backend clone
├── hoc-demo/                  # frontend clone (live)
├── hoc-pod/                   # OLD frontend backup, no longer deployed
├── PERFORMANCE_OPTIMIZATIONS.md
└── KNOWLEDGE_TRANSFER.md      # this file
```

---

## 3. System architecture

```
                    ┌────────────────────────────────┐
                    │   Browser (React + MediaPipe)  │
                    └──────────────┬─────────────────┘
                                   │  HTTPS / SSE
                                   ▼
               ┌─────────────────────────────────────────────┐
               │  nginx 1.27  (TLS termination, H2, SSE      │
               │  passthrough with proxy_buffering off)      │
               └───┬───────────────────────────┬─────────────┘
                   │ /                          │ /api/healoncal/
                   ▼                            ▼
       ┌──────────────────────┐      ┌──────────────────────────┐
       │  frontend container  │      │  backend container       │
       │  (nginx serving      │      │  FastAPI + uvicorn       │
       │   built Vite dist/)  │      │  2 worker procs          │
       └──────────────────────┘      │  + ProcessPoolExecutor   │
                                     │  (3 analysis workers)    │
                                     └───┬─────────┬────────┬───┘
                                         │         │        │
                                         │         │        │
                                         ▼         ▼        ▼
                                    ┌────────┐ ┌──────┐ ┌────────┐
                                    │ MySQL  │ │  S3  │ │ Gemini │
                                    │ 8.0    │ │ (web │ │ 2.5    │
                                    │(local) │ │ bkt) │ │ Flash  │
                                    └────────┘ └──────┘ └────────┘
```

Everything except S3 + Gemini runs on the single VM (`docker compose`
orchestrated). MySQL is **in the same compose project** — not a managed
RDS instance.

---

## 4. Quick start (local development)

### Prereqs
- Docker + `docker compose` plugin
- GitHub SSH access to both repos (public key added to the GitHub account)

### Clone + bring up

```bash
mkdir healoncal && cd healoncal
git clone git@github.com:yashch-hoc/healoncal-microservices.git
git clone -b pihu-ui-fix git@github.com:yashch-hoc/hoc-demo.git
# /deploy/ lives on the VM; copy it from there or ask the team.
cd deploy
docker compose up -d --build
```

Then hit **https://localhost** (self-signed cert — accept the warning).

### Front-end dev server (hot reload)

```bash
cd hoc-demo
npm install
npm run dev  # vite on http://localhost:5177
```

Vite proxies nothing — the app talks to the absolute API URL baked in
via `VITE_API_BASE_URL`. For local FE dev against the running backend,
either:

- set `VITE_API_BASE_URL=/api/healoncal` and put a proxy in
  `vite.config.ts`, or
- hit the deployed `https://healoncal.com/api/healoncal` directly (with
  CORS enabled).

### Backend iteration

Edit Python, then:

```bash
cd deploy
docker compose up -d --build backend
# ~15s rebuild; another ~15s warmup as the process pool spawns.
docker compose logs backend -f | grep -E "warmed|PARALLEL|ERROR"
```

### Health check

```bash
curl -sk https://localhost/api/healoncal/health
```

---

## 5. Production deployment

### Where the prod code lives

- Host: the VM running docker. Working tree at `/home/ubuntu/healoncal/`.
- Source of truth is Git for both repos. `deploy/` is hand-maintained
  on the VM.

### Deploy flow

```bash
# Pull latest
cd /home/ubuntu/healoncal/healoncal-microservices && git pull
cd /home/ubuntu/healoncal/hoc-demo              && git pull

# Rebuild + recreate containers. Backend warmup is ~15s.
cd /home/ubuntu/healoncal/deploy
docker compose up -d --build backend frontend
```

### TLS

- Origin cert: `deploy/nginx/certs/origin.{crt,key}`
- TLS is terminated by the `nginx` container.
- For Let's Encrypt, the `.well-known/acme-challenge/` path is
  already wired in nginx.conf — but we currently use the static origin
  cert, not ACME.

### nginx SPA + API split

- `/` → `frontend` service (serves built Vite `dist/`). COOP/COEP
  headers set for MediaPipe cross-origin isolation.
- `/api/healoncal/` → `backend` service on port 8080. `proxy_buffering
  off` so SSE streams cleanly.

### Rollback

We don't tag Docker images, so the cheap option is:
1. Check out the last-known-good git SHA on the VM.
2. `docker compose up -d --build`.

For a faster rollback, **tag images before recreating**:

```bash
docker tag healoncal-backend:latest healoncal-backend:before-$(date +%s)
```

---

## 6. Frontend tour

**Stack:** Vite 8 (beta), React 19, TypeScript, Tailwind v4, zustand,
react-router 6/7, MediaPipe tasks-vision, axios, framer-motion, recharts,
lucide-react.

### Routes (`src/App.tsx`)

| Path | Component | Purpose |
|---|---|---|
| `/` | `HomePage` | Landing + CTA |
| `/question` | `QuestionPage` | Short questionnaire before capture |
| `/capture` | `CapturePage` | Camera + MediaPipe face detection, triggers submit |
| `/report` | `ReportPage` | Renders analysis + heatmaps + recommendations |

### Key components

- `src/Page/CapturePage.tsx` — owns the camera lifecycle, face landmarking
  via MediaPipe, and triggers `submitAnalysisStream` on the three captured
  blobs. Navigates to `/report` on the first `results` SSE event.
- `src/components/report/SkinAnalysisPanel.tsx` — per-angle view. Shows the
  user's captured photo for that angle (falls back to `/face-<angle>.png`
  placeholder if the backend hasn't attached a captured_image_url yet).
- `src/api/uploadSession.ts` — two API calls:
  - `submitAnalysisAPI` / `uploadAndSubmit` — classic one-shot JSON.
  - `submitAnalysisStream` — SSE consumer with callbacks.
- `src/store/reportStore.ts` — zustand store with
  `setReportData({userId, report})`, `patchReport(partial | updater)`,
  `clearReportData()`.

### MediaPipe WASM

MediaPipe needs its own WASM files accessible at runtime. We copy them
out of `node_modules` into `public/wasm/` via a postinstall script
(`scripts/copy-mediapipe-wasm.mjs`) that runs on every `npm install`.
The Dockerfile for the frontend skips postinstall during `npm ci`, then
runs it explicitly after source copy — see `deploy/Dockerfile.frontend`.

### Build-time API URL

`VITE_API_BASE_URL` is **inlined at build time**. In production we build
with `VITE_API_BASE_URL=/api/healoncal` so axios hits nginx, which proxies
to the backend. The default in `src/api/uploadSession.ts:11` is an
older hard-coded Cloud Run URL — only relevant for local dev.

---

## 7. Backend tour

**Stack:** Python 3.12, FastAPI, uvicorn, PyMySQL, boto3, Pillow, numpy,
OpenCV, google-genai, Sentry.

### Entrypoint

`app/main_healoncal.py` — FastAPI app with a lifespan context manager that:
- Loads secrets
- Initializes MySQL client
- **Pre-warms the analysis ProcessPool** (three workers, `spawn`
  context, each of which pre-imports cv2/numpy and pre-loads the Haar
  cascade — so the first real request doesn't pay spawn cost)

The Dockerfile runs uvicorn with `--workers 2`. That means you have 2 FastAPI
processes, each with its own 3-worker ProcessPool = 8 backend processes
at steady state.

### Key services (`app/services/`)

| File | Role |
|---|---|
| `healoncal_service.py` | Core analysis orchestration. Owns the ProcessPool, `analyze_session`, `capture_image`, per-image sync analyzer, 30+ metric calculators, disease detector, heatmap trigger. |
| `heatmap_visualization_service.py` | All PIL rendering + per-disease overlay math. The vectorized `_draw_speckle_overlay` lives here. |
| `gemini_recommendation_service.py` | Wraps `google-genai`. Module-level singleton, eager-initialized at import. |
| `s3_storage_service.py` | AWS S3 client (cached boto3 client, 32-conn pool). Provides `upload_image`, `download_image`, `delete_object_key`, `get_signed_url`. (File was renamed from `gcs_storage_service.py` — purely a name change; it was always S3 under the hood.) |
| `mysql_client_service.py` | Thin PyMySQL wrapper. `insert`, `bulk_insert`, `execute`, `fetch_all`, `fetch_one`, JSON+bool coercion via `_row_for_insert`. |
| `treatment_storage_service.py` | Writes detected diseases + treatment recommendations to MySQL. Uses `bulk_insert` for diseases. |
| `metrics_service.py` | Observability / in-memory request metrics. |
| `report_chat_service.py` | Backs `POST /chat-on-report` (RAG chat over a finished report). |

### Endpoints (`app/api/endpoints/healoncal_analysis.py`)

```
POST  /api/healoncal/capture
POST  /api/healoncal/analyze
GET   /api/healoncal/diagnostic/schema
GET   /api/healoncal/results/{session_id}
GET   /api/healoncal/session/{user_id}/latest
GET   /api/healoncal/heatmaps/{session_id}
POST  /api/healoncal/submit-and-analyze          # classic JSON
POST  /api/healoncal/submit-and-analyze/stream   # SSE (recommended)
POST  /api/healoncal/chat-on-report
GET   /api/healoncal/health
POST  /api/healoncal/recommendations
POST  /api/healoncal/complete-analysis
# + a few /metrics/* endpoints
```

The frontend currently only uses `submit-and-analyze/stream`. The classic
`/submit-and-analyze` remains for backwards compatibility and debugging.

---

## 8. The `/submit-and-analyze` pipeline

### Classic JSON (`POST /submit-and-analyze`)

```
┌─────────────────────────────┐
│ 1. read + validate 3 files  │  gather()
├─────────────────────────────┤
│ 2. create session           │
├─────────────────────────────┤
│ 3. capture 3 images → S3    │  gather() of capture_image()
│    + write metadata rows    │  (S3 PUT + quality assess in thread)
├─────────────────────────────┤
│ 4. analyze_session(...)     │  ProcessPool, 3 workers
│    - pull captured images   │
│    - per-image pipeline:    │
│      quality → biomarkers → │
│      30+ metrics → disease  │
│      detection              │
│    - write analysis_results │
│    - write detected_diseases│  bulk_insert
│    - spawn heatmap tasks    │  3 × asyncio.create_task
│    - await all heatmaps     │
├─────────────────────────────┤
│ 5. fetch heatmaps from DB   │
│ 6. Gemini recs (parallel)   │  asyncio.gather(fetch_heatmaps, gemini)
├─────────────────────────────┤
│ 7. build response JSON      │
└─────────────────────────────┘
```

### SSE (`POST /submit-and-analyze/stream`) — preferred

Same pipeline, but heatmap generation is **not** awaited inside
`analyze_session`. Instead the endpoint drives heatmaps per-angle itself
and emits events as each finishes.

```
Event            Payload                                 Fires at
-------------    --------------------------------------  --------
progress         {stage: "validating"}                     0s
progress         {stage: "session_created", session_id}    ~0.2s
progress         {stage: "captured"}                       ~1–2s
progress         {stage: "analyzing"}                      ~1–2s
results          {session_id, results}                     ~5–7s
heatmap_angle    {angle, <angle>: {...}}                   ~6–9s (×3)
recommendations  {recommendations}                         ~8–12s
heatmaps         {heatmaps: {...}}  (full consolidated)    end
done             {session_id, processed_images}            end
error            {error: str}                              on failure
```

Real measurement from logs (single trace after all perf work + capture fix):

- Captures: ~0.7s (true 3-way parallel)
- Analysis: ~3.9s (parallel across 3 processes, max of 3 images)
- Heatmap gen + WebP upload (21 overlays): ~3.7s (parallel across angles)
- **Time-to-`results` event: ~5s**
- **Time-to-all-heatmaps: ~9s**

### Where "heatmap for disease X on angle Y" comes from

1. `_detect_skin_diseases(metrics, image_np)` returns a list of
   `{name, category, confidence, severity, ...}` for each image.
2. Top 7 diseases per angle (by severity + confidence) are kept.
3. For each `(angle, disease)` pair,
   `heatmap_visualization_service._create_disease_heatmap_on_image`:
   - Calls `_calculate_heatmap_regions_for_angle` to decide affected
     regions (face zones per angle).
   - Calls `_generate_pinpoint_heatmap_overlay` which builds a PIL
     RGBA overlay and calls the **vectorized** `_draw_speckle_overlay`
     to paint ~450 speckles per heatmap in one numpy pass.
   - `_add_disease_info_overlay_with_angle` paints the disease label.
4. One combined heatmap per angle is rendered concurrently with the
   per-disease ones.
5. Each heatmap is encoded as **WebP** (quality 82) and uploaded to S3.
6. A row goes into `disease_heatmaps` with `heatmap_url`,
   `heatmap_type` ("individual" or "combined"), colors JSON, etc.

### Angle detection from heatmap URL — sharp edge

`_fetch_heatmaps_for_session` currently decides which angle a heatmap
belongs to by **substring matching on the URL** (`_front_`, `_left_`,
`_right_`). If a filename convention changes, this silently misroutes.
Long-term fix: store `angle` as its own column on `disease_heatmaps`.

---

## 9. MySQL schema — the tables you'll touch most

- `healoncal_analysis_sessions` — one row per scan session.
  Columns include `id` (UUID), `user_id`, `status`
  (`pending`/`ready`/`completed`/`failed`), `total_images`,
  `processing_time_ms`, `created_at`, `completed_at`.
- `healoncal_captured_images` — one row per photo.
  `id`, `session_id`, `user_id`, `angle` (`front|left|right`),
  `image_url` (S3 URL), `quality_score`, `face_detected`.
- `healoncal_analysis_results` — per-image metric dump.
  `id`, `session_id`, `user_id`, `image_id`, `angle`,
  `diagnostic_accuracy`, `biomarkers_analyzed`,
  a large set of `*_score` columns, `processing_time_ms`, `model_version`.
- `detected_skin_diseases` — one row per detected disease per image.
  `id`, `session_id`, `analysis_result_id`, `user_id`, `disease_name`,
  `disease_category`, `confidence_score`, `severity_level`,
  `affected_area`, `symptoms_noted` (JSON), `requires_medical_attention`.
- `disease_heatmaps` — one row per rendered overlay.
  `id`, `session_id`, `heatmap_url` (S3), `disease_name`, `heatmap_type`,
  `colors` (JSON), `heatmap_index`.
- `treatment_recommendations` — one row per session with Gemini output.
  `id`, `session_id`, `products` (JSON), `routine_steps` (JSON),
  `key_advice` (JSON / text).

The authoritative SQL is in `healoncal-microservices/Healoncal_database_mysql.sql`
and the container-init scripts in `deploy/mysql-init/`.

---

## 10. S3 layout

Bucket: `healoncal-web` (ap-south-1). All objects are private; browser
access goes through time-limited presigned URLs produced by
`s3_storage_service.get_signed_url`.

```
healoncal-web/
└── skin-scans/                                # S3_PREFIX
    └── users/<user_id>/healoncal/<session_id>/
        ├── front_<ts>.jpg                     # captured image
        ├── left_<ts>.jpg
        ├── right_<ts>.jpg
        └── heatmaps/
            ├── heatmap_<disease>_<angle>_<i>_<ts>.webp
            └── combined_heatmap_<angle>_<ts>.webp
```

---

## 11. Environment variables

### Backend (`deploy/backend.env`)

| Var | Purpose |
|---|---|
| `MYSQL_*` | DB creds (database, user, password). Consumed by mysql container + backend. |
| `S3_BUCKET_NAME` | `healoncal-web`. |
| `S3_PREFIX` | `skin-scans`. Legacy alias: `GCS_SKIN_SCANS_PREFIX`. |
| `AWS_REGION` | `ap-south-1`. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | IAM user creds. On EC2 with an instance role these can be omitted. |
| `GEMINI_API_KEY` | google-genai key. Required in prod; if missing, eager init logs a warning and the service returns `{success: false, error: ...}` for recs. |
| `GEMINI_MODEL_NAME` | Defaults to `gemini-2.5-flash`. |
| `GEMINI_TIMEOUT_SECONDS` | Defaults to `35`. |
| `HEALONCAL_ANALYSIS_WORKERS` | Size of the analysis ProcessPool. Default **3** (one per angle). |
| `HEALONCAL_ANALYSIS_MAX_DIM` | Longest-side cap (px) for analysis-path downscale. Default **512**. |
| `SENTRY_DSN` | Optional. |

### Frontend (build-time, `deploy/.env`)

| Var | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Baked into the bundle. In prod set to `/api/healoncal`. |

---

## 12. Observability / logs

### Where they are

```bash
docker compose logs -f backend      # all backend output
docker compose logs -f nginx        # access + error
docker compose logs -f mysql
```

### Log markers worth knowing

- `[HEALONCAL POOL] Initialized ProcessPoolExecutor with 3 workers (spawn)` — backend booted.
- `🔥 Analysis process pool warmed up (3 workers)` — warmup done; backend is ready to serve with low first-request latency.
- `[HEALONCAL PARALLEL] Total parallel processing time: X.XXs (Download: ..., Analysis: ..., Storage: ...)` — one-line summary of the heavy path.
- `[HEALONCAL SUCCESS] Analysis completed - Accuracy: Y%, Biomarkers: N, Time: Xs` — per-image analysis time.
- `[HEATMAP PARALLEL] Starting/Completed parallel heatmap generation for <angle>` — heatmap lifecycle.
- `[S3 STORAGE] Upload successful: <key>` — every S3 PUT.
- `[HEALONCAL STREAM] ...` — SSE endpoint lifecycle + failures.

### Quick perf check

```bash
docker compose logs backend --since 30m \
  | grep -E "Total parallel processing time|All analyses completed|HEATMAP PARALLEL Completed" \
  | tail -20
```

---

## 13. Performance work history

This project's `/submit-and-analyze` was **45–70s** end-to-end. After
seven rounds of tuning it is ~**5s to first content / ~10s complete**
(including 21 heatmaps + Gemini recs).

Detailed change log in **`PERFORMANCE_OPTIMIZATIONS.md`**. Highest-impact
items at a glance:

1. **ProcessPoolExecutor for per-image analysis** — true CPU parallelism.
2. **Analysis-path image downscale to 512px** — cv2 ops cost scales with
   pixels; downscaling didn't change results but cut per-image CPU by
   ~10–50×.
3. **Process-pool pre-warm at FastAPI lifespan** — hides ~15s spawn cost.
4. **SSE streaming + progressive UI** — metrics render at ~5s, heatmaps
   slot in per-angle as they arrive.
5. **Vectorized speckle overlay** — replaced ~9,500 PIL `draw.ellipse`
   Python calls with one numpy composite.
6. **WebP heatmaps** instead of PNG — ~3–5× smaller S3 bodies.
7. **Cached boto3 S3 client + 32-conn pool** — boto client rebuild cost
   dominated at ~27 storage ops/request.
8. **Parallel image captures** — `asyncio.to_thread` wrapping S3 PUT and
   Haar quality assessment inside `capture_image`, so the outer
   `asyncio.gather` actually overlaps.
9. **Batched `detected_diseases` INSERT** via `mysql_client.bulk_insert`.
10. **Gemini client eager init at module load**.

---

## 14. Runbook / common operations

### Deploy a new frontend build

```bash
cd /home/ubuntu/healoncal/hoc-demo
git pull --ff-only
cd /home/ubuntu/healoncal/deploy
docker compose up -d --build frontend
```

### Deploy a new backend build

```bash
cd /home/ubuntu/healoncal/healoncal-microservices
git pull --ff-only
cd /home/ubuntu/healoncal/deploy
docker compose up -d --build backend
# wait for warmup
until docker compose logs backend --tail=30 | grep -q "Application startup complete"; do sleep 2; done
```

### Tail prod logs for a live request

```bash
docker compose logs backend -f --tail=0 \
  | grep -E "STREAM|PARALLEL|HEATMAP|ERROR"
```

### Reset the database (nuclear)

```bash
cd /home/ubuntu/healoncal/deploy
docker compose down -v   # removes mysql_data volume
docker compose up -d     # re-runs mysql-init/*.sql
```

### Rotate TLS cert

Drop a new `origin.crt`/`origin.key` into `deploy/nginx/certs/`, then:

```bash
docker compose exec nginx nginx -s reload
```

### Adjust analysis parallelism / downscale size

Edit `deploy/backend.env`:

```
HEALONCAL_ANALYSIS_WORKERS=4
HEALONCAL_ANALYSIS_MAX_DIM=640
```

Then `docker compose up -d backend`.

### SSH from this VM into GitHub

The VM's SSH key pair is at `~/.ssh/id_ed25519{,.pub}`. The public key
is registered on the GitHub account that owns the repos. If it gets
lost, regenerate and re-register:

```bash
ssh-keygen -t ed25519 -C "ops@healoncal" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub    # paste into GitHub → Settings → SSH keys
ssh -T git@github.com        # should greet you by name
```

---

## 15. Known issues / gotchas

### Sharp edges

- **`deploy/` isn't in git.** Losing the VM loses the compose file and
  the nginx cert. Check it into a private repo as soon as possible.
- **Heatmap → angle routing by filename substring.**
  `_fetch_heatmaps_for_session` parses the URL to decide angle. Any
  filename change silently breaks the UI. Long-term: add an `angle`
  column to `disease_heatmaps`.
- **uvicorn `--workers 2` + per-worker ProcessPool.** Each worker runs
  its own 3-process pool, so you have **8 Python interpreters** at idle.
  Fine for a single-VM deploy; if this ever gets horizontally scaled,
  drop uvicorn workers to 1 and let the scheduler do it.
- **Spawn-based ProcessPool imports the whole app per worker.** The
  lifespan warmup hides this at startup; if you rely on global state
  set *after* module import, it won't be visible in workers.
- **`capture_image` still does some blocking DB work** (`db.insert`,
  `db.execute`, `db.fetch_all`) on the event loop. Fine at current
  scale (MySQL is local, <10ms), but if you ever move to a remote DB,
  wrap those in `asyncio.to_thread` too.
- **Gemini failures are non-fatal.** `{success: false, error: ...}` is
  returned under `recommendations` in the response — frontend must
  tolerate null/empty recs.
- **SSL is a static origin cert**, not ACME. Plan expiry.
- **Haar cascade** is the face detector. It's fast but misses tilted /
  low-light faces. Tier 2 plan: swap for MediaPipe's face-detection
  task (already a transitive dep on the frontend).

### Naming trivia

- The backend service file `s3_storage_service.py` used to be called
  `gcs_storage_service.py`. The code was always S3 — the old name was
  legacy from when GCS was considered. Some log strings and config
  env-var aliases (`GCS_BUCKET_NAME`, `GCS_SKIN_SCANS_PREFIX`) survive
  as deprecated aliases for `S3_*`.
- Frontend package is `hoc-booth`; repo is `hoc-demo`; tab title is
  "Healoncal". All three refer to the same app.

---

## 16. Planned next steps (master plan excerpt)

See `PERFORMANCE_OPTIMIZATIONS.md` for the full plan. Priority queue:

### Tier 2 (medium effort)

1. **Streaming Gemini recommendations** — token-by-token via
   `generate_content_stream`; huge perceived-latency win.
2. **ProcessPool for heatmap rendering** — another ~3–6s off.
3. **MediaPipe face detection** instead of Haar cascade.
4. **CloudFront in front of S3** for heatmap URLs.
5. **Content-hash analysis cache** (deferred Tier-1 item) — huge win
   for repeats / demos, but needs a cache table and TTL policy.

### Tier 3 (architectural)

1. Split backend into `analyze` + `render` services behind a job queue.
2. GPU / vectorized-Torch analysis pipeline (drops analysis from ~4s
   to ~0.2s).
3. Direct browser → S3 uploads via presigned PUT (saves the backend
   hop).
4. OpenTelemetry tracing so we stop optimizing from log lines.

---

## 17. First-day checklist for a new engineer

1. Clone both repos locally; check out `perf-optimizations` (backend)
   and `perf-streaming-ui` (frontend) to read the latest code.
2. Read `PERFORMANCE_OPTIMIZATIONS.md` end-to-end — it's the fastest
   way to build a mental model of what matters here.
3. Skim `app/api/endpoints/healoncal_analysis.py` —
   `submit_and_analyze_stream` is the entry point that touches almost
   every subsystem.
4. Skim `app/services/healoncal_service.py` —
   `_analyze_image_healoncal_sync` is where all the CV lives.
5. On the VM: run `docker compose logs backend -f` and submit a test
   scan from https://healoncal.com to watch the pipeline live.
6. Check the disease heatmaps in S3 directly via the AWS console —
   helps visualise what the system is producing end-to-end.
7. Read this doc's §15 (sharp edges) and pick one to fix as your
   onboarding PR.

---

**Owner:** you now. Good luck.
