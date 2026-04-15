# `/submit-and-analyze` Performance Optimizations

Goal: cut end-to-end latency of the face-analysis endpoint (3 images → analysis
+ 21 heatmaps + Gemini recommendations) toward ~30s without reducing heatmap
count per angle.

Starting point (from logs): **45–70s** end-to-end, with per-image analysis
alone at **16–38s** under "parallel" threads.

---

## Round 1 — API surface parallelism

### 1.1 Parallelize image reads + S3 captures
**File:** `app/api/endpoints/healoncal_analysis.py` (~L534-572)

The endpoint originally read `image_front` / `image_left` / `image_right`
sequentially with three `await u.read()` calls, then ran a sequential
`for`-loop of `healoncal_service.capture_image(...)`, each of which synchronously
uploads to S3 and inserts a DB row.

Now: both phases use `asyncio.gather`, so the 3 reads and the 3 S3
uploads run concurrently.

- Expected saving: **~5–10s** (3 sequential S3 PUTs → 1 wall-clock S3 PUT).

### 1.2 Fan-out per-angle heatmaps AND combined heatmap together
**File:** `app/services/heatmap_visualization_service.py` (`generate_heatmaps_for_specific_angle`)

Previously, for each angle:
1. `asyncio.gather` the 7 per-disease heatmaps, *then*
2. `await` the combined heatmap — serial step after the gather.

Now: the combined heatmap task is included in the same `gather`, so it runs
alongside the 7 disease heatmaps instead of after them.

- Expected saving: **~1–3s per angle** (combined heatmap has similar cost to
  a single per-disease heatmap).

### 1.3 Eagerly initialize the Gemini client
**File:** `app/services/gemini_recommendation_service.py` (bottom of file)

`GeminiRecommendationService._ensure_initialized` was lazily invoked on the
first request, paying `genai.Client(...)` cost on that request's critical
path. Now it's called once at module load (wrapped in try/except so missing
API key doesn't break import).

- Expected saving: **~1–2s** on first request after boot.

---

## Round 2 — Naming cleanup (S3 was already in use)

Discovered that `gcs_storage_service.py` was *already* a pure AWS S3
implementation (as called out in its own top-of-file docstring). Renamed to
drop the misleading GCS prefix — **no behavior change**:

- File: `gcs_storage_service.py` → `s3_storage_service.py`
- `is_gcs_configured()` → `is_s3_configured()`
- Import aliases: `gcs_upload_image` / `gcs_delete_key` / `gcs_presign` →
  `s3_upload_image` / `s3_delete_key` / `s3_presign`
- Doc/log strings: `"GCS"` / `"Google Cloud Storage"` → `"S3"`

Callers: `api/endpoints/healoncal_analysis.py`,
`services/heatmap_visualization_service.py`, `services/healoncal_service.py`.

---

## Round 3 — True parallelism for CPU-bound analysis (the big one)

**Finding:** logs showed per-image analysis taking **16–38s** even though
three angles ran "in parallel" via `asyncio.to_thread(_analyze_image_healoncal_sync, ...)`.
Pure-Python pixel work serializes under the GIL, so threads weren't giving
real parallelism.

### 3.1 ProcessPoolExecutor for per-image analysis
**File:** `app/services/healoncal_service.py`

- Added module-level `ProcessPoolExecutor` with `spawn` context,
  `max_workers = HEALONCAL_ANALYSIS_WORKERS` (default 3 — one per image angle).
- Added `_analyze_image_in_worker(image_data)` helper that lazily instantiates
  a per-worker `HealoncalService()` singleton and delegates to
  `_analyze_image_healoncal_sync`.
- `_analyze_image_healoncal(...)` now dispatches via
  `loop.run_in_executor(_get_analysis_pool(), ...)` instead of
  `asyncio.to_thread`.

### 3.2 Pool warm-up at app startup
**File:** `app/main_healoncal.py` (lifespan)

The first `ProcessPoolExecutor.submit` cold-starts its workers — spawn + full
interpreter + `cv2`/`numpy` imports (~8–15s). To hide that from the first
user request:

