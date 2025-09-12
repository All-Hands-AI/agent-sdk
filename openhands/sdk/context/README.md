---
title: Context
description: Microagents and knowledge that agents can rely on during conversations. Provides repository context and structured knowledge.
---

# Context

Context provides microagents and knowledge the agent can rely on during a conversation.

## Key Components

- **AgentContext**: Composes microagents; pass to Agent to condition behavior
- **RepoMicroagent**: Pulls knowledge from `.openhands/microagents/repo.md` or explicit content
- **KnowledgeMicroagent**: Embeds structured knowledge with optional triggers

## Quick Example

```python
from openhands.sdk.context import AgentContext, KnowledgeMicroagent

agent_context = AgentContext(
    microagents=[
        KnowledgeMicroagent(
            name="flarglebargle",
            content="If the user says flarglebargle, compliment them.",
            triggers=["flarglebargle"],
        ),
    ]
)
```
