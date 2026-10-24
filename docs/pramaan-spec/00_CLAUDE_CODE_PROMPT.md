# 00 — Claude Code Kickoff Prompt

## How to use
1. Create an empty folder `pramaan/` and run `git init` in it.
2. Copy this whole spec pack (files `00`–`06`) into `pramaan/docs/`.
3. Open Claude Code in `pramaan/` and paste everything inside the box below as your first message.

---

```text
You are building PRAMAAN, a prototype for Smart India Hackathon problem statement SIH26261
(AICTE: AI-Powered Application Validation, Document Authentication and Regulatory Compliance
Verification). The complete specification is in ./docs:

  docs/01_SRS.md            requirements (FR/NFR IDs, acceptance criteria, traceability to the PS)
  docs/02_ARCHITECTURE.md   services, repo layout, pipeline, multi-agent design, data model,
                            flag schema, rule-pack format, API surface, mock services
  docs/03_UI_DESIGN.md      console, widget, mock host portals, demo script
  docs/04_STACK.md          exact technology choices (all free/open source) + GPU notes
  docs/05_SECURITY.md       threat model, auth, RBAC, encryption, audit, retention, AI safety
  docs/06_BUILD_PLAN.md     phases 0–10 with Definition of Done, seeded demo applications,
                            working agreements

STEP 1 — Read every file in ./docs fully before writing any code. Then create CLAUDE.md at the
repo root containing: a 10-line project summary, the working agreements from 06_BUILD_PLAN.md,
the coding rules below, and the commands from the Makefile once it exists.

STEP 2 — Create docs/PROGRESS.md with a table of phases 0–10 (status, what works, known issues,
next step). Keep it updated after every phase and whenever you stop.

STEP 3 — Execute the build plan phase by phase, starting at Phase 0. For each phase:
  a) list the tasks you will do (use your todo list),
  b) implement them,
  c) run the phase's Definition of Done checks for real (start services, run tests, call
     endpoints, open pages with Playwright where UI is involved),
  d) fix until the DoD passes, or record precisely why it cannot pass,
  e) update docs/PROGRESS.md and commit with message "phase N: <summary>",
  f) continue to the next phase without waiting for me.

ENVIRONMENT
- Host: Windows 11 with Docker Desktop on WSL2, 32 GB RAM, GPUs: RTX 5060 Ti (Blackwell, needs
  CUDA 12.8+ builds) and RTX 2000 Ada. Ollama runs natively on the host; containers reach it at
  http://host.docker.internal:11434. Pull models with `ollama pull qwen2.5vl:7b` and
  `ollama pull qwen2.5:7b-instruct` (tell me if pulls are needed and I can't be reached: proceed
  in LITE mode and note it).
- In Phase 0 run scripts/gpu_probe.py and record results in docs/VERSIONS.md. If PaddlePaddle GPU
  does not support the Blackwell card, use the RTX 2000 Ada for it, or CPU, or set
  PROVIDER_OCR=doctr. Do not stall on this.
- Everything must also run with MODE=LITE on CPU only.

CODING RULES
- Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Celery, LangGraph, Pydantic v2; React + Vite + TS
  + Tailwind + shadcn/ui for the console; framework-free TS + Shadow DOM for the widget.
- Every ML model behind a provider interface; every external system behind an adapter; choose
  implementations by config. In UI text and reports, name models by role ("OCR Model",
  "Handwriting Model", "Object Detector", "Reasoning LLM"), not by brand.
- No regulatory number hard-coded in Python: put it in a rule pack, marked demo_value: true.
- Every finding is a Flag per the schema in 02_ARCHITECTURE.md §9 with evidence; severity comes
  from the rule pack, never from an LLM. Anomaly wording is always "indicator — requires
  verification", never "forged/fake".
- Agents get read-only typed tools only; document text enters prompts only inside a
  <document_data> envelope; any agent failure falls back to the deterministic pipeline.
- Fail soft: a crashing check yields a MANUAL_REVIEW flag with the error, never a failed report.
- Security controls in 05_SECURITY.md are part of the build, not optional.
- Never use government logos or branding. Mock portals are labelled "(mock)". Real documents and photos from our own college are allowed with permission. They live only in the gitignored local folder realdata/, are never committed, published or sent to any external service, and personal IDs and phone numbers are masked. Synthetic data remains for forgery tests and large-scale metrics. Mock portals must not use AICTE or other government logos or branding. (Amended 24 Oct 2026.)
- Never fabricate results or metrics. Report real measured numbers, including bad ones.
- Write tests alongside code (pytest, vitest, Playwright). Keep `make test` green.
- Pin dependency versions; record them in docs/VERSIONS.md.
- Prefer small, reviewable commits; one commit at least per phase.

AUTONOMY
- Work continuously through all phases. Do not stop to ask for confirmation between phases.
- Only stop to ask me if a decision is irreversible AND genuinely ambiguous, or if you are
  blocked by something only I can provide (e.g. team infrastructure photos for synth/photos/ —
  until then, generate placeholder room images or use openly licensed images and mark them so).
- If you run out of context, make sure docs/PROGRESS.md states exactly where to resume, then
  continue from it in the next session.

FIRST ACTION: read ./docs, write CLAUDE.md and docs/PROGRESS.md, then start Phase 0.
```

---

## Resume prompt (for later sessions)
```text
Read CLAUDE.md, docs/PROGRESS.md and the relevant docs/0x files. Resume the build exactly where
PROGRESS.md says, verify the last phase's Definition of Done still passes, then continue through
the remaining phases without stopping, updating PROGRESS.md and committing after each phase.
```
