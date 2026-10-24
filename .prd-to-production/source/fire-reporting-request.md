# Source request — England incident reporting

User request, retained verbatim except the skill invocation is identified separately:

> with With a heavier task allocation to devin. So this document download is meant to be a legitimate document that firefighters will use to write their data report after they rescued a fire or when a fire incident has occurred. I want you to deploy a research agent as well to extract and return the template of what a firefighter of the form they would usually fill in, understand each field and what's required, then implement in the app, where the data obtained from the robot's vision extinguish or the vision model's extinguish of the fire can be used to fill up the form. I want you to strictly follow the form, like the actual form's parameters and output. And then if the data can't be retrieved from the Scene to Real app itself, then leave it blank for now. But I want it to be as accurate. I want it to be exactly like a real-life form. Because this is no longer a hackathon project and we're moving it to an actual product.

Explicit workflow: multi-agent-coding-orchestrator, with heavier Devin allocation.

User clarifications:

- Jurisdiction: “England fire and rescue services (research the national reporting standard)”.
- Current specification access: “No — we need to obtain the current specification”.
- Workspace trust: “Approve this exact folder”, referring only to `/Users/bedelau/Scene2Real-sim/scene2real-1` in Devin.
- Earlier constraints remain: “Remember to not touch production code”; local review/testing before any push.

The prior report PRD is the separate one-page demonstration summary request in the conversation. Its evidence integrity, missing-state and text-security constraints remain relevant, but official form layout and parameters now depend on an authoritative current source. Old v2 workflow artifacts are preserved under `fire-reporting/previous-workflow-v2/` and are not approval of this scope.
