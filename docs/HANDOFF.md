# Handoff: read this first

For any new Claude session or account working on PRAMAAN. It records what was built, what the owner asked for, and how
they like to work. Keep it current: add a dated line to the log at the end of every session.

## The project in one paragraph

PRAMAAN is our Smart India Hackathon 2026 entry for problem statement SIH26261 (AICTE: AI-assisted validation of approval
application documents). An institution uploads its documents through a portal widget. The engine checks completeness, expiry,
cross-document consistency, records, tamper indicators, issuer verification and infrastructure photos, then raises flags with
evidence. An AICTE officer reviews them in the console. It is hosted on Vercel with a MongoDB Atlas backend.

- Live: https://pramaan-sih26.vercel.app (click "Enter as Senior Officer")
- Code: C:\projects\pramaan, GitHub https://github.com/Adi-ctive/pramaan (public). Commit as adictiveofficial, never set an author email.
- Spec pack: docs/pramaan-spec/ (written in an earlier chat). Changes from the spec and why: docs/DECISIONS.md.
- Status and measured numbers: docs/PROGRESS.md. Demo script: docs/DEMO.md.
- Secrets: private/SECRETS.md (demo password, SEED_TOKEN, CRON_SECRET), .env.worker (Atlas URI). Both gitignored. Never commit or print them.
- Atlas: the Dishaara cluster, database "pramaan". The Dishaara project (C:\projects\Argus) shares the cluster but not the database.

## Machine

- Windows 11 laptop, RTX 4050 6 GB, Python venv in .venv (Python 3.14), Node for the console.
- Disk is nearly full (about 21 GB free on 25 Oct). Check `df -h /c` before any download. Datasets go only in realdata/ (gitignored).
- Ollama installed in %LOCALAPPDATA%\Programs\Ollama, model qwen2.5:7b-instruct pulled.
- Close every process you start (servers, worker, Ollama, Playwright) and confirm with Get-Process. Strays crashed the laptop once.

## Modes

- LITE: CPU only, what Vercel runs (225 MB bundle cap, so no torch or OpenCV). Digital PDFs read from the text layer.
- FULL: local GPU (`MODE=FULL`, requirements-full.txt). docTR OCR, TrOCR handwriting, EasyOCR Hindi, Grounding DINO counts,
  CLIP room type, Qwen 7B through Ollama for agents and summaries.
- Agents (Phase 7): eight LangGraph agents. On in FULL, off in LITE. Fall back to the fixed pipeline (the DAG) on any failure.
- Local AI worker: `python tasks.py worker` on the laptop polls Atlas and runs FULL plus agents for the hosted site.
  The console then shows "Local AI: online" and a "Re-check with local AI" button.

## Commands

```
python tasks.py test          # 28 unit/integration tests
python tasks.py e2e           # 9 Playwright acceptance tests
python tasks.py eval          # synthetic evaluation (MODE=FULL for model metrics)
python tasks.py fetch-public  # public dataset subsets into realdata/public
python tasks.py eval-public   # score them, writes docs/EVAL-PUBLIC.md
python tasks.py eval-real     # our own college files in realdata/, writes docs/EVAL-REAL.md (not committed)
python tasks.py worker        # local AI backend for the live site
python scripts/verify_agents.py   # Phase 7 checks with the real LLM
vercel deploy --prod --yes    # deploy
```

Reseed the live site: POST /api/admin/seed, then /api/admin/seed-next until done (X-Seed-Token header).

## How the owner works

- Short replies, three sentences at most unless they ask for a report. Plain words, no em dashes, no semicolons.
- They do not open attached files. Put plans and findings in the chat reply.
- Never guess. If something is unknown, say so or measure it. Never invent metrics.
- Settle loose ends yourself by measurement. Do not end with a list of things waiting on them.
- Real college data is allowed with permission, kept only in realdata/, never committed or sent to any outside service.
- Team material (decks, vehicle recordings, code from other teams) is confidential.

## What was built, in order (24 to 25 Oct 2026)

1. Spec phases 0 to 10: backend, rule packs, mock issuers and portals, widget, checks, forensics, signatures, QR, reports,
   alerts, audit chain, console, evaluation. Deployed to Vercel with Atlas.
2. Console redesigned twice after the owner said it was hard to understand: landing page with demo roles, traffic-light queue,
   guided problem-by-problem review.
3. Add-ons: Hindi OCR and transliterated name match, tables (fee totals, faculty count), vector floor plans, video frames,
   two-step sign-in screen.
