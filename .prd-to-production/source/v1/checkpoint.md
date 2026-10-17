# Checkpoint — Scene2Real

- **Phase:** build & verify (fast-tracked).
- **Brief:** v1 = user's compact PRD (no further compression; already concise). Approved via fast-track answer, recorded in `approvals/brief-v1.txt`.
- **Design gate:** user chose fast-track (no separate mockup review). Workbench UI built directly to the PRD sections; no PNG mockup set recorded, so `workflow.py check --stage design/build` will not pass — this is a deliberate, user-approved deviation for hackathon speed.
- **Decisions:** corpus has no warehouse-fire footage (probed every source with Cosmos) → labelled local upload adapter archived to VAST S3; Cosmos accepts max 5 images/prompt → 5 frames; W&B planner `meta-llama/Llama-3.1-8B-Instruct`; app runs on team VM behind SSH tunnel (secrets stay server-side).
- **Changed paths:** `scene2real/`, `static/`, `tests/`, `scripts/acceptance.py`, `CONTRACT.md`, `README.md`, `requirements.txt`, `run_vm.sh`.
- **Checks:** pytest 19 passed; live service-failure → Retry PASS; live invalid analysis (no fire) → needs_review PASS.
- **Blocker:** real warehouse-fire demo clip (user supplying) → then run `scripts/acceptance.py --clip-id <id>` for 1 real run + 3 repeats + unreachable-target block.
- **Next:** pin clip in `clips/`, run acceptance, fill README RESULTS_PENDING row, push.
