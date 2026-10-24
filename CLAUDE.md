# PRAMAAN (SIH26261)

AI-assisted validation of AICTE approval applications: completeness, expiry, cross-document and records consistency,
tamper indicators, issuer verification (signed QR + reference lookup), infrastructure photo checks, alerts, audit chain.
Spec: docs/pramaan-spec/ (01 SRS … 06 build plan). This build is the **Vercel + MongoDB edition** of that spec:
FastAPI as one Vercel Python function (api/index.py → pramaan/main.py), MongoDB Atlas for all data and files,
React console (src/), framework-free widget (public/widget/v1/pramaan.js), two mock host portals (public/host-a, host-b).
Runs in LITE mode only (no GPU, no OCR/handwriting model on serverless). Optional vision model via GROQ_KEY.

Live: https://pramaan-sih26.vercel.app (project domain, follows each prod deploy).

## Working agreements
- No regulatory numbers in code: rule packs in rulepacks/*.yaml, marked demo_value: true.
- Severity only from the rule pack. Anomaly wording: "indicator, requires verification", never forged/fake.
- Never fabricate metrics. Evaluation page shows measured numbers only.
- Fictional issuers and institutions only, all "(mock)". No real logos, names or personal data.
- Every check: rule/detector id, flag code with severity, evidence, test.
- Failing check becomes a CHECK_ERROR flag, never a failed report.

## Commands
- Tests: `.venv/Scripts/python -m pytest -q tests`
- Local: `.venv/Scripts/python -m uvicorn pramaan.main:app --port 8010` (in-memory Mongo, auto-seeds, password demo-local) and `npm run dev`
- Reseed (Atlas): `.venv/Scripts/python -m pramaan.seed` with MONGODB_URI etc. in the env (writes private/DEMO_LOGINS.md)
- Regenerate sample files: `python -m pramaan.seed --samples public/samples` (keys are deterministic, so samples verify)
- Deploy: `vercel deploy --prod --yes` then re-alias. Python 3.14 on Vercel; bundle must stay under 500 MB (no OpenCV).
- Secrets: Vercel env only. private/ is gitignored (SEED_TOKEN, DEMO_PASSWORD).
