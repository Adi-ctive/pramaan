# 03 — UI Design Plan

## 1. Surfaces
| Surface | Users | Purpose |
|---|---|---|
| **Officer Console** (React SPA) | Scrutiny officer, senior officer, rule admin, integration admin, auditor | Review, evidence, dispositions, dashboards, rules, integrations, audit, evaluation |
| **Embeddable Widget** | Institution (inside any host page) | Upload slots, instant per-file feedback, deficiency list, re-upload |
| **Mock Host A — "Approval Portal (mock)"** | Demo | A simple multi-step application form that embeds the widget |
| **Mock Host B — "University Affiliation Portal (mock)"** | Demo | A visually different portal with the same widget, a different rule pack and different slot names |

> Mock hosts must look like **generic demo portals**. Do not use AICTE or any real government logo, emblem or branding. Label them "(mock)".

## 2. Design language
- **Tone:** calm, institutional, high-trust, information-dense but legible. Evidence first, decoration last.
- **Type:** Inter (UI), JetBrains Mono (IDs, hashes, reference numbers), Noto Sans Devanagari (Hindi).
- **Colour tokens** (CSS variables, with light and dark themes):
  - `--bg`, `--surface`, `--surface-2`, `--border`, `--text`, `--text-muted`
  - `--primary` deep indigo `#2B3A8C` (light) / `#8A9BFF` (dark)
  - Status: `--ok` green, `--warn` amber, `--risk` red, `--info` slate-blue, `--manual` violet (for `MANUAL_REVIEW`)
  - Severity chips: HIGH = red, MEDIUM = amber, LOW = slate, INFO = grey
- **Rule:** status is never shown by colour alone. Always pair an icon and a text label.
- **Components:** shadcn/ui (Radix based) with Tailwind; lucide icons; TanStack Table; ECharts for charts; PDF and image viewer built on pdf.js plus a canvas overlay layer.
- **Density toggle:** comfortable / compact (officers prefer compact).
- **Keyboard:** `J`/`K` next/previous flag, `C` confirm, `D` dismiss (opens reason), `E` escalate, `/` search, `G Q` go to queue.

## 3. Officer Console — information architecture
```
Left nav
├─ Queue                (default)
├─ Dashboard
├─ Alerts               (badge count)
├─ Applications search
├─ Evaluation
├─ Admin ▸ Rule packs | Hosts & keys | Slot mappings | Users
└─ Audit
Top bar: global search (institution / AICTE ID / application / flag ID), mode badge (FULL/LITE), user menu
```

## 4. Screen specs

### 4.1 Login
Email and password, plus an optional TOTP step. The demo users are listed on the login page **only when `DEMO=true`**.

### 4.2 Queue
- A table sorted by review priority. Columns: priority bar (risk 0–100), institution, category, host, submitted, age / SLA chip, open HIGH/MED/LOW counts, verification progress (e.g. "14/18 verified"), status.
- Filters: region, category, host, status, flag code, "needs my action", SLA breached.
- Row click opens the Application Detail.
- Header strip: "Review priority is a sorting aid, not a decision."

### 4.3 Application Detail (the core screen)
Three-pane layout:
```
┌───────────────┬───────────────────────────────────┬────────────────────────┐
│ LEFT: Outline │ CENTER: Evidence Viewer           │ RIGHT: Findings        │
│               │                                   │                        │
│ Summary card  │ Document page (pdf.js/canvas)     │ Tabs: Flags | Verify   │
│ - risk, cat,  │ Overlays toggle:                  │       | Checklist      │
│   rule pack   │  [Fields][Handwriting][Stamps]    │       | Records diff    │
│ Checklist     │  [Signatures][Tamper heatmap]     │       | Timeline       │
│  ✓ slots      │  [QR][Duplicates]                 │                        │
│  ✗ missing    │ Zoom, page thumbnails, rotate     │ Flag card:             │
│ Documents     │ Side-by-side compare mode         │  severity chip, title, │
│  grouped by   │ (doc vs doc, doc vs record,       │  reason, expected vs   │
│  slot, with   │  photo vs duplicate)              │  observed, evidence    │
│  status icons │                                   │  links (jump to bbox), │
│ Infra gallery │                                   │  detector + version,   │
│               │                                   │  confidence, advisory  │
│               │                                   │  note, actions:        │
│               │                                   │  Confirm/Dismiss/Escal │
└───────────────┴───────────────────────────────────┴────────────────────────┘
Bottom bar: Observations box · "Record decision note" (disabled until all HIGH flags disposed, with tooltip listing which)
```
- Clicking an evidence item scrolls the viewer to the page and pulses the bounding box.
- **Records diff tab:** a table of the application's claims vs AICTE records vs extracted document values, with mismatches highlighted.
- **Verify tab:** a per-document verification table with method, source, status chip, timestamp, response digest, and a "Re-verify" button (re-queues).
- **Timeline tab:** stage runs as a Gantt-like strip, plus agent steps ("Forensics Agent escalated: ELA 0.71 > 0.65 → ran copy-move").
- **Case summary card** at the top of the Findings pane. Each sentence carries `[FLG-xxxx]` chips that link to flags. Footer: "Generated from flags; no independent claims."

