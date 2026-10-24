# 02 — Architecture Design

## 1. Architectural principles
1. **Headless core, many faces.** The validation engine knows nothing about any specific portal. Portals connect through API, widget, webhooks and slot mappings.
2. **Providers for models, adapters for systems.** Every ML model sits behind a provider interface (`OCRProvider`, `HTRProvider`, …). Every external system sits behind an adapter (`RecordsAdapter`, `VerificationAdapter`, `NotificationAdapter`). Swapping one is a config change.
3. **Deterministic where it matters, agentic where it helps.** Rules, hashes, signatures, scoring and audit are plain code. Agents plan, route, resolve conflicts and explain, using those as tools.
4. **Evidence-first.** No finding exists without a flag object carrying its evidence.
5. **Fail soft.** Any check that errors becomes `MANUAL_REVIEW`. It never crashes the report.
6. **Everything is versioned.** Rule pack, model versions and code version are stamped on every report.

## 2. System context

```
              ┌──────────────────────┐        ┌──────────────────────┐
              │ Host A: Approval     │        │ Host B: University   │
              │ Portal (mock)        │        │ Affiliation (mock)   │
              │ + PRAMAAN widget     │        │ + PRAMAAN widget     │
              └─────────┬────────────┘        └──────────┬───────────┘
          server-to-server (API key)            server-to-server
          browser→ upload session token          browser→ upload token
                        │                                │
                        ▼                                ▼
              ┌──────────────────────────────────────────────────────┐
              │                 Caddy (TLS reverse proxy)            │
              └───────┬───────────────────────┬──────────────────────┘
                      ▼                       ▼
            ┌──────────────────┐     ┌──────────────────┐
            │ PRAMAAN API      │     │ Officer Console  │
            │ (FastAPI)        │◀───▶│ (React SPA)      │
            └───┬────┬────┬────┘     └──────────────────┘
                │    │    │ enqueue
                │    │    ▼
                │    │  ┌──────────────┐   ┌───────────────────────────┐
                │    │  │ Redis (queue)│──▶│ Workers (Celery)          │
                │    │  └──────────────┘   │  q:cpu  q:gpu  q:agent    │
                │    │                     │  Pipeline + Agent graph   │
                │    │                     └──┬──────┬──────┬──────────┘
                ▼    ▼                        │      │      │
        ┌──────────┐ ┌──────────┐             │      │      ▼
        │PostgreSQL│ │ MinIO    │◀────────────┘      │   ┌──────────────┐
        │+pgvector │ │(docs,enc)│                    │   │ Ollama (host)│
        └──────────┘ └──────────┘                    │   │ VLM + LLM    │
                                                     ▼   └──────────────┘
                         ┌───────────────────┐  ┌────────────────────┐
                         │ Mock Records svc  │  │ Mock Issuer svc    │
                         │ (AICTE-like data) │  │ (verify, keys, CA) │
                         └───────────────────┘  └────────────────────┘
        Side services: ClamAV (upload scan), Mailpit (email), Mock Hosts backend
```

## 3. Services
| Service | Tech | Responsibility |
|---|---|---|
| `api` | FastAPI | Public `/api/v1` for hosts, console backend `/console/v1`, auth, upload sessions, report retrieval, webhooks out |
| `worker-cpu` | Celery | Preprocessing, PDF parsing, rules, consistency, forensics (classical), verification, reports, alerts |
| `worker-gpu` | Celery (concurrency 1) | OCR, HTR, classifier, detectors, embeddings, infrastructure CV. Models loaded lazily and cached |
| `worker-agent` | Celery + LangGraph | Runs the agent graph per application; calls tools, which dispatch to the cpu and gpu queues |
| `mock-records` | FastAPI + Postgres schema `records` | AICTE-like institutional records over HTTP (the Records Adapter target) |
| `mock-issuer` | FastAPI | Simulated issuers: reference lookup, QR public keys, PDF-signing CA, latency, downtime and mismatch toggles |
| `mock-hosts` | FastAPI + static pages | Host A and Host B: their own simple forms, embedding the widget, creating upload sessions server-side, receiving webhooks |
| `console` | React + Vite | Officer, admin and auditor UI |
| `widget` | TypeScript bundle (no framework) | Embeddable upload slots and live feedback |
| infra | Docker | `postgres` (pgvector), `redis`, `minio`, `clamav`, `mailpit`, `caddy` |
| `ollama` | native on host | VLM and LLM serving |

