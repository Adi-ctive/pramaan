# PRAMAAN (SIH26261)

AI-assisted validation of AICTE approval applications: completeness, expiry, cross-document and records consistency,
tamper indicators, issuer verification (signed QR, PDF signatures, reference lookup), infrastructure photo checks, alerts, audit chain.
New session or account: read docs/HANDOFF.md, then docs/CONVERSATION-LOG.md. Keep both current and pushed.
Spec: docs/pramaan-spec/. Differences from the spec and why: docs/DECISIONS.md. Status: docs/PROGRESS.md.
Backend: FastAPI (pramaan/), MongoDB (Atlas or mongomock). Console: React (src/). Widget: public/widget/v1/pramaan.js.
Mock portals: public/host-a, public/host-b. LITE mode on CPU (hosted on Vercel); FULL mode locally on the GPU (requirements-full.txt).
Models are behind pramaan/providers.py and named by role. Agents (LangGraph, Ollama qwen2.5:7b-instruct) in pramaan/agents/ fall back to the DAG in pramaan/engine.py.
Local AI worker (pramaan/worker.py) runs FULL mode plus agents for the hosted site; it polls Atlas, no port opened.

Live: https://pramaan-sih26.vercel.app (Vercel project "pramaan", project domain). Atlas: Dishaara cluster, database "pramaan".

## Working agreements
- No regulatory numbers in code: rule packs in rulepacks/*.yaml, marked demo_value: true.
- Severity only from the rule pack. Anomaly wording: "indicator, requires verification", never forged/fake.
- Never fabricate metrics. Evaluation shows measured numbers only.
- Demo issuers and institutions are fictional and marked "(mock)". No government logos or branding.
- Real college documents and photos: allowed with permission, only in gitignored realdata/, never committed, published or
  sent to any external service, personal IDs and phone numbers masked. Score them with `python tasks.py eval-real`.
- Every check: rule/detector id, flag code with severity, evidence, test.
- Failing check becomes a CHECK_ERROR flag, never a failed report.
- Document text reaches an LLM only inside <document_data>.

## Commands (python tasks.py <target>; Makefile wraps the same)
- secrets, up, down, seed, demo, test, e2e, eval, probe, cron
- FULL mode: MODE=FULL in env or .env. Agents: AGENT_MODE=on|off (needs Ollama). Worker: `python tasks.py worker` (reads .env.worker).
- Deploy: `vercel deploy --prod --yes`. Python 3.14 on Vercel, bundle under 500 MB (no OpenCV, no torch).
- Seed Atlas: POST /api/admin/seed then /api/admin/seed-next until done (X-Seed-Token from private/SECRETS.md).
- Secrets live in Vercel env and private/ (gitignored). Never commit them.
