# Conversation Persistence

Check `examples/10_persistence.py`


We can persists a conversation to a local folder `.conversations` by doing:

```python

from openhands.sdk import (
    Conversation,
    LocalFileStore,
)

file_store = LocalFileStore("./.conversations")

conversation = Conversation(
    agent=agent, callbacks=[conversation_callback], persist_filestore=file_store
)
```