## 4. Repository layout
```
pramaan/
├─ CLAUDE.md                     # working rules for Claude Code (copied from 00 prompt)
├─ docs/                         # this spec pack (01–06)
├─ docker-compose.yml            # infra + services
├─ docker-compose.gpu.yml        # GPU override for worker-gpu
├─ .env.example
├─ Makefile                      # make up, seed, demo, test, eval, lite
├─ backend/
│  ├─ pyproject.toml
│  ├─ pramaan/
│  │  ├─ api/                    # routers: hosts, applications, documents, reports, console, admin, auth
│  │  ├─ core/
│  │  │  ├─ config.py            # pydantic-settings, MODE=FULL|LITE
│  │  │  ├─ models/              # SQLAlchemy ORM
│  │  │  ├─ schemas/             # Pydantic: Flag, Report, Field, Region…
│  │  │  ├─ rules/               # rule-pack loader, validator, evaluator (json-logic-like)
│  │  │  ├─ pipeline/            # deterministic DAG + stage functions
│  │  │  ├─ scoring.py           # risk score from flags (weights in rule pack)
│  │  │  ├─ audit.py             # hash-chained append
│  │  │  ├─ security/            # authn, rbac, crypto, masking, upload sanitising
│  │  │  └─ storage.py           # MinIO client, content addressing
│  │  ├─ providers/              # model interfaces + implementations
│  │  │  ├─ base.py
│  │  │  ├─ ocr/                 # paddle.py, doctr.py, tesseract.py
│  │  │  ├─ htr/                 # trocr.py, vlm.py
│  │  │  ├─ classify/            # vlm.py, keyword.py (LITE)
│  │  │  ├─ detect/              # open_vocab.py (Grounding DINO), yolo.py
│  │  │  ├─ extract/             # vlm_kie.py, regex_kie.py
│  │  │  ├─ embed/               # text.py, image.py (CLIP)
│  │  │  ├─ forensics/           # ela.py, noise.py, copymove.py, pdf_forensics.py, text_forensics.py
│  │  │  ├─ scene/               # room_classifier.py (CLIP zero-shot), counter.py
│  │  │  └─ llm/                 # ollama.py, null.py (LITE)
│  │  ├─ adapters/
│  │  │  ├─ records/             # base.py, mock_http.py
│  │  │  ├─ verification/        # base.py, qr.py, pdf_signature.py, reference_lookup.py
│  │  │  └─ notify/              # email.py, webhook.py, inapp.py
│  │  ├─ agents/                 # LangGraph graph, agent prompts, tool registry, guards
│  │  ├─ workers/                # celery app, task routing
│  │  └─ reports/                # HTML/PDF templates (Jinja2 + WeasyPrint)
│  ├─ rulepacks/
│  │  ├─ aicte-demo-2026-27.yaml
│  │  └─ university-affiliation-demo.yaml
│  ├─ migrations/                # Alembic
│  └─ tests/
├─ services/
│  ├─ mock_records/
│  ├─ mock_issuer/
│  └─ mock_hosts/
├─ frontend/
│  ├─ console/                   # React app
│  └─ widget/                    # embeddable bundle
├─ synth/                        # synthetic data + forgery generator
│  ├─ generate.py
│  ├─ templates/                 # document templates per type
│  ├─ fonts/                     # handwriting fonts (OFL-licensed)
│  ├─ forgeries.py
│  └─ photos/                    # team-captured lab/classroom photos (gitignored)
└─ eval/
   ├─ run_eval.py
   └─ metrics.py
```

## 5. Processing pipeline (deterministic baseline DAG)

Triggered by `POST /api/v1/applications/{id}/submit` or by any document upload (incremental mode).

