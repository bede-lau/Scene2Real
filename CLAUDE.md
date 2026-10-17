# CLAUDE.md — Real-Time Video Agents Hack (VAST Builders Challenge, London)

Event page: https://tokensand.com/vastlondon · Date: **Sat 17 Oct 2026** · Team 28

**Use this file to stay on track.** Before starting any new piece of work, check it against the goal,
the deadline and the judging criteria below. If it doesn't help the 2-minute demo, don't build it.

## The brief

Build **one video agent** that searches footage, answers questions, spots events, or takes action —
working by end of day.

- Pick a **specific** use case ("flag someone missing a hard hat", not "watch for safety issues").
- Adapt the idea to the **footage that's actually available** (the pre-ingested team corpus, see below).
- Search quality depends on what the ingest prompt captured in each segment description. We can
  re-ingest video with a different prompt if the default descriptions miss what we need.
- Build during the event only.

## Deadline & schedule (BST)

| Time | |
|---|---|
| 9:30 | Build begins |
| 12:30 | Lunch |
| **16:30** | **Submission deadline** + demos start |
| 18:30 | Closing & awards |

Rule of thumb: feature-freeze by ~15:30, then README, demo video, submission.

## What to submit (tokensand.com/vastlondon → Submit project)

- [ ] GitHub repo reviewers can access
- [ ] Short demo video (~2 min) with a shareable link
- [ ] What we built + tools used
- [ ] Team names and contact emails
- [ ] Optional: working website, project screenshot

## Judging (what to optimise for)

1. A clear idea that uses the **video search / summarization stack**
2. **Technical quality** + documentation of **inputs, outputs, and evaluation** (README sections)
3. Design / UX of the demo
4. Uses **≥ 3 sponsor tools**
5. A tight **2-minute demo**

Prizes: 1st NVIDIA DGX Spark, 2nd Hugging Face Microduck.

## Sponsor stack (aim to visibly use ≥ 3)

| Sponsor | What it gives us |
|---|---|
| VAST Data (AI OS) | Video ingestion; S3 buckets + VastDB keep video, vectors and metadata together |
| NVIDIA (VSS Blueprint + Cosmos) | Turns video segments into searchable descriptions + embeddings; Cosmos-Reason VLM, Cosmos-Embed |
| CoreWeave | GPUs serving the models (Cosmos-Reason, YOLO11, Cosmos-Embed1, Canary-1B ASR) |
| Weights & Biases | Serverless LLM inference (OpenAI-compatible) + Weave tracing/observability |
| Cursor | IDE / dev over SSH to the team VM |

Event resources: Video search overview, YOLO object detection, CoreWeave GPUs, ARIA research agent
(see links on the event page and `ref/vast-builders-challenge`).

## Environment facts

- Work on the **team VM** over SSH (alias `bc-mattlo0546`). All credentials live on the VM in
  `/config/team-28.config` — **never copy secrets into this repo or commit `.env`.**
- The team corpus lives in VAST S3, not on VM disk:
  - `s3://team-28-vss-chunks/team-28/*.mp4` — ~612 × 25 s chunks (~12 source videos, 24 GB)
  - `s3://team-28-vss-chunks-segments` — segment mp4s + `detections/*.json.gz` YOLO sidecars
  - Also browsable via VSS `GET /api/v1/videos/explore`
- VAST S3 uses a self-signed cert (`verify=False`).
- W&B inference needs header `OpenAI-Project: vastdata/team-28`.
- GPU model endpoints (on the CoreWeave host, bearer token in team config): Cosmos-Reason `:8001`,
  YOLO11 `:8002`, Cosmos-Embed1 `:8003`, Canary-1B `:8004`.
- Event repo with skills/docs: `~/vast-builders-challenge` on the VM; local copy in `ref/`.

## Repo map

- `vss_client.py` — thin client for the VSS summarize API
- `check_connections.py` — smoke test for VAST S3, Cosmos/VSS, W&B
- `yolo_smoke.py` — local YOLO sanity check
- `README.md` — must end up with **Inputs / Outputs / Evaluation** filled in (currently TODO)

## Guardrails for Claude

- Prefer the event stack (VSS, Cosmos, VAST, W&B) over generic alternatives — sponsor usage is scored.
- Prefer the smallest thing that makes the demo work; no infra yak-shaving, no refactors.
- Use the existing corpus; don't spend time sourcing new footage unless the use case truly needs it.
- Keep the README's Inputs / Outputs / Evaluation current as features land.
- Trace LLM calls with Weave so we can show observability in the demo.
- If a task drifts from the chosen use case, flag it and ask before continuing.

---

# PRD-to-production workflow (Scene2Real)

Use Bede's bundled PRD-to-production workflow for PRD-to-app work in this repository.
Its complete instructions are imported below:

@.claude/skills/prd-to-production/SKILL.md

## Repository paths

- `<skill-dir>` means `.claude/skills/prd-to-production` relative to the repository root.
- Resolve the skill's reference and script paths relative to that directory.
- `<project>` means the target project root; use `.` when working on Scene2Real.
- Workflow artifacts belong in `<project>/.prd-to-production/`.
- Read the phase references when needed; upstream files are supporting resources.

The workflow requires separate approval of the compact PRD and the complete mockup
set before production implementation. Apply those gates to PRD-to-app builds;
ordinary repository maintenance does not start a new product workflow.

## Helper commands

Run from the repository root with Python 3.9 or newer:

```sh
python3 .claude/skills/prd-to-production/scripts/sources.py verify
python3 .claude/skills/prd-to-production/scripts/workflow.py init --root .
python3 .claude/skills/prd-to-production/scripts/workflow.py status --root .
```

Initialize workflow artifacts when starting a PRD build. Record only approvals
actually received from the user. See [README.md](README.md) for team usage and
resource provenance.
