# Demo script

About 8 minutes. Works on the live site (https://pramaan-sih26.vercel.app) or locally after `python tasks.py demo` (http://localhost:5180).
Sample files: /samples/ on the same site.

1. **Start.** Open the site. The landing page explains the flow. Click **Enter as Senior Officer**.
2. **Queue.** "Applications to review" shows 5 applications, worst first. Narmada College has serious problems. Shivalik passes everything.
3. **Problem application.** Open Narmada College of Engineering. Point at:
   - the red verdict and the 9-check grid;
   - "Building Completion Certificate not uploaded";
   - "Fire Safety NOC has expired" (click the evidence, the date is boxed on the document);
   - the name mismatch between the society registration and the lease deed;
   - claimed intake 180 vs 120 in AICTE records ("AICTE records comparison" tab);
   - the affidavit: scanned and handwritten, routed to manual reading, and a pasted-in date (tick "Show edit heatmap");
   - the accreditation QR mismatch ("Issuer confirmations" tab shows issuer vs document values);
   - lab photo reused from another college (click "Compare with matching image");
   - "12 computers seen in photos, 30 claimed", and a photo taken 40 km from campus;
   - the fee receipt with instruction-like text, treated as data and flagged.
4. **Clean application.** Open Shivalik Institute. "All checks passed", every document confirmed with its issuer. Its affidavit is bilingual
   (Hindi labels) and is still read correctly. Also point at the faculty list (rows match AICTE records) and the floor plan (lab area measured).
   Narmada's floor plan shows Lab 1 at 48 sq m against 66 claimed.
5. **Institution flow.** Open /host-a/ (Approval Portal, mock). Pick INST-012, intake 180, Lab 1 = 30, Lab 2 = 15. Upload the PROBLEM-A
   samples slot by slot. The widget warns on the expired Fire NOC immediately. Submit. The college sees only the items to fix, no forensics.
6. **Rectify.** Upload `FIRE_NOC__fire_noc_renewed.pdf` in the Fire NOC slot. The expired item disappears. In the console, "How it was
   processed" shows report v2 and that only the Fire NOC was re-checked.
7. **Decide.** In Narmada's page the decision note is locked. Click Review on a serious finding, give a reason, Dismiss. The note stays locked
   until every serious finding is confirmed or dismissed. Then record it.
8. **Second portal.** Open /host-b/ (University Affiliation Portal, mock). Different slot names ("Fire Clearance Certificate"), different rule
   pack, same engine.
9. **Audit.** Switch role to Auditor (top right). Audit trail, Verify chain: intact. Locally, `curl -X POST localhost:8010/api/admin/tamper-demo
   -H "X-Seed-Token: <token>"` edits one row, and Verify shows the chain broken at #3. Reseed to restore.
10. **Accuracy.** Switch to Rule Admin, open Accuracy, "Run quick evaluation". The full numbers (FULL and LITE) are in docs/EVAL-FULL.md and
    docs/EVAL-LITE.md.
11. **Two-step sign-in.** Top right, "2-step sign-in": scan the QR with any authenticator app and confirm a code.
12. **LITE vs FULL.** The live site is LITE (CPU). Locally with MODE=FULL the affidavit's handwriting is read by the OCR and Handwriting
    Models, photos are counted by the Object Detector, and the summary is written by the Reasoning LLM and checked by the Critic.

Backup: record steps 3 to 7 as a screen capture before the event in case the network fails.