```
A. INTAKE
   A1 verify host + rule pack + category (FR-CHK-01)
   A2 freeze application version; snapshot form fields
B. PER-DOCUMENT  (parallel per document; incremental: only new or changed docs)
   B1 sanitise: magic-byte type check, size limit, ClamAV scan, PDF safety (no JS execution)
   B2 store: SHA-256 → MinIO (encrypted), dedupe by hash
   B3 render: PDF text-layer detection; rasterise pages @300dpi; video → keyframes
   B4 preprocess: deskew, denoise, perspective, orientation
   B5 classify → doc_type + confidence; slot mismatch check
   B6 read: native text OR printed OCR (words + boxes + conf); tables
   B7 regions: detect handwriting / stamp / seal / signature / QR / photo regions
   B8 HTR on handwriting regions (confidence-gated)
   B9 field extraction per doc_type schema → normalise
   B10 fingerprints: pHash per page, text embedding, image embedding → pgvector
   B11 forensics: ELA, noise, copy-move (images); PDF structure/metadata; text-level
   B12 verification route: QR? → QR verify; signed PDF? → signature verify; ref no + issuer? → lookup
C. PER-APPLICATION
   C1 fetch institution records (RecordsAdapter)
   C2 checklist completeness + expiry
   C3 consistency: intra-doc, cross-doc, app↔records (entity resolution)
   C4 plausibility: dates, identifiers, issuer limits, holidays
   C5 duplicates: hash/embedding search across all institutions and years
   C6 infrastructure: room type, object counts vs claims/norms, EXIF geo/time, reuse
   C7 carry-forward of previously verified documents (FR-REC-02)
D. AGGREGATE
   D1 collect flags → severity from rule pack → risk score
   D2 report JSON → HTML/PDF; institution rectification view
   D3 case summary (LLM, grounded) → critic validation → fallback template
   D4 alerts (in-app, email, webhook) per alert rules
   D5 audit entries for everything above; webhook `validation.completed`
```

Every stage writes `stage_runs` (status, duration, model versions, error) to support the NFR timing metrics and the processing timeline in the UI.

## 6. Multi-agent architecture (LangGraph)

### 6.1 Why agents here
The baseline DAG runs every check in a fixed order. Agents add three things:
- **adaptive depth**, such as escalating forensics only when cheap signals are suspicious, or re-reading a region at higher resolution when OCR and the VLM disagree;
- **route selection** for verification and claim-to-evidence matching;
- **explanation** grounded in flags.

Agents never decide outcomes. Severity and status come from rules and tools.

### 6.2 Graph
```
                ┌──────────────┐
   start ──────▶│ Orchestrator │  builds Plan(steps[]) from checklist + manifest
                └──────┬───────┘
      ┌───────────┬────┴─────┬──────────────┬───────────────┐
      ▼           ▼          ▼              ▼               ▼
 ┌─────────┐ ┌──────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────────┐
 │Document │ │Forensics │ │Verification│ │Consistency  │ │Infrastructure│
 │ Agent   │ │ Agent    │ │ Agent      │ │ Agent       │ │ Agent        │
 └────┬────┘ └────┬─────┘ └─────┬──────┘ └──────┬──────┘ └──────┬───────┘
      └───────────┴─────────────┴───────┬───────┴───────────────┘
                                        ▼
                                ┌──────────────┐
                                │ Case Writer  │  summary citing flag IDs only
                                └──────┬───────┘
                                       ▼
                                ┌──────────────┐
                                │ Critic       │  validates evidence + citations;
                                └──────┬───────┘  loops back once or falls back
                                       ▼
                                      end
```

