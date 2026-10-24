# Progress (Vercel + MongoDB edition)

| Phase | Status | Notes |
|---|---|---|
| 0 Skeleton | Done | Vercel instead of Docker. No GPU probe (serverless). |
| 1 Data, auth, RBAC, audit | Done | Mongo collections, argon2, JWT cookie, lockout, RBAC matrix test, hash-chained audit + tamper test. TOTP not built. |
| 2 Mock ecosystem, synthetic data | Done | 30 fictional institutions, 6 mock issuers (Ed25519), signed QR, scanned affidavit, lab photos with EXIF. No Augraphy/pyHanko. |
| 3 Rule packs, plug-in layer | Done | Two packs, hosts, API keys, slot mapping, widget, HMAC webhooks, upload safety (EICAR signature scan, no ClamAV). |
| 4 Document understanding | LITE only | PDF text layer, keyword classifier, anchor extractor, zxing QR. Scanned/handwritten docs go to manual review. |
| 5 Validation checks | Done | Completeness, expiry, entity match, intake vs records, plausibility, noise/ELA/copy-move, PDF revisions, pHash duplicates, QR + ref lookup. |
| 6 Infrastructure | Partial | EXIF distance/time, reuse, object count (classical counter on synthetic photos, or vision model if GROQ_KEY). No CLIP room type. |
| 7 Agents | Not built | Deterministic DAG with escalation (cheap noise check first, ELA + copy-move only when borderline). Spec allows LITE = DAG. |
| 8 Reports, alerts, review | Done | Case summary with flag ids (template), alerts, dispositions, decision gate 409, rectification re-runs only changed docs. No PDF report export, no email. |
| 9 Console | Done | Queue, detail (3 panes, overlays, heatmap, compare, records diff, verify, timeline), dashboard, alerts, rule packs (validate/diff/dry run/activate), hosts, audit, evaluation. |
| 10 Evaluation | Done | Real numbers from a generated test set + seeded apps. Handwriting CER not measured (no model). |

Next: set MONGODB_URI in Vercel, seed Atlas, run evaluation from the deployed console.
