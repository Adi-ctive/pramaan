# 01 — Software Requirements Specification (SRS)

**Project:** PRAMAAN — Pluggable Regulatory Application & Document Verification Engine
**Problem Statement:** SIH26261 — AI-Powered Application Validation, Document Authentication and Regulatory Compliance Verification (AICTE, Regulation Bureau, Smart Automation)
**Document type:** SRS for a hackathon **prototype**. Everything must run free, locally, on synthetic data.
**Version:** 1.0

---

## 1. Introduction

### 1.1 Purpose
This SRS defines what PRAMAAN must do. It is the source of truth for the build. Every functional requirement (FR) is traced back to the wording of SIH26261 (section 9, Traceability Matrix).

### 1.2 Problem summary
Institutions applying to AICTE for Extension of Approval (EoA) and other approval-related changes upload many supporting documents. Today these are checked manually. The resulting problems are:
- missing, incomplete, expired or inconsistent documents;
- suspected alterations;
- difficulty confirming documents with the original issuing authorities.

Together these cause delays and repeated manual effort.

### 1.3 Product summary
PRAMAAN is a **headless validation engine with an officer console**, designed to plug into any document-upload workflow. The primary target is the AICTE approval portal; any other portal can be added through an adapter. When a host portal submits an application, PRAMAAN:
1. identifies the application category and loads the applicable checklist;
2. pulls the institution's existing records;
3. reads every document (printed OCR, handwriting, stamps, signatures, fields);
4. checks completeness, validity, consistency, tampering, duplication and plausibility;
5. verifies documents against their issuing source where a mechanism exists;
6. checks infrastructure evidence (photos, videos, floor plans) with computer vision;
7. produces an evidence-linked validation report, alerts, a risk score and an audit trail.

**PRAMAAN never approves or rejects.** It is decision support. Final decisions stay with human officials.

### 1.4 Scope
**In scope (prototype):**
- the validation engine;
- an embeddable upload widget;
- two mock host portals, used to prove the engine is pluggable;
- the officer console;
- the admin rules editor;
- mock AICTE records;
- mock issuer verification services;
- a synthetic data generator;
- an evaluation harness.

**Out of scope:**
- real AICTE, DigiLocker, NBA/NAAC or municipal integrations (mocked behind adapters);
- production scale;
- legal admissibility of findings;
- signature *identity* proof (similarity is advisory only).

### 1.5 Definitions
| Term | Meaning |
|---|---|
| Host portal | Any system that accepts document uploads and calls PRAMAAN (for example, the AICTE portal) |
| Application | One submission by an institution: its form fields plus its document set |
| Document slot | A named required document in a checklist (for example, `FIRE_NOC`) |
| Rule pack | A versioned, configurable set of checklists and rules (for example, `aicte-aph-2026-27`) |
| Flag | One finding: a rule violation, anomaly or verification outcome, with evidence |
| Issuer | The authority that issued a document (fire department, municipal body, accreditation body, and so on) |
| Verification status | One of `VERIFIED`, `MISMATCH`, `EXPIRED`, `PENDING`, `SOURCE_UNAVAILABLE`, `MANUAL_REVIEW` |
| Risk score | 0–100 aggregate used only to order the review queue. Never used as a decision |
| HTR | Handwritten text recognition |
| VLM | Vision-language model |
| EoA | Extension of Approval |
| APH | AICTE Approval Process Handbook |
| TER | Fee payment record referenced in the PS |

### 1.6 Model naming convention
All third-party models are referenced in code and UI by **role**, not brand. Examples: "OCR Model", "Handwriting Model", "Document Classifier", "Object Detector", "Tamper Localiser", "Reasoning LLM", "Vision-Language Model". Concrete open-source implementations sit behind provider interfaces so they can be swapped for commercial ones later.

---

## 2. Overall description

### 2.1 Users and roles
| Role | Who | Main goals |
|---|---|---|
| `INSTITUTION` | College applicant, acting through the host portal or widget | Upload documents, see deficiencies instantly, fix and re-upload |
| `SCRUTINY_OFFICER` | AICTE regional or bureau official | Review the queue, inspect flags with evidence, confirm or override them, record observations |
| `SENIOR_OFFICER` | Approving authority | See escalations, the summary dashboard and audit history. Final decision recorded outside PRAMAAN; only noted here |
| `RULE_ADMIN` | Policy and IT cell | Edit checklists, rules, thresholds and rule-pack versions |
| `INTEGRATION_ADMIN` | IT cell | Register host portals, API keys, webhooks and slot mappings |
| `AUDITOR` | Vigilance or internal audit | Read-only access to the audit trail and reports |
| `SYSTEM` | Host portal machine identity | Calls APIs with an API key |