### 6.3 Agent responsibilities and tools
| Agent | Decides | Tools (typed, read-only except `emit_flag`) |
|---|---|---|
| Orchestrator | Which documents need which stages; parallelism; when to re-plan | `get_checklist`, `get_manifest`, `get_records_summary`, `dispatch(step)` |
| Document Agent | Reading strategy per document (native text vs OCR vs VLM); resolves field conflicts between methods; triggers high-res re-read or HTR | `ocr`, `htr`, `detect_regions`, `extract_fields`, `crop_region`, `compare_field_candidates`, `emit_flag` |
| Forensics Agent | Escalation: cheap checks first, deeper checks if a signal crosses the rule-pack threshold | `ela`, `noise_map`, `copy_move`, `pdf_history`, `text_forensics`, `duplicate_search`, `emit_flag` |
| Verification Agent | Route per document: QR / digital signature / reference lookup / manual; retry and back-off on downtime | `qr_verify`, `pdf_sig_verify`, `issuer_lookup`, `emit_verification` |
| Consistency Agent | Which entity pairs to compare; explains mismatches | `entity_resolve`, `get_record_field`, `get_doc_field`, `evaluate_rule`, `emit_flag` |
| Infrastructure Agent | Maps each claimed facility to evidence; builds detection prompts from claims ("computer monitor" for a computer lab) | `room_classify`, `count_objects`, `exif_check`, `duplicate_search`, `emit_flag` |
| Case Writer | Plain-language summary for officers; separate plain list for institutions | `list_flags`, `get_flag` |
| Critic | Rejects flags without evidence and summaries citing unknown flag IDs or stating unsupported facts | `list_flags`, `validate_summary` |

**Guards:**
- `emit_flag` validates the schema.
- Severity is looked up from the rule pack by `flag_code`. Agents cannot set severity.
- Tools have no write access to records, rules or decisions.
- Document text reaches the LLM only inside a `<document_data>` envelope, with a system instruction that it is untrusted data.
- Max steps per agent run; global timeout; on any agent failure the deterministic DAG completes the remaining stages.

**LITE mode:** the `NullLLM` provider makes the graph degrade to the deterministic DAG. The case summary uses a Jinja template.

### 6.4 Agent traces
Each agent step is stored in `agent_traces` (agent, step, tool, args digest, result digest, tokens, latency). It is visible in the console under "Processing timeline → Why".

## 7. Provider interfaces (Python)
```python
class OCRProvider(Protocol):
    name: str; version: str
    def read(self, image: np.ndarray, langs: list[str]) -> list[Word]  # text, bbox, conf

class HTRProvider(Protocol):
    def read_region(self, crop: np.ndarray, lang_hint: str) -> TextResult  # text, conf

class ClassifierProvider(Protocol):
    def classify(self, page_images: list[np.ndarray], text: str, labels: list[str]) -> list[Label]

class DetectorProvider(Protocol):
    def detect(self, image: np.ndarray, prompts: list[str], box_thr: float) -> list[Detection]

class ExtractorProvider(Protocol):
    def extract(self, doc: ParsedDoc, schema: FieldSchema) -> list[FieldCandidate]

class EmbeddingProvider(Protocol):
    def embed_text(self, texts: list[str]) -> np.ndarray
    def embed_image(self, images: list[np.ndarray]) -> np.ndarray

class LLMProvider(Protocol):
    def chat(self, messages, tools=None, response_schema=None) -> LLMResult
```
A registry (`providers/registry.py`) picks implementations from config (`MODE`, `PROVIDER_OCR=paddle|doctr|tesseract`, …). UI and report labels use each provider's **role name** ("OCR Model"), not the brand.

**Default mapping (FULL mode):**

| Role | Default | Fallback |
|---|---|---|
| OCR Model | PaddleOCR | docTR (PyTorch) → Tesseract |
| Handwriting Model | VLM via Ollama | TrOCR (English) |
| Document Classifier | VLM zero-shot over the taxonomy | Keyword/regex classifier (LITE) |
| Field Extractor | VLM JSON-schema extraction plus regex validators | Regex/anchor-based extractor (LITE) |
| Region / Object Detector | Grounding DINO (open-vocabulary) | — |
| Scene Classifier | CLIP zero-shot | — |
| Embeddings | sentence-transformers multilingual; CLIP image | — |
| Reasoning LLM | Ollama text model (7–8B) | NullLLM (LITE) |

## 8. Data model (PostgreSQL)

Core tables (UUID PKs, `created_at`, `updated_at` everywhere):

