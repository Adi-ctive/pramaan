# 06 — Build Plan (phased, with Definition of Done)

Build vertically: each phase ends with something runnable and demoable. Do not start a phase until the previous phase's Definition of Done (DoD) passes. Record progress in `docs/PROGRESS.md` (phase, status, what works, known issues, next step).

---

## Phase 0 — Environment and skeleton
**Tasks**
- Create the repo layout from 02_ARCHITECTURE.md §4. Copy the spec into `docs/`. Create `CLAUDE.md`.
- Docker Compose: postgres (pgvector), redis, minio, clamav, mailpit, caddy.
- Backend skeleton: FastAPI app, config (`MODE=FULL|LITE`), health endpoint, SQLAlchemy + Alembic, Celery app with queues `cpu`, `gpu`, `agent`.
- Frontend skeleton: console (Vite + React + TS + Tailwind + shadcn) with the nav shell; widget library build.
- `Makefile`, `.env.example`, `make secrets`, pre-commit, CI-like `make test`.
- **GPU probe script** `scripts/gpu_probe.py`: report the CUDA devices and test PyTorch, PaddlePaddle (if installed) and Ollama reachability. Write the results to `docs/VERSIONS.md`.

**DoD:** `make up` brings everything up healthy; `/health` reports DB, Redis, MinIO, ClamAV and Ollama status; the console loads at `https://localhost`; the GPU probe report exists.

## Phase 1 — Data model, auth, RBAC, audit
**Tasks**
- All tables from §8 with Alembic migrations. Encrypted column type (AES-GCM).
- Users, argon2, JWT access and refresh, optional TOTP, lockout.
- RBAC `require()` dependency plus the matrix test.
- Hash-chained `audit_log` with an insert-only trigger; `audit.verify()`; `access_log` middleware.
- Seed demo users for every role.

**DoD:** login works for every role; the RBAC matrix test passes; the audit tamper test passes.

## Phase 2 — Mock ecosystem and synthetic data v1
**Tasks**
- `mock-records` service plus the `records` schema plus HTTP API.
- `mock-issuer` service: fictional issuers, Ed25519 keys, demo root CA with per-issuer certificates, reference lookup, toggles (latency, down, force_mismatch).
- `synth/generate.py` v1:
  - About 30 synthetic institutions across 4 regions, with records (approvals, programmes and intake, faculty, accreditations, NOCs, undertakings, deficiencies, payments, history), campus lat/long and establishment dates.
  - Document templates for every slot type in the demo rule pack: Society Registration, Land/Lease Deed, Fire NOC, Building Completion Certificate, General Affidavit (with handwritten fills), Accreditation Certificate, Fee Receipt (table), Faculty List (table), Infrastructure photos manifest.
  - Each issuer-backed document carries a signed QR code; some are pyHanko-signed PDFs; issuer records are registered in `mock-issuer`.
  - Outputs: clean digital PDFs, plus "scanned" variants via Augraphy (skew, blur, noise, folds, low DPI), plus handwriting fields rendered with OFL handwriting fonts (English and Hindi).
  - Ground-truth JSON for every document (type, every field value with bbox, regions).
- Infrastructure photos: load team photos from `synth/photos/` (gitignored), with ground-truth counts in `synth/photos/labels.csv`. Write EXIF GPS and time with piexif to create good and bad cases.

**DoD:** `make seed` produces the dataset; the mock services answer; one sample of each document type is viewable; ground truth validates against its schema.

## Phase 3 — Rule packs and the plug-in layer
**Tasks**
- Rule-pack YAML schema (JSON Schema), loader, validator, safe json-logic evaluator, typed rule kinds (`entity_match`, `count_vs_claim`, `exif_geo`, `expiry`, `plausibility`).
- `aicte-demo-2026-27.yaml` and `university-affiliation-demo.yaml` (different slot names, a subset of rules).
- Hosts, API keys, slot mappings; host API (§11); upload sessions; webhook sender with HMAC, retries and a delivery log.
- `mock-hosts` service: Host A and Host B pages per 03_UI_DESIGN.md §6, each with a backend that creates applications and upload sessions server-to-server, and webhook receivers that display status.
- Widget v1: slots from the session, upload, a placeholder quick-check (type by extension), deficiency panel stub, CustomEvents, Shadow DOM.
- Upload safety pipeline (05_SECURITY.md §8).

