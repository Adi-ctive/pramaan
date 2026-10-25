# Conversation log

What the owner asked, in order, and what was done. For a new Claude account picking this up mid-way. Read docs/HANDOFF.md
first, then this. Add an entry every time the owner asks for something and every time a step finishes.

## 24 Oct 2026

1. Asked: read the Dishaara chat, build a second site for SIH 2026 PS SIH26261 from the spec pack, hosted on Vercel with a Mongo
   backend, using as few tokens as possible. Done: phases 0 to 10 of the spec, deployed to https://pramaan-sih26.vercel.app.
2. Asked what they had to provide. Gave the Mongo URI (Dishaara cluster, reused with a separate "pramaan" database). Said they know
   no demo passwords, so demo login is one click.
3. Said the UI was naive and they could not tell what they were looking at. Redesigned it (landing page, demo roles, verdicts).
4. Pasted the full "Build PRAMAAN completely" phases 0 to 10 prompt. Finished every phase, 8/8 Playwright acceptance tests.
5. Asked what was missing and why floor plans are needed. Built the add-ons: Hindi, tables, floor plans, video, two-step sign-in.
6. Asked for a plain explanation of what the product does and how to use it. Explained in chat.
7. Said the UI still had no affordance, just bulk text. Rebuilt it as a traffic-light queue with guided problem-by-problem review.
8. Showed misplaced evidence boxes and asked how to test on real documents and floor plans. Fixed the boxes.
9. Asked why the spec forbade real documents. Amended the spec (DECISIONS #24): real college data allowed with permission,
   gitignored realdata/, masked IDs, eval-real command.
10. Complained the PC was almost full and things were slow. Stopped the eval and freed disk.

## 25 Oct 2026

11. Asked to use public datasets where available. Fetched small subsets: MIT Indoor 67 (360), CubiCasa5K (60), IIIT-HW-Dev (failed).
12. Asked how to clean more disk space. Gave advice in chat.
13. Asked to upload to GitHub without keys, then to make it public. Done: https://github.com/Adi-ctive/pramaan (public).
14. Pasted the Phase 7 multi-agent spec and asked to put it on GitHub and on the live app, with a local AI backend if possible.
    Done: eight LangGraph agents on Ollama qwen2.5:7b-instruct, local AI worker for the hosted site, commit afc70ba.
    Measured: same flags as the fixed pipeline, no extra flags, 4 to 25 times slower.
15. Asked if multi-agent is better to show. Answer: show it as an add-on (timeline tab), keep the fixed pipeline for results.
16. Asked why agents did not improve results. Answer: the synthetic test set has nothing the rules miss. A harder set is needed.
17. Asked for a much bigger test set from online datasets, in the thousands, plus project logs a new account can pick up.
    Started: docs/HANDOFF.md, this log, scripts/fetch_public_data.py large sets, pramaan/evaluate_large.py (tasks.py eval-large).
    Found and fixed: the noise detector flagged 100% of real genuine scans. Real receipts: classical tamper checks cannot tell
    genuine from tampered. Date parser now reads 968 of 973 real receipt dates (was 725).
18. Asked to keep updating the project logs and conversation logs, because the weekly limit may end at any time and they will
    switch to a different Claude account. Doing: this file plus HANDOFF.md, committed and pushed as work goes.

## Where the current task stands

See the newest "Session log" entry in docs/HANDOFF.md.