```
hosts(id, name, rule_pack_id, webhook_url, webhook_secret_enc, status)
api_keys(id, host_id, prefix, hash, scopes[], expires_at, revoked_at)
slot_mappings(id, host_id, host_slot, canonical_slot, host_field, canonical_field)
upload_sessions(id, host_id, application_id, token_hash, expires_at)

users(id, email, name, password_hash, role, region, mfa_secret_enc, active)
rule_packs(id, key, version, effective_from, yaml, sha256, status[draft|active|retired])

applications(id, host_id, external_ref, institution_ref, category, rule_pack_id,
             status[draft|submitted|processing|ready|in_review|closed], risk_score,
             current_version, sla_due_at)
application_versions(id, application_id, version, form_fields_json_enc, submitted_at)
documents(id, application_id, version, slot, sha256, mime, size, storage_key,
          doc_type, doc_type_conf, page_count, superseded_by)
pages(id, document_id, index, image_key, width, height, text_layer bool)
words(id, page_id, text, bbox, conf, source[native|ocr|htr])         -- optional, can be JSONB on pages
regions(id, page_id, kind[handwriting|stamp|seal|signature|qr|photo|table],
        bbox, conf, data_json)
fields(id, document_id, key, raw_value, norm_value, page_id, bbox, conf,
       method, candidates_json)
fingerprints(id, document_id, page_id, phash, text_vec vector(768), img_vec vector(512))

flags(id, application_id, document_id NULL, code, category, severity, status,
      title, reason, evidence_json, rule_id, rule_pack_version, detector,
      detector_version, confidence, created_by[pipeline|agent:<name>],
      disposition[open|confirmed|dismissed|escalated], disposed_by, disposed_reason)
verifications(id, document_id, method[qr|pdf_sig|ref_lookup|carry_forward|manual],
              source, status, request_digest, response_digest, details_json,
              started_at, completed_at)
alerts(id, application_id, flag_id NULL, type, severity, recipients_role,
       channel[], status, due_at, sent_at, acked_by)
observations(id, application_id, user_id, text)
reports(id, application_id, version, json_key, html_key, pdf_key,
        rule_pack_version, model_versions_json, code_version, generated_at)
stage_runs(id, application_id, document_id NULL, stage, status, started_at,
           ended_at, error, model_versions_json)
agent_traces(id, application_id, agent, step, tool, args_digest, result_digest,
             tokens_in, tokens_out, latency_ms, created_at)
audit_log(seq bigserial, ts, actor_type, actor_id, action, object_type, object_id,
          payload_json, prev_hash, hash)     -- append-only, hash = sha256(prev_hash||canonical_json)
access_log(id, ts, user_id, ip, route, object_type, object_id, purpose)
retention_jobs(id, ran_at, purged_count, details_json)
eval_runs(id, started_at, dataset_version, metrics_json, report_key)
```

Mock records (separate schema `records`, served by `mock-records`):
```
institutions(aicte_id, name, society_name, address, state, region, lat, lon,
             established_on, type, status)
approvals(aicte_id, year, category, status, letter_ref)
programmes(aicte_id, year, programme, level, shift, approved_intake)
faculty(aicte_id, faculty_id, name, designation, qualification, joined_on)
accreditations(aicte_id, body, programme, valid_from, valid_to, ref)
nocs(aicte_id, type, issuer, ref, issued_on, valid_to)
undertakings(aicte_id, type, ref, due_on, status)
deficiencies(aicte_id, year, code, text, status)
payments(aicte_id, year, ref, amount, status)
application_history(aicte_id, year, category, outcome)
```