**DoD:** from Host A and Host B, an institution can create an application, upload into mapped slots and submit; the API returns 202; a webhook arrives (with a stub report); the EICAR file is rejected.

## Phase 4 — Document understanding
**Tasks**
- Provider interfaces plus registry. Implementations: PaddleOCR (with docTR and Tesseract fallbacks), VLM via Ollama (classify, HTR, KIE), TrOCR, Grounding DINO, CLIP, e5 embeddings, NullLLM and keyword/regex providers for LITE.
- Pipeline stages B1–B10: render, preprocess, classify, read, regions (handwriting, stamp, seal, signature, QR, table), HTR, extraction, normalisation, fingerprints.
- Field-candidate reconciliation: when OCR+regex and VLM disagree, re-read the region crop at 2× resolution; otherwise lower the confidence and raise an `EXTRACTION_CONFLICT` flag.
- Widget quick-check is now real: type, quality (blur via Laplacian variance, resolution) and key fields seen.

**DoD:** on the clean synthetic set, field exact-match ≥ 90 % and printed CER ≤ 5 % in FULL mode (report actual numbers; do not fake them); handwriting below threshold routes to `MANUAL_REVIEW`; LITE mode still extracts printed fields from digital PDFs.

## Phase 5 — Validation checks
**Tasks**
- C1 records fetch; C2 completeness and expiry; C3 consistency with entity resolution (RapidFuzz token-set + transliteration normalisation + e5 cosine; combined score; threshold from the rule pack); C4 plausibility (dates, ID formats, issuer max validity, holidays); C7 carry-forward.
- B11 forensics: ELA (multi-quality), noise residual (high-pass + block variance), SIFT copy-move with RANSAC, PDF forensics (pikepdf: incremental revisions, `/Info` vs XMP dates, Producer, fonts per text run in a field bbox, objects added after signing), text-level font outliers. Heatmaps saved to MinIO.
- C5 duplicates: pHash Hamming plus pgvector cosine across all applications and institutions.
- B12 verification adapters: QR (decode → Ed25519 verify → field compare), PDF signature (pyHanko: trust root, integrity, signer), reference lookup (mock issuer), with statuses and logging per FR-VER-04/05.
- Flag factory: severity from the rule pack, evidence objects, advisory wording.

**DoD:** the problem application yields every expected flag listed in SRS §7, acceptance criterion 3, with evidence; the golden application yields zero HIGH and MEDIUM flags; the verification table is complete with sources and timestamps.

