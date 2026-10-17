# Scene2Real

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