## 9. Flag schema (canonical)
```json
{
  "id": "FLG-7Q2K",
  "code": "DOC_EXPIRED",
  "category": "COMPLETENESS|VALIDITY|CONSISTENCY|ANOMALY|VERIFICATION|INFRASTRUCTURE|EXTRACTION",
  "severity": "HIGH|MEDIUM|LOW|INFO",
  "title": "Fire NOC has expired",
  "reason": "Valid-to date 2026-03-31 is before the application date 2026-10-20 (rule FIRE_NOC.expiry).",
  "evidence": [
    {"type": "field", "document_id": "...", "page": 1, "bbox": [x,y,w,h],
     "key": "valid_to", "value": "2026-03-31", "conf": 0.97},
    {"type": "rule", "rule_id": "FIRE_NOC.expiry", "pack": "aicte-demo-2026-27@1.2"}
  ],
  "expected": "valid_to ≥ submission_date",
  "observed": "2026-03-31",
  "detector": "rules-engine", "detector_version": "1.0.0",
  "confidence": 0.97,
  "recommended_action": "Request renewed Fire NOC",
  "institution_visible": true,
  "advisory_note": "Preliminary indicator; requires official verification."
}
```
Evidence types: `field`, `region` (bbox plus crop key), `heatmap` (image key plus regions), `record` (adapter, entity, field, value), `verification` (verification ID), `duplicate` (other document or application IDs plus similarity), `metadata` (key/value), `rule`.

## 10. Rule pack format (YAML)
> All numeric norms in demo packs are **illustrative placeholders**, labelled `demo_value: true`. They are not real APH figures.

```yaml
key: aicte-demo-2026-27
version: 1.2.0
effective_from: 2026-07-01
source_note: "Illustrative rules modelled on the structure of an approval handbook; values are demo placeholders."

taxonomy:            # document types + field schemas
  FIRE_NOC:
    label: "Fire Safety NOC"
    fields:
      issuer: {type: string, required: true}
      ref_no: {type: string, required: true, pattern: "^FS/[A-Z]{2}/\\d{4}/\\d{5}$"}
      addressee: {type: entity_name, required: true}
      address: {type: address}
      issued_on: {type: date, required: true}
      valid_to: {type: date, required: true}
    requires_regions: [stamp, signature]
    verification: [qr, ref_lookup]
    issuer_max_validity_days: 1095
    retention_days: 2555

categories:
  EOA:
    label: "Extension of Approval"
    required_slots: [SOCIETY_REG, LAND_LEASE, FIRE_NOC, BUILDING_COMPLETION,
                     AFFIDAVIT_GENERAL, ACCREDITATION, FEE_RECEIPT, INFRA_PHOTOS]
    conditional_slots:
      - slot: ACCREDITATION
        when: "app.has_accredited_programmes == true"

rules:
  - id: FIRE_NOC.expiry
    code: DOC_EXPIRED
    applies_to: FIRE_NOC
    expr: {">=": [{"var": "doc.valid_to"}, {"var": "app.submitted_on"}]}
  - id: XDOC.society_name_match
    code: NAME_MISMATCH
    kind: entity_match
    left: "SOCIETY_REG.society_name"
    right: ["LAND_LEASE.lessee", "FIRE_NOC.addressee", "app.society_name"]
    threshold: 0.88
  - id: REC.intake_match
    code: INTAKE_MISMATCH_RECORDS
    expr: {"==": [{"var": "app.current_intake"}, {"var": "records.approved_intake"}]}

plausibility:
  - id: DATE.before_establishment
    code: DATE_IMPLAUSIBLE
    expr: {">=": [{"var": "doc.issued_on"}, {"var": "records.established_on"}]}

infrastructure:
  facilities:
    COMPUTER_LAB:
      room_labels: ["computer lab", "computer laboratory"]
      count_objects: {"computer monitor": {per_claim_field: "claimed_workstations"}}
      tolerance_pct: 15
    CLASSROOM:
      room_labels: ["classroom", "lecture hall"]
      count_objects: {"student desk": {per_claim_field: "claimed_seats"}}
  exif:
    max_distance_km: 2.0
    capture_window_days: 180

severity:            # code → severity (agents cannot override)
  DOC_MISSING: HIGH
  DOC_EXPIRED: HIGH
  NAME_MISMATCH: MEDIUM
  TAMPER_INDICATOR: HIGH
  DUPLICATE_ACROSS_INSTITUTIONS: HIGH
  HTR_LOW_CONFIDENCE: LOW
  VERIFICATION_SOURCE_UNAVAILABLE: MEDIUM

risk_weights: {HIGH: 25, MEDIUM: 10, LOW: 3, INFO: 0}
alerts:
  - type: PENDING_VERIFICATION
    when: "verification.status == 'PENDING' and age_hours > 24"
    notify: [SCRUTINY_OFFICER]
  - type: SLA_BREACH
    when: "application.age_days > 10 and open_high_flags > 0"
    notify: [SENIOR_OFFICER]
thresholds:
  ocr_min_conf: 0.80
  htr_min_conf: 0.70
  ela_suspicion: 0.65
  duplicate_phash_hamming: 6
  duplicate_embed_cos: 0.95
```
The rule evaluator is a small, safe json-logic interpreter (no `eval`). Entity-match and count rules are typed rule kinds implemented in Python.