### 2.2 Operating environment (prototype)
- **Main dev machine:** Windows 11, 32 GB RAM, RTX 5060 Ti (Blackwell) and/or RTX 2000 Ada. Docker Desktop with WSL2. Ollama installed on the host.
- **Must also run in `LITE` mode on CPU only.** No vision-language model and no large detectors. Degraded but working, for teammates' laptops.
- Browsers: latest Chrome and Edge.

### 2.3 Constraints
- C1: Zero cost. Open-source, self-hosted, no paid APIs.
- C2: Authorised, anonymised or synthetic data (as the PS allows). Real documents and photos from our own college are allowed with permission. They live only in the gitignored local folder realdata/, are never committed, published or sent to any external service, and personal IDs and phone numbers are masked. Synthetic data remains for forgery tests and large-scale metrics. Mock portals must not use AICTE or other government logos or branding. (Amended 24 Oct 2026; see DECISIONS.md #24.)
- C3: No access to restricted government databases. All external sources go through mock adapters.
- C4: AI outputs are advisory. An adverse action requires a recorded human review (enforced in code).
- C5: All rules are configurable. No regulatory threshold may be hard-coded in Python.
- C6: Document content is untrusted input. It must never be able to instruct the system (prompt-injection safe).

### 2.4 Assumptions
- A1: Host portals can send an HTTP request with document files or URLs, plus form fields.
- A2: Synthetic issuers sign QR payloads and PDFs with keys that PRAMAAN trusts. This simulates real e-sign and QR verification.
- A3: Infrastructure photos for the demo are either team-captured photos of their own college labs and classrooms, or openly licensed images.

---

## 3. Functional requirements

Priority: **M** = must have for the demo, **S** = should have, **C** = could have (stretch goal).

### 3.1 Integration and intake (plug-in layer)
| ID | Requirement | Pri |
|---|---|---|
| FR-INT-01 | Expose a versioned REST API (`/api/v1`) to create an application, attach documents, trigger validation and fetch the report | M |
| FR-INT-02 | Authenticate host portals with per-host API keys (hashed at rest) | M |
| FR-INT-03 | Send signed (HMAC-SHA256) webhooks to the host on `validation.completed`, `validation.updated` and `alert.raised` | M |
| FR-INT-04 | Per-host **slot mapping**: map the host's field and document names to PRAMAAN's canonical slots and fields | M |
| FR-INT-05 | Provide an embeddable JS widget (`<script>` plus one `<div>`) that renders upload slots and live per-slot feedback for any host page | M |
| FR-INT-06 | Two mock host portals (Host A: "Approval Portal (mock)"; Host B: "University Affiliation Portal (mock)") that use the same engine with different rule packs, demonstrating pluggability | M |
| FR-INT-07 | Idempotent submissions (an `Idempotency-Key` header) | S |
| FR-INT-08 | OpenAPI documentation auto-generated and browsable | M |

### 3.2 Application category and checklist
| ID | Requirement | Pri |
|---|---|---|
| FR-CHK-01 | Determine the application category (for example `EOA`, `INTAKE_INCREASE`, `NEW_COURSE`, `CHANGE_OF_SITE`, `CHANGE_OF_NAME`) from host-provided fields, with a fallback inference | M |
| FR-CHK-02 | Load the applicable checklist (required slots, required fields, conditions) from the active rule pack | M |
| FR-CHK-03 | Report missing slots, missing required fields and incomplete submissions | M |
| FR-CHK-04 | Detect a wrong document in a slot (classifier label ≠ slot's expected type) | M |
| FR-CHK-05 | Detect expired documents using extracted validity dates and the rule-pack expiry rules | M |

### 3.3 Institutional record reuse
| ID | Requirement | Pri |
|---|---|---|
| FR-REC-01 | Fetch existing institution records through a Records Adapter: past EoA and approval status, approved programmes and intake, faculty records, accreditation, NOCs and permissions, affidavits and undertakings, deficiency and compliance status, TER payment status, application history | M |
| FR-REC-02 | Reuse previously verified documents: if an identical, still-valid document was verified earlier (same hash, or same issuer and reference), mark it `VERIFIED (carried forward)` with a link to the earlier verification | S |
| FR-REC-03 | The Records Adapter is pluggable. The prototype ships a mock Postgres-backed implementation | M |

### 3.4 Document understanding
| ID | Requirement | Pri |
|---|---|---|
| FR-DOC-01 | Accept PDF (digital and scanned), JPG, PNG, TIFF, MP4 and MOV. Enforce size and type limits | M |
| FR-DOC-02 | Detect whether a PDF has a usable text layer. If so, use the native text and skip OCR | M |
| FR-DOC-03 | Pre-process scans: deskew, denoise, perspective correction, page split, orientation fix | M |
| FR-DOC-04 | Classify each document into a type from the rule pack's document taxonomy, with a confidence score | M |
| FR-DOC-05 | Printed OCR, including English and Hindi, with word-level bounding boxes and confidence | M |
| FR-DOC-06 | Table structure extraction for tabular documents (fee receipts, faculty lists) | S |
| FR-DOC-07 | Detect handwritten regions and run HTR on them. Below the confidence threshold, emit a `MANUAL_REVIEW` flag | M |
| FR-DOC-08 | Detect stamps, seals and signatures (presence and location). Check the required ones per the rule pack | M |
| FR-DOC-09 | Signature similarity against a reference signature on file. Advisory score only | C |
| FR-DOC-10 | Key field extraction using a per-type schema (institution or society name, address, survey or plot number, issue date, expiry date, reference number, issuer, amount, intake, and so on), each with value, bounding box, confidence and method | M |
| FR-DOC-11 | Normalise fields: dates to ISO, names transliteration-normalised, numbers parsed, Indian number formats handled | M |
| FR-DOC-12 | Video evidence: sample frames, dedupe them, and feed them to infrastructure checks | S |

### 3.5 Consistency validation
| ID | Requirement | Pri |
|---|---|---|
| FR-CON-01 | Intra-document checks (for example, expiry date after issue date; totals add up) | M |
| FR-CON-02 | Cross-document checks (for example, the lessee on the lease deed matches the society name in the society registration, the NOC addressee and the application form) | M |
| FR-CON-03 | Application vs records checks (for example, claimed current intake equals approved intake; faculty count is consistent with the records) | M |
| FR-CON-04 | Entity resolution for names and addresses: fuzzy, abbreviation-aware, transliteration-aware and embedding-based, with a configurable match threshold | M |
| FR-CON-05 | Every inconsistency flag shows both values, both sources (document and box, or record and field) and the rule ID | M |

### 3.6 Anomaly and tamper detection
| ID | Requirement | Pri |
|---|---|---|
| FR-ANO-01 | Image forensics: error level analysis, noise-residual inconsistency, copy-move detection. Output a heatmap and suspicious regions | M |
| FR-ANO-02 | PDF forensics: incremental-update history, objects modified after creation, mixed fonts inside one field, producer and creator metadata, creation vs modification date gap, a signature invalidated by later edits | M |
| FR-ANO-03 | Text-level forensics: font-size, baseline or character-spacing outliers within a field region | S |
| FR-ANO-04 | Duplicate detection across all submissions (any institution, any year): perceptual hash plus embedding similarity, for documents and photos | M |
| FR-ANO-05 | Date and identifier plausibility rules (for example, a document issued before the institution's establishment date, validity longer than the issuer's maximum, a reference number not matching the issuer's format, an issue date on a gazetted holiday) | M |
| FR-ANO-06 | Statistical outlier detection on numeric fields vs similar institutions | C |
| FR-ANO-07 | Anomaly flags are always worded as "indicator, needs verification", never as "forged" | M |

### 3.7 Source verification
| ID | Requirement | Pri |
|---|---|---|
| FR-VER-01 | QR verification: decode the QR, verify the payload's issuer signature (Ed25519), compare payload fields with the printed and extracted fields | M |
| FR-VER-02 | PDF digital-signature validation: certificate chain against the trusted issuer CA, integrity (not modified after signing), signer identity | M |
| FR-VER-03 | Reference-number lookup through per-issuer Verification Adapters (mock issuer service) | M |
| FR-VER-04 | Each verification records the source, method, timestamp, request digest, response digest and outcome | M |
| FR-VER-05 | Status set: `VERIFIED`, `MISMATCH`, `EXPIRED`, `PENDING`, `SOURCE_UNAVAILABLE`, `MANUAL_REVIEW`. Unavailable or inconclusive results route to manual confirmation | M |
| FR-VER-06 | The mock issuer service can simulate latency, downtime and mismatches for the demo | S |

### 3.8 Regulatory and infrastructure compliance
| ID | Requirement | Pri |
|---|---|---|
| FR-INF-01 | Rule-pack-driven compliance checks on application data (for example, intake vs approved; faculty-to-student ratio vs the norm) | M |
| FR-INF-02 | Room-type classification of infrastructure photos (classroom, computer lab, workshop, library, seminar hall, washroom, other) | M |
| FR-INF-03 | Open-vocabulary object counting (computers, monitors, benches, projectors, bookshelves, fire extinguishers) vs the claimed counts and norms | M |
| FR-INF-04 | Photo metadata checks: EXIF GPS distance from the registered campus location; capture date inside the allowed window; missing metadata flagged softly | M |
| FR-INF-05 | Reuse detection: the same room or photo presented as different facilities, within or across institutions (via FR-ANO-04) | M |
| FR-INF-06 | Floor-plan analysis: read the scale, segment rooms, estimate area, compare with area norms | C |
| FR-INF-07 | Infrastructure flags are advisory and recommend "additional evidence" or "physical inspection" | M |

### 3.9 Reporting, dashboard and alerts
| ID | Requirement | Pri |
|---|---|---|
| FR-REP-01 | Structured validation report per application (JSON plus rendered HTML and PDF) | M |
| FR-REP-02 | Report sections: summary, checklist status, per-document results, verification table, consistency findings, anomaly findings, infrastructure findings, cases requiring intervention | M |
| FR-REP-03 | Every flag is evidence-linked (see the flag schema in 02_ARCHITECTURE.md) | M |
| FR-REP-04 | Plain-language summary written by the Reasoning LLM, grounded only in flags, citing flag IDs. No new claims allowed | S |
| FR-REP-05 | Institution-facing deficiency list (rectification view) without internal forensic details | M |
| FR-REP-06 | Rectification loop: on re-upload, re-run only the affected checks and keep version history | M |
| FR-DSH-01 | Officer queue sorted by risk score, with filters (region, category, status, flag type, age) | M |
| FR-DSH-02 | Application detail view with document viewer, overlays and flag panel | M |
| FR-DSH-03 | Summary dashboard: counts by status, top deficiency types, pending verifications, ageing, average processing time | M |
| FR-ALR-01 | Alerts for missing information, expired documents, pending source verification, suspected anomalies, unresolved items past SLA | M |
| FR-ALR-02 | Alerts delivered in-app, plus email via a local mail catcher (Mailpit), plus a webhook to the host | M |
| FR-ALR-03 | Alert rules configurable in the rule pack (thresholds, SLA days, recipients by role) | S |

### 3.10 Human review
| ID | Requirement | Pri |
|---|---|---|
| FR-HIL-01 | Officers can confirm, dismiss or escalate each flag, with a mandatory reason when dismissing or escalating | M |
| FR-HIL-02 | Officers add free-text observations per application | M |
| FR-HIL-03 | The system blocks marking an application "Deficiency confirmed – adverse" until all high-severity flags have a human disposition | M |
| FR-HIL-04 | Override statistics are stored for threshold tuning (feedback dataset export) | S |

### 3.11 Rules administration
| ID | Requirement | Pri |
|---|---|---|
| FR-RUL-01 | Rule packs are YAML, versioned, with effective dates and a reference to their source clause (for example, "APH 2026-27 §x.y" as a placeholder citation) | M |
| FR-RUL-02 | A web rules editor with schema validation, diff view and "dry run on sample application" | S |
| FR-RUL-03 | Every report records the rule-pack version used, so results are reproducible | M |

### 3.12 Audit trail
| ID | Requirement | Pri |
|---|---|---|
| FR-AUD-01 | Log every rule applied, record checked, source request and response, flag, alert, human action and observation | M |
| FR-AUD-02 | Append-only, hash-chained log (each entry stores the hash of the previous one). A verification endpoint proves the chain is intact | M |
| FR-AUD-03 | Audit viewer with filter and export | M |

### 3.13 Agentic orchestration
| ID | Requirement | Pri |
|---|---|---|
| FR-AGT-01 | A multi-agent orchestration layer plans and executes validation per application (see 02_ARCHITECTURE.md §6) | M |
| FR-AGT-02 | Agents act only through typed, read-only tools. They cannot change records, rules or decisions | M |
| FR-AGT-03 | Deterministic checks (rules, hashes, signatures, audit) are tools, not LLM judgements | M |
| FR-AGT-04 | Agent reasoning traces are stored and viewable per application ("why was this checked") | S |
| FR-AGT-05 | Graceful degradation: if the LLM is unavailable (LITE mode), a deterministic pipeline runs the same tools in a fixed order | M |

### 3.14 Synthetic data and evaluation
| ID | Requirement | Pri |
|---|---|---|
| FR-SYN-01 | Generator for synthetic institutions, records, applications and documents (every slot type), rendered as PDF and as scan-like images | M |
| FR-SYN-02 | Realistic scan degradation (blur, noise, skew, folds, stains, low DPI) | M |
| FR-SYN-03 | Forgery generator with ground truth: edited dates, swapped names, pasted stamps, altered amounts, cloned regions, re-saved PDFs with incremental edits, broken signatures, mismatched QR codes, reused photos | M |
| FR-SYN-04 | Handwritten fields rendered with handwriting fonts (English and Hindi), with ground truth | S |
| FR-SYN-05 | Evaluation harness computing the PS metrics: extraction accuracy (field-level exact match and character error rate), validation accuracy, anomaly detection precision, recall and F1, source-verification success rate, discrepancy identification reliability, average processing time, alert timeliness, estimated manual effort saved | M |
| FR-SYN-06 | An evaluation results page in the console, with charts | M |

---

## 4. Non-functional requirements
| ID | Category | Requirement (prototype target) |
|---|---|---|
| NFR-01 | Performance | A 20-document application is fully validated in ≤ 90 s in GPU mode and ≤ 5 min in LITE mode |
| NFR-02 | Performance | Instant widget feedback (type, quality, missing fields) per uploaded file in ≤ 10 s in GPU mode |
| NFR-03 | Scalability | Stateless API plus a worker queue. Workers scale horizontally (demonstrate 2 workers) |
| NFR-04 | Availability | A failure in one check never fails the whole report. It yields `MANUAL_REVIEW` with the error noted |
| NFR-05 | Explainability | 100 % of flags carry a rule ID or detector name, evidence and a human-readable reason |
| NFR-06 | Reproducibility | Same inputs plus the same rule pack and model versions produce the same deterministic results. Model versions are recorded |
| NFR-07 | Security | See 05_SECURITY.md. RBAC, encryption at rest for documents and PII fields, TLS, access logging, retention |
| NFR-08 | Privacy | PII masked in views by role. Institution view excludes forensic internals |
| NFR-09 | Portability | `docker compose up` brings up all infrastructure. ML runs in Docker with the GPU or natively. Works on Windows (WSL2) and Linux |
| NFR-10 | Modularity | Every model sits behind a provider interface. Every external system sits behind an adapter. Swapping one is a config change |
| NFR-11 | Usability | An officer can understand any flag in ≤ 10 s from the detail view. Keyboard navigation through flags |
| NFR-12 | Localisation | UI strings externalised. English is complete; Hindi labels for the institution widget |
| NFR-13 | Accessibility | WCAG 2.1 AA contrast. All overlays also listed as text |
| NFR-14 | Testability | Unit tests for rules, adapters and forensics. Integration test for the end-to-end golden application. ≥ 70 % coverage on `core/` |

---

## 5. External interfaces
- **Host portal → PRAMAAN:** REST plus the JS widget (FR-INT-*)
- **PRAMAAN → host portal:** signed webhooks
- **PRAMAAN → Records Adapter:** internal interface (mock implementation backed by Postgres)
- **PRAMAAN → Verification Adapters:** HTTP to the mock issuer service
- **PRAMAAN → model runtimes:** in-process Python (OCR, detectors, forensics) plus Ollama HTTP (VLM and LLM)
- **Email:** SMTP to Mailpit

## 6. Data requirements
- Documents are stored in object storage (MinIO), encrypted, and content-addressed by SHA-256.
- Relational data lives in PostgreSQL. Embeddings are stored in pgvector.
- Retention: per document-type TTL in the rule pack. A purge job deletes expired raw files but keeps the hash and the audit trail.

## 7. Acceptance criteria (demo)
1. The same engine plugs into **two different mock portals** with different rule packs, live.
2. A clean "golden" application passes with all checks green and all documents verified.
3. A seeded "problem" application surfaces: a missing slot, an expired NOC, a name mismatch across documents, an intake mismatch vs records, a tampered date (with heatmap), a reused lab photo from another institution, a QR mismatch, low-confidence handwriting routed to manual review, and a lab with fewer computers than claimed.
4. The institution sees only the rectification list. It re-uploads, and only the affected checks re-run.
5. An officer dismisses one flag with a reason. The adverse-decision gate blocks until all high-severity flags are disposed.
6. The audit chain verifies as intact. Tampering with one database row makes verification fail.
7. The evaluation page shows every PS metric on the synthetic test set.
8. The system runs in LITE mode on a CPU-only laptop.

## 8. Risks
| Risk | Mitigation |
|---|---|
| GPU and framework incompatibility (Blackwell RTX 50-series needs CUDA 12.8+ builds) | Provider interfaces with fallbacks (PyTorch-based OCR fallback); pin versions; RTX 2000 Ada as backup GPU |
| Weak Indic handwriting accuracy | Confidence gating to `MANUAL_REVIEW`; present honestly |
| Floor-plan analysis immature | Marked stretch goal (C) |
| LLM hallucination in summaries | Summaries may only cite existing flag IDs; validator rejects unknown IDs; deterministic template fallback |
| Prompt injection via document text | Document text passed as quoted data; tools read-only; structured outputs; see 05_SECURITY.md |
| Demo-day instability | Pre-computed reports cache plus a recorded backup video |

---

## 9. Traceability matrix (PS clause → requirements)
| SIH26261 clause | Requirements |
|---|---|
| Identify application category, determine applicable checklist | FR-CHK-01, FR-CHK-02 |
| Retrieve records: affidavits/undertakings, accreditation, NOCs/permissions, previous EoA and approval status, approved programmes/courses/intake, faculty and institution records, compliance/deficiency status, TER payment status, application history | FR-REC-01, FR-REC-03 |
| Reduce repeated manual checking using records already available | FR-REC-02 |
| OCR, document classification, intelligent data extraction | FR-DOC-02…FR-DOC-11 |
| Missing fields, incomplete submissions, expired documents, inconsistencies within or across records | FR-CHK-03…05, FR-CON-01…05 |
| Structured validation report; allow rectification where permitted | FR-REP-01, FR-REP-05, FR-REP-06 |
| Suspicious alterations, duplicated documents, inconsistent metadata, mismatched identifiers, irregular dates | FR-ANO-01…05 |
| Each flag identifies the evidence and the reason; preliminary indicators only | FR-REP-03, FR-ANO-07, NFR-05 |
| Verify through APIs, portals, digitally signed records, QR codes, unique reference numbers | FR-VER-01…03 |
| Record source, timestamp and result; statuses verified/mismatch/expired/pending/source unavailable/manual review; route inconclusive cases to manual | FR-VER-04, FR-VER-05 |
| Configurable checklists from APH, regulations, authorised instructions | FR-RUL-01…03, C5 |
| Photographs, videos, floor plans, certificates; CV to flag discrepancies; advisory | FR-INF-01…07, FR-DOC-12 |
| Dashboard: validation status, deficiencies, verification results, unresolved discrepancies, cases requiring intervention | FR-DSH-01…03 |
| Alerts: missing info, expired docs, pending source verification, suspected anomalies, unresolved items | FR-ALR-01…03 |
| Audit trail of rules, records, source responses, alerts, observations, actions | FR-AUD-01…03 |
| Role-based access, secure handling, confidentiality, access logging, data retention | NFR-07, NFR-08, 05_SECURITY.md |
| Must not bypass access controls or assume restricted database access | C3, adapters, SOURCE_UNAVAILABLE status |
| Explainable, evidence-supported AI flags | NFR-05, FR-REP-03 |
| Human review before adverse action; AI is decision support only | FR-HIL-01…03, C4 |
| Prototype with authorised/anonymised/synthetic data | FR-SYN-01…04, C2 |
| Evaluation metrics (extraction accuracy … manual effort reduction) | FR-SYN-05, FR-SYN-06 |
| EoA **and other approval-related changes** | FR-CHK-01 categories |
| Integrated with, or designed for integration with, the AICTE portal | FR-INT-01…08 |
