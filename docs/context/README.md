# Context

Context provides microagents and knowledge the agent can rely on during a conversation.

Key pieces
- RepoMicroagent: pulls knowledge from `.openhands/microagents/repo.md` or explicit content
- KnowledgeMicroagent: embeds structured knowledge with optional triggers
- AgentContext: composes microagents; pass to Agent to condition behavior

Quick example
```python
from openhands.sdk.context import AgentContext, KnowledgeMicroagent, MicroagentMetadata

agent_context = AgentContext(
    microagents=[
        KnowledgeMicroagent(
            name="flarglebargle",
            content="If the user says flarglebargle, compliment them.",
            metadata=MicroagentMetadata(name="flarglebargle", triggers=["flarglebargle"]) ,
        ),
    ]
)
```