## 11. API surface (abridged)

**Host API (`/api/v1`, API-key auth):**
```
POST   /applications                     {external_ref, institution_ref, category, form_fields}
POST   /applications/{id}/upload-session → {token, expires_at}   # for the browser widget
POST   /applications/{id}/documents      multipart (slot, file)  # server-side upload alternative
POST   /applications/{id}/submit         → 202 {job_id}
GET    /applications/{id}/status
GET    /applications/{id}/report?view=institution|full
GET    /applications/{id}/deficiencies
POST   /hosts/me/webhooks/test
```
**Widget API (`/widget/v1`, upload-session token):**
```
GET    /session                          → slots, labels, accepted types (from mapping + rule pack)
POST   /documents                        multipart → quick checks result (type, quality, fields seen)
GET    /deficiencies
```
**Console API (`/console/v1`, user JWT + RBAC):**
```
GET  /queue  GET /applications/{id}  GET /documents/{id}/pages/{n}  GET /flags/{id}
POST /flags/{id}/disposition  POST /applications/{id}/observations
POST /applications/{id}/decision-note   # gated by FR-HIL-03
GET  /dashboard/summary  GET /alerts  POST /alerts/{id}/ack
GET  /audit?filters  GET /audit/verify
GET/POST/PUT /admin/rule-packs  POST /admin/rule-packs/{id}/dry-run
GET/POST /admin/hosts  /admin/api-keys  /admin/slot-mappings
GET  /eval/runs  POST /eval/runs
GET  /applications/{id}/timeline        # stage_runs + agent_traces
```
**Webhook payload:**
```json
{"event":"validation.completed","application_id":"…","external_ref":"…",
 "status":"ready","risk_score":62,"deficiency_count":5,"report_url":"…","ts":"…"}
```
Header: `X-Pramaan-Signature: t=<ts>,v1=<hmac_sha256(secret, ts.body)>`

## 12. Mock issuer design
- Issuers: `FIRE_DEPT_MP`, `MUNICIPAL_INDORE`, `ACCREDITATION_BOARD_DEMO`, `REGISTRAR_SOCIETIES_DEMO`, `NOTARY_DEMO`. All names are fictional demo issuers.
- Each issuer has an Ed25519 keypair. QR payload = base64url(JSON fields) + "." + signature. Public keys are served at `/issuers/{id}/keys`.
- A demo root CA (created with `cryptography`) issues per-issuer signing certificates. Synthetic PDFs are signed with pyHanko. PRAMAAN trusts only the demo root.
- `GET /issuers/{id}/documents/{ref}` returns the canonical record or 404.
- Admin toggles: `latency_ms`, `down`, `force_mismatch`.

## 13. Risk score
`risk = min(100, Σ weight(severity) over open flags)`. It is used **only** for queue ordering, and is shown with the label "Review priority, not a decision".

## 14. Deployment (prototype)
- `make up`: Docker Compose (postgres, redis, minio, clamav, mailpit, caddy, api, workers, mocks, console, hosts).
- `make up-gpu`: adds the GPU override for `worker-gpu` (NVIDIA container toolkit on WSL2).
- Ollama runs natively on the host. Containers reach it through `host.docker.internal:11434`.
- `make seed`: generates synthetic data, loads mock records, registers hosts and keys.
- `make demo`: submits the golden and problem applications to both hosts.
- `make eval`: runs the evaluation harness and stores the results.
- `MODE=LITE make up`: CPU-only profile.