4. Fixed evidence boxes drawn in the wrong place.
5. Spec amended to allow real college data (DECISIONS #24) with realdata/truth.csv and eval-real.
6. Public datasets, small subsets: MIT Indoor 67 (360 photos, room type 87.5%), CubiCasa5K (60 plans, room recall 23%),
   IIIT-HW-Dev (download failed, still pending).
7. Uploaded to GitHub and made public.
8. Phase 7 multi-agent orchestration with Ollama. Same flags as the DAG on all seeded apps, no extra flags found, 4 to 25
   times slower. Agents only help on cases the rules miss, so a harder test set is needed to show their value.

## Open items

- A large test set (thousands of real documents and images) to show capacity. Started 25 Oct, see the log.
- Tamper detection on real documents: classical checks fail there. Train a small learned detector on T-SROIE (FULL mode).
- A harder test set where fixed rules miss, to measure whether agents add anything.
- Hindi handwriting scoring.

## Session log

- 25 Oct 2026: Phase 7 committed (afc70ba), pushed, deployed. FULL numbers in PROGRESS.md. Owner asked for public datasets
  in the thousands and this handoff file.
- 25 Oct 2026, large test set (in progress when written):
  - `python scripts/fetch_public_data.py sifta tsroie rvl sroie forgery mit_full cubicasa_1000` fetches them. Anonymous Hugging Face
    downloads hit 429 when fast, so the script retries with backoff and skips files already on disk. Just rerun it.
  - Sets: RVL-CDIP (350 per type, 16 types, about 5,600 real scans), SROIE 973 genuine receipts, T-SROIE 986 tampered receipts,
    SIFTA 192, photo forgery set (CASIA/COCO/Paris, about 8,400 test images with masks), MIT Indoor 67 all 15,620, CubiCasa5K 1,000,
    IIIT-HW-Dev (archive at realdata/public/iiit.tar.gz, resume with curl -C -).
  - Not used: DocTamper. Its owners give it out by email request for non-commercial use. A Hugging Face re-upload exists but skips that.
  - Scorer: `python tasks.py eval-large [part ...]` (pramaan/evaluate_large.py), writes docs/EVAL-LARGE.md and .json. Parts:
    rvl sroie sifta forgery mit_full cubicasa iiit. LITE does tamper checks, MODE=FULL adds OCR, room type, Hindi.
  - Found on real data: the noise detector flagged 100% of genuine RVL scans. Cause: real scanners clip paper to pure white, so
    noise is zero and every blank block looked odd. Fixed in forensics.py 1.1.0 (MIN_DIFF 2 grey levels, 6 MP size cap after a
    35 MP SROIE scan ran out of memory). Synthetic forgery F1 stays 1.0.
  - Still true after the fix: on real receipts the noise and copy-move checks flag genuine and tampered receipts at about the same
    rate (SROIE/T-SROIE precision 51%, false alarms 74%). Classical checks cannot find real text tampering. A learned detector
    trained on T-SROIE is the next real step.
  - Date parser: two-digit years and month names added. Real receipt dates read went from 725 to 968 of 973.
  - Measured (FULL, 25 Oct): OCR Model on 973 real SROIE receipts reads the total on 98.3% and the date on 95.3%, company name
    CER 17%, 352 ms per receipt. SIFTA after the fix: precision 62%, recall 76%, false alarms 47%.
  - RVL-CDIP sample complete: 5,600 documents, 350 of each of the 16 types (realdata/public/rvl_cdip/sample).
  - Still downloading at this point: photo forgery set (resumable), MIT Indoor full, CubiCasa to 1,000, IIIT archive.
  - RVL-CDIP 5,600 (forensics 1.1.0): false alarms 25.4% (was 100%). Worst: handwritten 55%, adverts 46%, email 7%.
    OCR on 1,000 of them also ran (numbers in docs/EVAL-LARGE.json, rvl.ocr).
  - Split test (scratchpad, 704 RVL, 244+247 receipts, SIFTA, 12 synthetic): "much cleaner block" half of the noise rule has
    0.6% false alarms on RVL, 0.8% on receipts, 3.1% on SIFTA real, and still 100% on synthetic tampering. The "much noisier
    block" half caused nearly all false alarms (25% RVL, 71% receipts) with no separation on receipts. Copy-move pairs: synthetic
    clones 1,891 to 2,202, genuine receipts 95th percentile 851, 99th 1,783.
  - Applied, forensics 1.2.0 (UNTESTED when the session stopped): noise flag on the cleaner side only, copy-move min_pairs 500 to 1500.

## STOPPED HERE (25 Oct, owner switching accounts)

All processes were stopped on purpose. Nothing is running. Resume in this order:
1. Verify forensics 1.2.0: `python tasks.py test` (28 must pass) and the synthetic forgery eval
   (`evaluate.anomalies(pack, 12)` after `pack, _ = rulepack.parse(rulepack.load_file("aicte-demo-2026-27.yaml"))`). The pixel
   rows and "copy-move inside page" must stay at F1 1.0. The two PDF-signature rows fail when run standalone because trust roots
   come from the database. That is expected, not a bug.
2. Rescore with 1.2.0: `python tasks.py eval-large rvl sroie sifta` (LITE), then `MODE=FULL python tasks.py eval-large rvl sroie`.
3. Resume downloads: `python scripts/fetch_public_data.py forgery mit_full cubicasa_1000`. At the stop: forgery 6,309 files on
   disk (images plus masks, about 13,800 total), MIT Indoor 360 of 15,620, CubiCasa 462 of 1,000. Then
   `python tasks.py eval-large forgery mit_full cubicasa` (mit_full needs MODE=FULL).
4. IIIT archive: 1,771,133,615 of 1,822,862,305 bytes. In realdata/public run
   `curl -C - -o iiit.tar.gz https://cvit.iiit.ac.in/images/Projects/wordlevel-Indicscripts/IIIT-HW-Hindi_v1.tar.gz`,
   then `python scripts/fetch_public_data.py iiit` and `MODE=FULL python tasks.py eval-large iiit`.
5. Write the final numbers into docs/PROGRESS.md (new "Large public test set" section), DECISIONS.md (#32 noise cleaner side only,
   #33 copy-move 1500, #34 date formats, #35 DocTamper not used), README (eval-large), this file and CONVERSATION-LOG.md.
6. Commit as adictiveofficial, push, deploy (`vercel deploy --prod --yes`, forensics changed). Close every process you start.
