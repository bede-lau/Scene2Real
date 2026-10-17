# Scene2Real

## PRD-to-production workflow

Bede's personal PRD-to-production skill is bundled in this repository, including
its phase guides, approval and verification helpers, and pinned upstream resources.
No personal skill installation is required.

[CLAUDE.md](CLAUDE.md) loads the complete workflow from
[SKILL.md](.claude/skills/prd-to-production/SKILL.md). Claude Code also discovers it
as a project skill in `.claude/skills/prd-to-production/`.

### Use it

Clone or pull this repository, open Claude Code in its root, and provide your PRD:

```text
/prd-to-production path/to/your-prd.md
```

Follow the staged workflow: approve the compact PRD, review and approve desktop
and mobile mockups for every page/tab, then build and verify against the approved
scope. A repository checkout does not grant those product approvals.

The helpers require Python 3.9 or newer and use only the standard library. Run
these commands from the repository root:

```sh
python3 .claude/skills/prd-to-production/scripts/sources.py verify
python3 .claude/skills/prd-to-production/scripts/workflow.py --help
```

When starting a PRD build, initialize and inspect its durable artifacts:

```sh
python3 .claude/skills/prd-to-production/scripts/workflow.py init --root .
python3 .claude/skills/prd-to-production/scripts/workflow.py status --root .
```

Artifacts and approval records live in `.prd-to-production/`. Other coding agents
can read `CLAUDE.md`, the bundled `SKILL.md`, and the relevant phase guides directly.
Rendering mockups and testing an app still require the appropriate browser tools
and the dependencies selected for that app.

### Included resources

| Resource | Location |
| --- | --- |
| Complete workflow | [SKILL.md](.claude/skills/prd-to-production/SKILL.md) |
| PRD compaction and inventory | [compact.md](.claude/skills/prd-to-production/references/compact.md) |
| Mockup and design guidance | [design.md](.claude/skills/prd-to-production/references/design.md) |
| Implementation and acceptance checks | [build-verify.md](.claude/skills/prd-to-production/references/build-verify.md) |
| Upstream source map and usage guidance | [sources.md](.claude/skills/prd-to-production/references/sources.md) |
| Approval and artifact helper | [workflow.py](.claude/skills/prd-to-production/scripts/workflow.py) |
| Source lookup and integrity helper | [sources.py](.claude/skills/prd-to-production/scripts/sources.py) |
| Exact upstream revisions, URLs, licenses, and hashes | [sources.lock.json](.claude/skills/prd-to-production/sources.lock.json) |
| Codex display metadata | [openai.yaml](.claude/skills/prd-to-production/agents/openai.yaml) |

The offline reference bundle contains 30 pinned files from OpenDesign, Impeccable,
ReUI, coss ui, and CopilotKit, including their original license files. It is a
curated reference bundle; component examples may require additional dependencies
when adapted into an app. The original skill and its bundled resources are
preserved unchanged.

OpenDesign and Impeccable retain Apache-2.0 notices; ReUI and CopilotKit retain MIT
notices; the bundled coss source retains its AGPL-3.0 license. Preserve applicable
notices and review the source's license when reusing it. Bundling these resources
does not assign a new license to Scene2Real.

Claude Code integration follows its official
[project instruction imports](https://code.claude.com/docs/en/memory#import-additional-files)
and [project skills](https://code.claude.com/docs/en/skills) documentation.