### 4.4 Document Viewer — overlay specifics
- Fields: thin primary-colour boxes; hover shows key, value and confidence.
- Handwriting: dashed violet box, with HTR text and a confidence bar.
- Stamps, seals and signatures: labelled chips at their positions.
- Tamper heatmap: semi-transparent jet colour map at an adjustable opacity, with suspicious regions outlined in red.
- QR: box plus decoded payload table, with a match or mismatch per field.
- Duplicates: a banner reading "Visually matches 1 document from another institution (similarity 0.97)" that opens the compare view.

### 4.5 Infrastructure Gallery
Cards per claimed facility (Computer Lab 1, Classroom 3, …). Each card shows:
- photo thumbnails;
- predicted room type and confidence;
- detected object count vs claimed count ("Monitors: 12 detected / 30 claimed");
- EXIF distance from campus and capture date;
- a reuse warning;
- a recommendation chip ("Additional evidence" / "Physical inspection").

Click a card to see detections drawn on the photo.

### 4.6 Dashboard
KPI cards: applications in queue, ready for review, SLA breaches, pending verifications, average processing time, flags per application.

Charts:
- flags by category (bar);
- top deficiency codes (bar);
- verification outcomes (stacked bar);
- ageing distribution (histogram);
- region-wise counts (bar);
- processing time trend (line).

### 4.7 Alerts
A list with type, severity, application, due time and channel. Actions: acknowledge, jump to application.

### 4.8 Rule Packs (admin)
- List of packs with version and status.
- Editor: Monaco YAML with schema validation and inline errors.
- Diff vs the active version.
- **Dry run**: choose a sample application, show the flags that would change.
- Activate a version with confirmation; it creates an audit entry.

### 4.9 Hosts and Keys (admin)
- Host list, with create host, rotate key (shown once), webhook URL and secret, a "send test webhook" action, and a delivery log.
- **Slot Mappings:** a two-column mapper (host slot/field ↔ canonical slot/field) with a preview of the widget as that host would render it.

### 4.10 Audit
- Filterable log (actor, action, object, time).
- "Verify chain" button showing a result banner with the last verified sequence number.
- Export as CSV or JSON.

### 4.11 Evaluation
- Run list.
- Selected run shows a metrics grid matching the PS list: extraction accuracy (field exact match, CER), validation accuracy, anomaly detection P/R/F1 per forgery type, source-verification success rate, discrepancy identification reliability, average processing time per application and per document, alert timeliness, and estimated manual effort saved (formula shown).
- A confusion matrix for tamper detection, a per-document-type extraction table, and download of the report.

## 5. Embeddable Widget

### 5.1 Embed contract
```html
<div id="pramaan-uploader"></div>
<script src="https://<pramaan>/widget/v1/pramaan.js"
        data-session="<upload-session-token>"
        data-lang="en" data-theme="auto"></script>
```
- Built as a framework-free TypeScript bundle in a Shadow DOM, so host CSS can't break it and it can't break the host.
- Communicates with the host page via `CustomEvent`s: `pramaan:file-checked`, `pramaan:ready-to-submit`, `pramaan:deficiencies`.
- Themes itself from CSS custom properties that the host may override (`--pramaan-primary`, and so on).

### 5.2 Widget UI
- A slot list, generated from the session (slot label in host wording, accepted types, required/optional).
- Per slot, a drop zone, then a quick check with a spinner, then a result row:
  - ✓ "Looks like a Fire Safety NOC · valid until 31 Mar 2026 · ⚠ expired"
  - ✗ "This looks like a Building Completion Certificate, not a Fire NOC"
  - ⚠ "Image is blurry — please upload a clearer scan"
- A deficiency panel after submission: only institution-visible flags, in plain language, each with the action needed and a re-upload button. Forensic internals are **never** shown to institutions ("needs verification by authority" at most).
- Hindi toggle for labels.

## 6. Mock host portals
- **Host A, "Approval Portal (mock)":** sober blue header, a 3-step form (Institution details → Application details → Documents [widget]) and a status page that shows the webhook-driven status.
- **Host B, "University Affiliation Portal (mock)":** maroon theme, single page, different slot names ("Fire Clearance Certificate" instead of "Fire NOC"). This shows that slot mapping works.
- Both have a small "Powered by PRAMAAN validation engine" footer and a "Switch host" link for the live demo.

## 7. Demo script mapping (what each screen proves)
1. Host A: upload a golden application → all green → the console shows it ready, low priority.
2. Host A: upload a problem application → widget instant warnings → the console shows HIGH-priority flags, heatmap, QR mismatch, duplicate photo across institutions, lab count shortfall.
3. Institution view: only the rectification list → re-upload the Fire NOC → only the affected checks re-run (timeline shows it).
4. Officer: dismiss one flag with a reason → the decision gate unlocks only after the HIGH flags are disposed.
5. Host B: the same engine, a different portal, a different rule pack → it works unchanged (pluggability).
6. Audit: verify the chain → OK; tamper one row via the admin SQL demo script → chain broken at seq N.
7. Evaluation page: metrics on the synthetic set.
8. Toggle LITE mode on a laptop → still produces a report.

## 8. Accessibility and quality bar
- WCAG AA contrast. Focus rings. All overlays mirrored as an accessible list.
- Loading skeletons. Empty and error states for every list. Toasts for actions.
- Responsive down to 1280 px for the console; the widget works down to 360 px.