## Phase 6 — Infrastructure CV
**Tasks**
- Room-type classification (CLIP zero-shot with label prompts from the rule pack).
- Object counting with Grounding DINO using prompts derived from the claimed facility; NMS; per-photo counts summed per facility (with dedupe across photos via image embeddings so the same view isn't counted twice).
- EXIF distance and time checks; reuse detection via C5.
- Video keyframes feed the same path.
- (Stretch) floor-plan room segmentation and area.

**DoD:** on the labelled team photos, the count MAE is reported; the shortfall case is flagged; the reused-photo case is flagged across institutions; EXIF bad cases are flagged.

## Phase 7 — Multi-agent orchestration
**Tasks**
- LangGraph graph per 02_ARCHITECTURE.md §6: Orchestrator, Document, Forensics, Verification, Consistency, Infrastructure, Case Writer, Critic.
- Tool registry wrapping the pipeline functions (Celery dispatch for heavy tools); typed args and results; `emit_flag` and `emit_verification` guards.
- Escalation logic: cheap forensics first; deeper ones on threshold; verification route selection with retry and back-off; Document Agent conflict resolution.
- Untrusted-data envelope; step, token and time budgets; fallback to the deterministic DAG on any agent error; LITE mode equals the DAG.
- `agent_traces` persisted; timeline API.
- Prompt-injection documents added to the synthetic set, with a test.

**DoD:** agent mode and DAG mode produce the same set of rule-derived flags on the golden and problem applications (agents may add conflict or escalation flags, never remove rule flags); the injection test passes; the trace is visible via the API.

## Phase 8 — Reports, alerts, human review
**Tasks**
- Report JSON → HTML/PDF (Jinja2 + WeasyPrint); institution view vs full view.
- Case Writer summary with flag-ID citations; Critic validation; template fallback.
- Alert engine from rule-pack alert rules; channels: in-app, Mailpit email, host webhook; SLA computation; Celery beat for time-based alerts.
- Dispositions (confirm, dismiss, escalate with reason), observations, decision-note gate (HTTP 409 until HIGH flags are disposed).
- Rectification loop: re-upload → incremental re-run of only the affected stages and rules → new report version → webhook `validation.updated`.
- Retention purge job.

**DoD:** acceptance criteria 3, 4 and 5 from the SRS pass end to end.

## Phase 9 — Officer console (full UI)
**Tasks**
- Every screen in 03_UI_DESIGN.md §4: Queue, Application Detail (three panes, overlays, compare mode, Records diff, Verify, Timeline, case summary with chips), Infrastructure Gallery, Dashboard, Alerts, Rule Packs (Monaco, diff, dry run, activate), Hosts and Keys, Slot Mappings with widget preview, Audit (verify chain, export), Evaluation.
- Keyboard shortcuts, density toggle, dark mode, i18n scaffolding, empty, loading and error states.
- Widget v2 polish: Hindi labels, plain-language deficiency messages.

**DoD:** the demo script in 03_UI_DESIGN.md §7 runs entirely through the UI with no terminal steps except `make demo`.

## Phase 10 — Evaluation harness and hardening
**Tasks**
- `synth` forgery set v2 with ground truth. Forgery types:
  - date edit (pixel)
  - name swap (pixel)
  - amount alteration
  - pasted stamp from another document
  - copy-move inside a page
  - PDF incremental text edit
  - PDF edited after signing
  - QR payload mismatch (valid signature for different data)
  - invalid QR signature
  - reused photo across institutions
  - expired document
  - wrong document in slot
  - intake mismatch vs records
  - name mismatch across documents
  - implausible issue date
  - bad reference-number format
  - EXIF far from campus
  - prompt-injection text
- `eval/run_eval.py` computes and stores:
  - **Extraction accuracy:** field exact match per type; CER for printed and handwritten text.
  - **Validation accuracy:** per-rule precision and recall vs ground-truth violations.
  - **Anomaly detection:** P/R/F1 per forgery type; overall AUROC where scores exist.
  - **Source-verification success rate:** verified ÷ verifiable documents; plus a mismatch catch rate.
  - **Discrepancy identification reliability:** recall of seeded discrepancies, and the false-positive rate on clean applications.
  - **Average processing time:** per application and per document (from `stage_runs`), in FULL and LITE modes.
  - **Alert timeliness:** delay between the triggering condition and the alert being sent.
  - **Manual effort reduction (estimate):** `(baseline_minutes_per_doc × docs − officer_minutes_on_flagged_items) / baseline`, with the baseline assumption stated in the UI.
- Results go into `eval_runs` and onto the Evaluation page.
- Hardening: run the full security test list in 05_SECURITY.md §12; Playwright end-to-end for the demo script; finalise `README.md`; pre-compute a demo cache; record the backup demo video checklist in `docs/DEMO.md`.

**DoD:** `make eval` produces a complete metrics report with real numbers; all tests pass; `README.md` quickstart works on a fresh clone in FULL and LITE modes.

---

## Seeded demo applications
| Name | Host | Contents |
|---|---|---|
| `GOLDEN-A` | Host A | Complete, all valid, all verifiable, consistent with records, real lab photos with matching counts |
| `PROBLEM-A` | Host A | Missing Building Completion Certificate; expired Fire NOC; lessee name mismatch; claimed intake 180 vs records 120; pixel-edited date on the affidavit; handwritten fields with low confidence; QR payload mismatch on the accreditation certificate; lab photo reused from another institution; lab with 12 monitors vs 30 claimed; one photo with EXIF 40 km away; one document carrying injection text |
| `GOLDEN-B` | Host B | Clean, under the university rule pack |
| `PROBLEM-B` | Host B | Wrong document in slot; implausible issue date; issuer service down → `SOURCE_UNAVAILABLE` → manual review |

## Working agreements for the build
- Never hard-code regulatory values in code. They go in rule packs, marked `demo_value: true`.
- Never fabricate metrics. If a target isn't met, report the real number and the reason in `PROGRESS.md`.
- Never use real government logos, real institution names or real people's data.
- Every new check needs: a rule or detector ID, a flag code with severity in the rule pack, evidence, a unit test and a synthetic test case.
- Keep FULL/LITE parity: every feature either works in LITE or degrades to `MANUAL_REVIEW` with a clear reason.
