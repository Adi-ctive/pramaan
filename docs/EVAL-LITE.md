# Evaluation report (LITE mode)

Run `EVAL-EE27E5F7` at 2026-10-24T06:38 UTC, 6 samples per class, 266.8 s.
All material is freshly generated synthetic data with known answers. Numbers are as measured.

| Metric | Value |
|---|---|
| Field exact match, digital PDFs | 100.0% (114 fields) |
| Printed CER, digital PDFs | 0.0% |
| Field exact match, scanned printed (OCR Model) | n/a |
| Printed CER, scanned (OCR Model) | n/a |
| Handwriting CER | n/a |
| Handwriting exact match | n/a |
| Validation: single-defect apps flagged exactly right | 91.7% (24 apps) |
| Seeded discrepancy recall | 100.0% (14/14) |
| HIGH/MEDIUM flags on golden apps | 0 |
| Source-verification success (golden) | 100.0% of 14 verifiable |
| Lab monitor count MAE | 0.0 over 12 photos (classical counter) |
| Room-type accuracy | n/a |
| Avg processing time | 1646 ms/app, 242 ms/doc |
| Alert delay | 0.0 ms (Alerts are raised in the same run that finds the condition; delay is measured in-process.) |
| Estimated manual effort reduction | 86.3% (assumes 6.0 min/doc baseline, 2.0 min/flag) |

## Anomaly detection per forgery type

| Type | Precision | Recall | F1 | TP/FP/FN |
|---|---|---|---|---|
| date edit (pixel) | 1.0 | 1.0 | 1.0 | 6/0/0 |
| name swap (pixel) | 1.0 | 1.0 | 1.0 | 6/0/0 |
| amount alteration (pixel) | 1.0 | 1.0 | 1.0 | 6/0/0 |
| pasted stamp | 1.0 | 1.0 | 1.0 | 6/0/0 |
| copy-move inside page | 1.0 | 1.0 | 1.0 | 6/0/0 |
| PDF incremental edit | 1.0 | 1.0 | 1.0 | 6/0/0 |
| PDF edited after signing | 1.0 | 1.0 | 1.0 | 6/0/0 |
| broken / untrusted PDF signature | 1.0 | 1.0 | 1.0 | 6/0/0 |
| QR payload mismatch | 1.0 | 1.0 | 1.0 | 6/0/0 |
| invalid QR signature | 1.0 | 1.0 | 1.0 | 6/0/0 |
| reused photo (pHash) | 1.0 | 0.833 | 0.909 | 5/0/1 |
| prompt-injection text | 1.0 | 1.0 | 1.0 | 6/0/0 |

## Validation accuracy per rule (single-defect applications)

| Finding code | Precision | Recall | TP/FP/FN |
|---|---|---|---|
| DOC_MISSING | 1.0 | 1.0 | 2/0/0 |
| DOC_EXPIRED | 1.0 | 1.0 | 2/0/0 |
| WRONG_DOC_TYPE | 1.0 | 1.0 | 2/0/0 |
| INTAKE_MISMATCH_RECORDS | 1.0 | 1.0 | 2/0/0 |
| NAME_MISMATCH | 1.0 | 1.0 | 2/0/0 |
| DATE_IMPLAUSIBLE | 1.0 | 1.0 | 2/0/0 |
| FORMAT_INVALID | 1.0 | 1.0 | 2/0/0 |
| EXIF_LOCATION_MISMATCH | 1.0 | 1.0 | 2/0/0 |
| DUPLICATE_ACROSS_INSTITUTIONS | 1.0 | 1.0 | 2/0/0 |
| QR_MISMATCH | 1.0 | 1.0 | 2/0/0 |
| PDF_MODIFIED_AFTER_SIGNING | 1.0 | 1.0 | 2/0/0 |

| Variant | Institution | Expected | Found (HIGH/MEDIUM) |
|---|---|---|---|
| clean | INST-011 | - | - |
| clean | INST-003 | - | - |
| missing document | INST-011 | DOC_MISSING | DOC_MISSING |
| missing document | INST-003 | DOC_MISSING | DOC_MISSING |
| expired document | INST-011 | DOC_EXPIRED | DOC_EXPIRED |
| expired document | INST-003 | DOC_EXPIRED | DOC_EXPIRED |
| wrong document in slot | INST-011 | WRONG_DOC_TYPE | WRONG_DOC_TYPE |
| wrong document in slot | INST-003 | WRONG_DOC_TYPE | WRONG_DOC_TYPE |
| intake mismatch vs records | INST-011 | INTAKE_MISMATCH_RECORDS | INTAKE_MISMATCH_RECORDS |
| intake mismatch vs records | INST-003 | INTAKE_MISMATCH_RECORDS | INTAKE_MISMATCH_RECORDS |
| name mismatch across documents | INST-011 | NAME_MISMATCH | NAME_MISMATCH |
| name mismatch across documents | INST-003 | NAME_MISMATCH | NAME_MISMATCH |
| implausible issue date | INST-011 | DATE_IMPLAUSIBLE | DATE_IMPLAUSIBLE |
| implausible issue date | INST-003 | DATE_IMPLAUSIBLE | DATE_IMPLAUSIBLE |
| bad reference-number format | INST-011 | FORMAT_INVALID | FORMAT_INVALID |
| bad reference-number format | INST-003 | FORMAT_INVALID | FORMAT_INVALID |
| EXIF far from campus | INST-011 | EXIF_LOCATION_MISMATCH | EXIF_LOCATION_MISMATCH |
| EXIF far from campus | INST-003 | EXIF_LOCATION_MISMATCH | EXIF_LOCATION_MISMATCH |
| reused photo across institutions | INST-011 | DUPLICATE_ACROSS_INSTITUTIONS | DUPLICATE_ACROSS_INSTITUTIONS |
| reused photo across institutions | INST-003 | DUPLICATE_ACROSS_INSTITUTIONS | DUPLICATE_ACROSS_INSTITUTIONS |
| QR payload mismatch | INST-011 | QR_MISMATCH | QR_MISMATCH |
| QR payload mismatch | INST-003 | QR_MISMATCH | QR_MISMATCH |
| PDF edited after signing | INST-011 | PDF_MODIFIED_AFTER_SIGNING | PDF_EDIT_INDICATOR, PDF_MODIFIED_AFTER_SIGNING |
| PDF edited after signing | INST-003 | PDF_MODIFIED_AFTER_SIGNING | PDF_EDIT_INDICATOR, PDF_MODIFIED_AFTER_SIGNING |

## Seeded demo applications

| Application | Missed | Other flags |
|---|---|---|
| DONOR | none | - |
| GOLDEN-A | none | - |
| PROBLEM-A | none | - |
| GOLDEN-B | none | - |
| PROBLEM-B | none | - |

Handwriting: No Handwriting Model in LITE: handwritten documents route to manual review, CER not measured.