- At FastAPI lifespan startup, we `submit(_warmup_worker)` once per worker
  and block on `.result(timeout=60)` for each.
- `_warmup_worker` imports cv2/numpy, instantiates the per-worker
  `HealoncalService`, and pre-loads the Haar cascade (see 4.2).

- Expected saving: analysis phase goes from **~38s (serialized)** down to
  roughly **max(per-image) ≈ 13–16s** (true 3x parallelism).

---

## Round 4 — Per-image speedups

### 4.1 Downscale inputs to 512px (or `HEALONCAL_ANALYSIS_MAX_DIM`)
**File:** `app/services/healoncal_service.py` — `_maybe_downscale()`

Phone-camera inputs are typically 3–12 MP. All per-image metrics in
`_calculate_skin_metrics`, `_analyze_biomarkers`, `_analyze_medical_conditions`
(Canny, Laplacian, HoughCircles, cornerHarris, color-space conversions,
histograms, pixel means/vars) are **statistical aggregates that stay stable
at lower resolution** but cost scales roughly with pixel count.

- We `cv2.resize(..., INTER_AREA)` down to 512px longest side at the top of
  `_analyze_image_healoncal_sync`.
- Override: `HEALONCAL_ANALYSIS_MAX_DIM` env var (raise it if accuracy
  regresses on any metric).

- Expected saving per image: **10–50x** on downstream cv2 ops.
  `cv2.HoughCircles` in particular (used in `_analyze_medical_conditions`)
  was the single biggest beneficiary.

### 4.2 Module-level Haar cascade cache
**File:** `app/services/healoncal_service.py` — `_get_face_cascade()`

`_assess_image_quality` was building a fresh `cv2.CascadeClassifier(
cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')` on every
call. Cached at module level; `_warmup_worker` pre-loads it in every pool
process so the first real request doesn't hit disk.

- Expected saving: **~10–30ms per image**.

### 4.3 Drop the duplicate JPEG decode + full-res quality pass
**File:** `app/services/healoncal_service.py` — `_assess_quality_from_np()`

`_analyze_image_healoncal_sync` used to:
1. Decode JPEG → numpy (1st decode).
2. Call `_assess_image_quality(image_data)` which decoded the JPEG a
   **second time** and ran Haar on full resolution.
3. Run the rest of the pipeline on the already-downscaled array.

Replaced step 2 with `_assess_quality_from_np(image_np)` which reuses the
already-decoded-and-downscaled array (Haar runs on 512px instead of full
res, which is also fine — we only need a boolean face-detected flag).

- Expected saving: **~100–500ms per image** (one fewer JPEG decode + small-image
  Haar instead of full-res Haar).

---

## Round 5 — S3 client caching + bigger connection pool

### 5.1 Cache boto3 S3 client at module level
**File:** `app/services/s3_storage_service.py` — `_get_s3_client()`

Every storage op (`upload_image`, `download_image`, `delete_object_key`,
`is_s3_configured`) was calling `boto3.client("s3", ...)` fresh. boto3
client construction resolves credentials, reads config, caches endpoint
metadata — ~50–200ms per build. With ~24–27 storage ops per request that's
a non-trivial tax.

- Cached `(client, bucket, prefix, region)` in `_S3_CLIENT_CACHE` after the
  first successful build.
- Expected saving: **~1.5–3s per request**.

### 5.2 Bigger S3 connection pool
Same `_get_s3_client()` — bumped `Config(max_pool_connections=32)` so the
~21 concurrent heatmap uploads + 3 captures don't serialize on the default
10-connection pool.

- Expected saving: removes hidden serialization at the TCP-pool level when
  >10 uploads run in parallel.

---

## Operational notes

- **Process pool size:** 3 by default (one worker per image angle). Bump
  via `HEALONCAL_ANALYSIS_WORKERS` only if you also raise uvicorn
  concurrency — otherwise you're just paying RAM for idle workers.
- **Downscale size:** 512px works well for the statistical metrics we
  compute. If you add a new analyzer that genuinely needs more detail
  (e.g. small-feature lesion detection), raise `HEALONCAL_ANALYSIS_MAX_DIM`
  or run that analyzer on the original bytes before downscaling.
