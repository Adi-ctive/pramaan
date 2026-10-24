# Demo script

About 8 minutes. Works on the live site (https://pramaan-sih26.vercel.app) or locally after `python tasks.py demo` (http://localhost:5180).
Sample files: /samples/ on the same site.

1. **Start.** Open the site. Two doors: click **I review applications**. A short tour points at each part (replay it with "Show me around").
2. **Queue.** One card per application, worst first. Red shield means serious problems; the row of 9 small icons shows which checks failed.
   Click **Review** on Narmada College of Engineering.
3. **Guided review.** Click **Start review**. PRAMAAN shows "Problem 1 of 12": the right document opens, a numbered pin marks the spot,
   the problem is one plain sentence with "Should be / Found", and there are two buttons: **It's a problem** or **Not a problem**.
   Step through with the arrows:
   - Building Completion Certificate was not uploaded;
   - Fire Safety NOC expired on 31 Mar 2026 (pin on the date, QR table below confirms the document itself is genuine);
   - claims 180 students, AICTE approved 120;
   - part of the affidavit looks edited (tick "Show edit heatmap");
   - this lab photo also appears in another college's application (side-by-side view);
   - QR code says "B.Tech Civil Engineering", document says "B.Tech Computer Science and Engineering";
   - 12 computers seen in photos, 30 claimed, and Lab 1 is 48 m² on the floor plan against 66 claimed;
   - the fee receipt contains hidden text aimed at the AI (it was ignored and flagged);
   - name differs between the society registration and the lease deed; photo taken 40 km from campus; handwritten affidavit for a person to read.
4. **Clean application.** Open Shivalik Institute. "All checks passed", every document confirmed with its issuer. Its affidavit is bilingual
   (Hindi labels) and is still read correctly. Also point at the faculty list (rows match AICTE records) and the floor plan (lab area measured).
   Narmada's floor plan shows Lab 1 at 48 sq m against 66 claimed.
5. **Institution flow.** Open /host-a/ (Approval Portal, mock). Pick INST-012, intake 180, Lab 1 = 30, Lab 2 = 15. Upload the PROBLEM-A
   samples slot by slot. The widget warns on the expired Fire NOC immediately. Submit. The college sees only the items to fix, no forensics.
6. **Rectify.** Upload `FIRE_NOC__fire_noc_renewed.pdf` in the Fire NOC slot. The expired item disappears. In the console, "How it was
   processed" shows report v2 and that only the Fire NOC was re-checked.
7. **Decide.** The bar at the bottom says "Decision locked" until every serious problem has been marked, each with a reason saved to the audit
   trail. Then type the decision and record it.
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
