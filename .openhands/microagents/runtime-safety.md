---
name: Runtime Safety Reminder
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers: []
---

Purpose
- Remind the assistant not to use `set -e` or any other `set` flags in this runtime environment. Just run commands directly; they will work as expected.

Usage
- This microagent has no triggers. It can be referenced explicitly by name when assembling context.
- When executing shell commands, avoid adding shell options like `set -e`, `set -eu`, or `set -euo pipefail`.

Guidance
- For multi-step bash sequences, chain commands with `&&` or `;` as needed.
- If a long-running command risks hanging, prefer background execution with output redirection (e.g., `cmd > out.log 2>&1 &`).
- Do not alter global shell options in this environment.

Limitations
- This microagent provides guidance only; it does not execute commands itself.