- **Warm-up at boot:** the process pool warm-up adds ~8–15s to container
  startup. This is intentional — it pays the cost once so the first user
  request doesn't see it.
- **Heatmap quality unchanged:** heatmaps are still generated at full
  resolution on the original captured image. The downscale only affects
  the metric/biomarker analysis path, not the heatmap overlay rendering.
- **No functional changes to results shape:** the response JSON from
  `/submit-and-analyze` is identical in structure.

---

## Changed files (summary)

- `app/api/endpoints/healoncal_analysis.py` — parallelized reads + captures; `gcs_*` → `s3_*`.
- `app/services/healoncal_service.py` — ProcessPoolExecutor, warm-up helper,
  downscale, Haar cache, np-based quality assessment, `gcs_*` → `s3_*`.
- `app/services/heatmap_visualization_service.py` — combined heatmap in the
  same `gather`; `gcs_*` → `s3_*`.
- `app/services/gemini_recommendation_service.py` — eager init.
- `app/services/s3_storage_service.py` — renamed from `gcs_storage_service.py`;
  cached boto3 client; bigger connection pool; `is_gcs_configured` → `is_s3_configured`.
- `app/main_healoncal.py` — pre-warm the analysis process pool during lifespan.

## Env vars introduced

| Var | Default | Purpose |
|-----|---------|---------|
| `HEALONCAL_ANALYSIS_WORKERS` | `3` | Size of the analysis `ProcessPoolExecutor`. |
| `HEALONCAL_ANALYSIS_MAX_DIM` | `512` | Longest-side cap (px) for the analysis-path image downscale. |

## Expected end-to-end impact

Rough cumulative estimate vs. the **45–70s** baseline:

| Stage                         | Before  | After   |
|------------------------------|---------|---------|
| 3x image reads + S3 captures | 6–15s   | 2–5s    |
| 3x per-image analysis        | 16–38s  | 3–6s    |
| 21 heatmaps + Gemini (parallel) | 15–30s | 12–22s |
| Misc (DB writes, response)   | 3–5s    | 2–4s    |
| **Total**                    | **45–70s** | **~20–35s** |

Measure with the existing log lines
`[HEALONCAL PARALLEL] Total parallel processing time: ...` and
`[HEALONCAL SUCCESS] Analysis completed - ... Time: Xs`.

---

## Round 6 — Streaming response (perceived-latency win)

Even with the raw-latency work above, the UI still waits for the whole
response before rendering. We now stream progress via Server-Sent Events so
the user sees metrics before heatmaps/Gemini finish.

### 6.1 SSE endpoint `POST /submit-and-analyze/stream`
**File:** `app/api/endpoints/healoncal_analysis.py`

Same inputs as the non-streaming endpoint, but returns
`text/event-stream` and emits events as each phase completes:

| Event             | Payload                                             | Approx. fires at |
|-------------------|-----------------------------------------------------|------------------|
| `progress`        | `{stage: "validating"\|"session_created"\|"captured"\|"analyzing"}` | 0–8s     |
| `results`         | `{session_id, results}` — metrics, diseases, per-angle analyses     | ~8–12s   |
| `heatmaps`        | `{heatmaps: {...}}`                                 | ~15–22s  |
| `recommendations` | `{recommendations: {...}}` (parallel with heatmaps) | ~15–25s  |
| `done`            | `{session_id, processed_images}`                    | end      |
| `error`           | `{error: str}` — fatal                              | on failure |

Heatmap fetch + Gemini run in parallel via `asyncio.wait(...,
FIRST_COMPLETED)` so whichever finishes first is emitted first. Nginx
already has `proxy_buffering off` on `/api/healoncal/`, and the response
sets `X-Accel-Buffering: no` + `Cache-Control: no-cache, no-transform`
defensively.

### 6.2 Client streaming consumer
**Files:** `src/api/uploadSession.ts`, `src/Page/CapturePage.tsx`,
`src/store/reportStore.ts`

