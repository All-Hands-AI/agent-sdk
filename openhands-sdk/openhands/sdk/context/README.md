---
title: Context
description: Skills and knowledge that agents can rely on during conversations. Provides repository context and structured knowledge.
---

# Context

Context provides skills and knowledge the agent can rely on during a conversation.

## Key Components

- **AgentContext**: Composes skills; pass to Agent to condition behavior
- **RepoSkill**: Pulls knowledge from `.openhands/skills/repo.md` or explicit content
- **KnowledgeSkill**: Embeds structured knowledge with optional triggers

## Quick Example

```python
from openhands.sdk.context import AgentContext, KnowledgeSkill

agent_context = AgentContext(
    skills=[
        KnowledgeSkill(
            name="flarglebargle",
            content="If the user says flarglebargle, compliment them.",
            triggers=["flarglebargle"],
        ),
    ]
)
```
