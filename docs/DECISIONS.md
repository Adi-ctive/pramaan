# Decisions

Choices made while building, with the reason for each. The spec in docs/pramaan-spec is the source of truth. Where this build differs, it is listed here.

| # | Decision | Why |
|---|---|---|
| 1 | MongoDB (Atlas in the cloud, mongomock in tests and local LITE) instead of PostgreSQL + pgvector | The project owner asked for a Mongo backend hosted on Vercel. Documents, blobs, flags, audit and embeddings all live in Mongo collections. |
| 2 | Hosted build is one Vercel Python function plus a static React console, LITE mode only | Vercel has no GPU, a 500 MB bundle cap and a 60 s time limit. FULL mode runs locally on the GPU with the same code. |
| 3 | No Docker Compose stack | Docker is not installed on the build machine. `tasks.py` (and a Makefile that calls it) replaces `make up/seed/demo/test/eval`. Services the compose file would have run are covered as follows. |
| 4 | Redis/Celery replaced by in-process runs | Validation of one application takes about 1 to 2 s in LITE and 3 to 70 s in FULL. Scheduled jobs run through Vercel Cron (`/api/cron/daily`) or `python tasks.py cron`. |
| 5 | MinIO replaced by a Mongo `blobs` collection | Same content-addressed storage idea. Files are stored with their SHA-256, originals kept read-only, derived images stored separately. |
| 6 | ClamAV used when `CLAMD_HOST` is set, otherwise an EICAR signature check | No ClamAV daemon on the machine or on Vercel. The INSTREAM client is built and used when a daemon exists. |
| 7 | Mailpit replaced by SMTP-if-configured plus an `outbox` collection shown in the console | No Mailpit on the machine. Point `SMTP_HOST`/`SMTP_PORT` at Mailpit and mail goes out for real. |
| 8 | Caddy TLS replaced by Vercel HTTPS; security headers set in vercel.json | Vercel terminates TLS. Locally the servers are plain HTTP on localhost. |
| 9 | GPU is an RTX 4050 Laptop (6 GB), not the RTX 5060 Ti in the prompt | Checked with nvidia-smi. All five FULL models fit together (5.9 GB peak). |
| 10 | Ollama is not installed, so FULL models run in-process with transformers | Same roles, local and free. OCR Model: docTR (the spec's PaddleOCR fallback). Handwriting Model: TrOCR base handwritten. Object Detector: Grounding DINO tiny. Scene Classifier: CLIP ViT-B/32. Reasoning LLM: Qwen2.5-1.5B-Instruct (a 7B model does not fit next to the others in 6 GB). With `GROQ_KEY` set, the hosted build can use a hosted LLM for the Case Writer. |
| 11 | Hindi: labels in rule packs carry Hindi alternatives; digital PDFs read Hindi from the text layer; scanned Hindi pages use a second OCR pass (EasyOCR hi+en) in FULL; names in Devanagari are transliterated (ITRANS) and compared by consonant skeleton | No Hindi handwriting model. Pillow cannot shape Devanagari, so Hindi test documents are rendered by Chromium (scripts/make_hindi_assets.py). |
| 12 | Agents use LangGraph with rule-based planning, and the LLM only writes the case summary | A 1.5B model is not reliable enough to steer checks. Agents choose reading strategy, escalation and verification routes from the evidence. Every check is a deterministic tool. Severity and status never come from a model. LITE mode, or any agent error, falls back to the fixed DAG. |
| 13 | Case summary is checked by a Critic; any failure uses the template | The Critic rejects unknown flag IDs, numbers not present in the cited flags, and words such as "forged" or "approved". |
| 14 | Photo duplicates need both an embedding match (cosine 0.97 or more, demo value) and a loose pHash match (distance 20 or less) | On the schematic synthetic photos, CLIP alone rated two different labs 0.956 similar. |
| 15 | Walkthrough videos are sampled at 1 frame/s (up to 8, near-duplicates dropped) and counted by their best frame, locally. The hosted build has no ffmpeg (Vercel's 225 MB function cap) and flags videos for manual viewing | Counting the best frame avoids double counting the same monitors across frames. |
| 16 | Synthetic scans use our own degradation (low DPI, fold, stain, noise, skew) instead of Augraphy | Fewer dependencies. Damage is applied before sensor noise, as in a real scanner. |
| 17 | PDF signatures use a deterministic demo CA (EC P-256) and pyHanko | Sample files signed once still verify after any reseed. The CA is labelled "(mock)". |
| 18 | One-click demo sign-in when `DEMO=true` | Judges and teammates do not need passwords to try the demo. It only works for the seeded demo accounts and is off when `DEMO` is not "true". |
| 19 | Access tokens last 15 minutes, refresh tokens 8 hours and rotate | As in 05_SECURITY.md. Reusing a refresh token revokes the whole family. |
| 20 | Upload limit is 4 MB on Vercel, 25 MB locally | Vercel's request body cap is 4.5 MB. |
| 21 | Same Atlas cluster as Dishaara, separate `pramaan` database | The owner chose to reuse it. Reset only clears the `pramaan` database. |
| 22 | Floor plans are measured from vector PDFs (room rectangles, label inside, printed "Scale 1:N"); raster plans get a LOW "not measured" flag | Architects export CAD plans as vector PDFs, which measure exactly. Segmenting scanned plans reliably needs real samples. Advisory only, as the PS asks. |
| 23 | Tables come from the PDF text layer (pdfplumber). Fee receipts must add up; faculty lists must match the faculty count in records | Covers FR-DOC-06 and the "totals add up" intra-document check. Scanned tables are not parsed. |
