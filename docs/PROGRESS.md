# Progress

Status on 24 Oct 2026: all phases done in the Vercel + MongoDB form the owner asked for, with FULL mode running locally on the GPU.
How this differs from the original Docker/Postgres plan, and why: DECISIONS.md.

## Phases

| Phase | Status | Notes |
|---|---|---|
| 0 Environment, skeleton | Done | No Docker or make on the machine: `tasks.py` + Makefile. GPU probe writes VERSIONS.md (RTX 4050 6 GB, CUDA 12.4). |
| 1 Data, auth, RBAC, audit | Done | Mongo collections, argon2, 15-min access + rotating 8-h refresh tokens, optional TOTP, lockout, field encryption (AES-GCM), RBAC matrix test, hash-chained audit with tamper test, access log, daily audit anchor. |
| 2 Mock ecosystem, synthetic data | Done | 30 fictional institutions, 6 mock issuers (Ed25519 QR keys, demo CA for PDF signatures), issuer toggles (down, latency, forced mismatch), scan damage, handwriting fills, ground truth. |
| 3 Rule packs, plug-in layer | Done | Two packs, validation, json-logic, source citations, host API with hashed keys, idempotency keys, slot mapping, widget, HMAC webhooks with timestamp and replay protection, upload safety (ClamAV client or EICAR fallback, magic bytes, active-content PDF check, pixel limit, no archives). |
| 4 Document understanding | Done | LITE: PDF text layer, keyword classifier, anchor extractor, QR reader, stamp/signature detector. FULL: deskew, OCR Model (docTR), Handwriting Model (TrOCR) on low-confidence values. No Hindi. |
| 5 Validation checks | Done | Completeness, expiry, entity match, records, plausibility (incl. valid-to after issue), noise/ELA/copy-move, PDF revisions, PDF signatures (pyHanko), pHash + embedding duplicates, QR and reference lookup, carry-forward of earlier verifications. |
| 6 Infrastructure CV | Done | EXIF distance and age, reuse, Object Detector counts (classical in LITE, Grounding DINO in FULL), Scene Classifier room type (FULL). Video accepted but not analysed (LOW flag). No floor plans (C item). |
| 7 Agents | Done | LangGraph: Orchestrator, Document, Forensics, Verification agents per document, Case Writer + Critic. Traces stored and shown. Same rule flags as the DAG (test). Falls back to the DAG on any error. |
| 8 Reports, alerts, review | Done | HTML and PDF reports (full and institution view), alerts with email (SMTP or outbox) and webhook, SLA cron, dispositions, observations, 409 decision gate, rectification re-runs only changed documents, retention purge with legal hold, override export. |
| 9 Console | Done | Plain-language redesign: landing page with one-click demo roles, queue, detail (verdict, 9-check grid, findings with evidence, viewer with overlays, heatmap, compare), overview, alerts + outbox, checklist rules (validate, diff, dry run, activate), connected portals (keys, webhooks, issuer toggles), audit trail, accuracy. |
| 10 Evaluation, hardening | Done | `tasks.py eval` writes EVAL-LITE.md / EVAL-FULL.md. 20 unit/integration tests and 8 Playwright acceptance tests pass. |

## Acceptance criteria (01_SRS.md §7), verified with Playwright

| # | Criterion | Result |
|---|---|---|
| 1 | One engine, two portals, two rule packs, live | Pass (local and live site) |
| 2 | Golden application all green and verified | Pass (local and live) |
| 3 | Problem application surfaces every seeded problem | Pass (local and live) |
| 4 | Institution sees only its fix list; re-upload re-runs only affected checks | Pass (local and live) |
| 5 | Dismiss with reason; decision gate until HIGH flags disposed | Pass (local and live) |
| 6 | Audit chain verifies; tampering one row breaks it | Pass (local; not run live because it damages the chain) |
| 7 | Evaluation page shows the PS metrics | Pass (local) |
| 8 | Runs in LITE on CPU | Pass (local and live) |

## Measured metrics (synthetic test set, 6 samples per class, run against the live database)

| Metric | LITE (CPU) | FULL (RTX 4050) |
|---|---|---|
| Field exact match, digital PDFs | 100% (114 fields) | 100% |
| Field exact match, scanned printed | not available | 100% |
| Handwriting CER / exact match | not available (manual review) | 5.5% / 50% (18 fields) |
| Hindi scanned fields, CER / exact match | not available | 0% / 100% (18 fields) |
| Single-defect applications flagged exactly right | 100% (30) | 100% (30) |
| Seeded discrepancy recall | 100% (16/16) | 100% (16/16) |
| HIGH/MEDIUM flags on golden apps | 0 | 0 |
| Source verification success, golden | 100% of 14 | 100% of 14 |
| Forgery detection (12 types) | F1 1.0 on 11 types, reused photo 0.91 | same |
| Lab monitor count MAE, photos | 0.0 (classical counter, synthetic only) | 2.25 (open-vocabulary detector) |
| Walkthrough video count MAE | 1.0 | 0.67 |
| Floor-plan area error (vector) | 0.0% | 0.0% |
| Room-type accuracy | not available | 75% |
| Processing time | about 1.7 to 2.1 s per application | about 29 s per application |

Weak spots, as measured: the FULL detector miscounts dense synthetic labs (MAE 2.25, worse than the classical counter on these drawings). Room type is right 75% of the time.
Handwriting exact match is 50% even though the character error rate is low. Everything is synthetic, so real scans will score lower.
Full tables: EVAL-LITE.md and EVAL-FULL.md.

## Run the demo

```bash
.venv/Scripts/python tasks.py secrets
.venv/Scripts/python tasks.py demo          # LITE, http://localhost:5180
set MODE=FULL && .venv/Scripts/python tasks.py demo   # FULL on the GPU
.venv/Scripts/python tasks.py test
.venv/Scripts/python tasks.py e2e
.venv/Scripts/python tasks.py eval
```

Live: https://pramaan-sih26.vercel.app (click "Enter as Senior Officer"). Script: DEMO.md.

## Known gaps

- Added 24 Oct (second pass): Hindi labels and Hindi OCR (FULL), transliterated name matching, tables (fee totals, faculty count), vector floor-plan areas, walkthrough video frames (local), two-step sign-in setup screen.
- Still missing: Hindi handwriting, scanned tables, raster floor plans, video on the hosted build, signature similarity (C).
- No Docker Compose, Redis/Celery, MinIO, Mailpit or Caddy (see DECISIONS.md for what replaces each).
- Tests now: 26 unit/integration, 8 Playwright acceptance (local), 5 non-destructive acceptance tests on the live site.

## Where to resume

Nothing is half done. Next ideas: real team lab photos and floor plans, Hindi handwriting, scanned tables.