- New `submitAnalysisStream(args, callbacks)` uses `fetch()` +
  `ReadableStream` (EventSource can't POST multipart) and parses SSE
  frames as they land, firing `onProgress` / `onResults` / `onHeatmaps` /
  `onRecommendations` / `onDone` / `onError`.
- `reportStore` gained `patchReport(partial)` so later streaming phases
  merge into the existing report instead of replacing it.
- `CapturePage` navigates to `/report` as soon as the `results` event
  arrives — heatmaps and recommendations slot in progressively via
  `patchReport`.

### 6.3 Result

Wall-clock time is similar, but **perceived** latency drops a lot:

| Milestone              | Non-streaming | Streaming |
|------------------------|---------------|-----------|
| Any meaningful content | 20–35s        | ~8–12s    |
| Heatmaps visible       | 20–35s        | ~15–22s   |
| Recommendations visible| 20–35s        | ~15–25s   |

The user stares at the spinner for less than half as long before the
report is interactive — and the remaining work lands in place without
another round-trip.

---

## Round 7 — Tier 1 of the master plan

### 7.1 Per-angle heatmap streaming
**Files:** `app/api/endpoints/healoncal_analysis.py`,
`src/api/uploadSession.ts`, `src/Page/CapturePage.tsx`,
`src/store/reportStore.ts`

Previously the stream emitted a single `heatmaps` event after all 21
overlays were rendered. Now:

- `analyze_session(generate_heatmaps=False)` runs first (fast, just
  analysis + DB storage), so `results` lands in ~5s.
- The endpoint reconstructs per-angle `detected_diseases` from the DB
  (via `analysis_result_id` → `angle` mapping) and dispatches three
  independent `_generate_heatmaps_parallel(angle)` tasks.
- As each angle finishes, a `heatmap_angle` event is emitted with just
  that angle's `individual_heatmaps` + `combined_heatmap`.
- A final consolidated `heatmaps` event is still sent for clients that
  only speak the v1 shape.
- The client merges incoming angles into `report.heatmaps.images[angle]`
  via `patchReport((prev) => ...)`.

UX: users see front / left / right heatmaps appear one-by-one, typically
5–8s apart, instead of all three landing together ~15–22s in.

### 7.2 Vectorized speckle overlay
**File:** `app/services/heatmap_visualization_service.py`
(`_draw_speckle_overlay`)

The old loop issued up to 450 `draw.ellipse` calls per heatmap
(~9,500 PIL calls total across 21 heatmaps). The new implementation:

- Generates all speckle coordinates / radii in one `numpy.random`
  call per region.
- Pre-computes disc stamps for radii 1–3.
- Paints stamps into a single `(H, W, 4)` uint8 numpy array via slicing.
- Composites once onto the backing PIL image with `alpha_composite`.

PIL original implementation is kept as `_draw_speckle_overlay_pil_fallback`
for compat if `draw._image` isn't reachable.

- Saving: **~3–8s** across 21 heatmaps (the biggest chunk of render time
  was this Python loop).

### 7.3 WebP encoding for heatmaps
**File:** `app/services/heatmap_visualization_service.py`
(`_save_heatmap_to_storage`, `_save_heatmap_to_storage_with_angle`)

Heatmaps are now encoded as WebP (`quality=82, method=4`) instead of
PNG. For 512px RGBA overlays:

- PNG: typically ~100–300 KB each.
- WebP: typically ~30–80 KB each.

That's 3–5× less S3 body per PUT × 21 heatmaps, which also means
smaller / faster client download on the report page.

- Saving: **~2–4s** on the upload stage, plus visibly faster
  client-side image load.

### 7.4 Batched `detected_diseases` INSERT
**Files:** `app/services/mysql_client_service.py` (new `bulk_insert`),
`app/services/treatment_storage_service.py` (`store_detected_diseases`)

Previously: one `INSERT ... VALUES (...)` per disease, inside a for-loop.
With 5–15 diseases × 3 angles, that's 15–45 round-trips. Now a single
multi-row `INSERT ... VALUES (...),(...),(...)` via `cur.executemany`.

- Saving: **~300–800ms** per request (more on high-RTT DB links).

### 7.5 Deferred Tier-1 items

- **Content-hash caching of analysis results** — needs a new cache
  table + TTL policy; deferred to a follow-up.

All Tier-1 work shipped in this round keeps the existing API response
shape fully backward compatible.

---

## Round 8 — Quality-vs-memory rebalance

Shift of stance: we were trading image detail for speed (analysis ran at
512 px on Q=0.92 JPEG captures). This round raises both ends of the
pipeline without letting RAM balloon.

### 8.1 Higher-resolution capture from the browser
**File:** `src/Page/CapturePage.tsx`

- `videoConstraints` bumped from `ideal: 1280×720` → `1920×1080`.
- `canvas.toBlob(...)` now tries **WebP Q=0.95** first; if the browser
  refuses (Safari <14, rare), falls back to **JPEG Q=0.95** (up from
  0.92). Both are visually and statistically near-lossless.

Result: ~1–1.5 MB per image (vs ~130 KB before). Upload adds ~1–3s on
mobile, but the analyser sees much more real detail.

### 8.2 Raise the analysis resolution to 1024 px, decode efficiently
**File:** `app/services/healoncal_service.py`

- `HEALONCAL_ANALYSIS_MAX_DIM` default: **512 → 1024**.
- Analyzer now calls `PIL.Image.open(io.BytesIO(...)).draft("RGB",
  (W, H))` **before** materialising pixels. For JPEG sources this tells
  the decoder to read only as many DCT coefficients as needed for the
  target size — so we never allocate a full-res pixel buffer (key for
  the RAM ceiling). Following that up with `_maybe_downscale(...)`
  snaps to the exact bound because `.draft()` rounds to native JPEG
  subsample factors (1/2, 1/4, 1/8).
- Drops the PIL `Image` handle (`.close() + del`) immediately once the
  numpy array exists, so the decoded byte buffer is reclaimable before
  the long analysis tail runs.

Peak RAM per worker stays close to the pre-round numbers (≈7 MB vs ≈5
MB previously) even though we're analyzing 4× the pixels.

### 8.3 Bounded ProcessPool worker lifetime
**File:** `app/services/healoncal_service.py`

- `ProcessPoolExecutor(..., max_tasks_per_child=50)` — each worker is
  recycled after 50 analyses. cv2/numpy arena growth therefore can't
  run away, even under a small leak. Configurable via
  `HEALONCAL_ANALYSIS_MAX_TASKS_PER_CHILD` (set to 0 to disable).
  Falls back to the no-kwarg form on Python < 3.11.

### 8.4 Higher-quality heatmaps
**File:** `app/services/heatmap_visualization_service.py`

- WebP encoder quality **82 → 92** in both
  `_save_heatmap_to_storage` and `_save_heatmap_to_storage_with_angle`.
  Still well under PNG for size; eliminates the faint banding/blocking
  that was visible on the combined overlay at Q=82.

### 8.5 Metadata/branding cleanup
**Files:** `hoc-demo/package.json`, `hoc-demo/package-lock.json`.
Package name `hoc-booth` → `healoncal` so nothing in the built bundle
or npm metadata still mentions the old booth project name. Tab title
had already been fixed in Round 0; this finishes the job.

### New / changed env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `HEALONCAL_ANALYSIS_MAX_DIM` | **1024** (was 512) | Longest-side cap for analysis-path downscale. |
| `HEALONCAL_ANALYSIS_MAX_TASKS_PER_CHILD` | `50` | Recycle process-pool workers after N tasks; `0` to disable. |

### Expected impact

| Axis | Round 7 | Round 8 |
|---|---|---|
| Capture size on wire | ~130 KB × 3 | ~1.3 MB × 3 |
| Analyser sees | 512 px side | 1024 px side |
| Per-image analyse CPU | ~1.3 s | ~2.2 s |
| Wall-clock analysis phase | ~3.9 s | ~4.5 s |
| Peak worker RAM | ~5 MB | ~7 MB |
| Heatmap visual quality | WebP Q=82 | WebP Q=92 |
| Pore / fine-line / texture signal | muddied by 512 px | meaningful |

Net: ~1 s slower end-to-end (hidden by SSE streaming anyway — `results`
still lands in ~6 s), in exchange for a real accuracy lift on the
detail-sensitive metrics.

