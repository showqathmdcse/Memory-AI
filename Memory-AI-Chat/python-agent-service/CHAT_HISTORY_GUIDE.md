# Chat History Management Guide

## Overview

The agent service now supports **two storage backends** for conversation history:

1. **LangChain Built-in Memory** (Recommended) - Fast, reliable, sequential
2. **ChromaDB** (Optional) - Vector database with semantic search

## Why LangChain Memory is Recommended

### Problems with ChromaDB for Chat History:
- **Semantic search unreliability**: Relevant tool results might not be retrieved if query doesn't match semantically
- **Non-sequential retrieval**: Messages can come back out of order
- **Performance overhead**: Embedding every message is expensive
- **Not guaranteed**: For tool context retention, you need sequential history

### Benefits of LangChain Memory:
- ✅ **Sequential order guaranteed**: Messages stored in conversation order
- ✅ **Fast**: No embedding overhead, direct memory access
- ✅ **Reliable**: Tool results always available to subsequent messages
- ✅ **Simple**: No external dependencies, built into LangChain
- ✅ **Professional**: Industry standard approach for conversational agents

## Configuration

### Using LangChain Memory (Default & Recommended)

In your `.env` file:

```env
CHAT_HISTORY_STORAGE=langchain
CHAT_HISTORY_WINDOW_SIZE=20
```

- **CHAT_HISTORY_STORAGE**: Set to `langchain` for in-memory storage
- **CHAT_HISTORY_WINDOW_SIZE**: Number of messages to keep in memory (default: 20)

### Using ChromaDB (Optional)

In your `.env` file:

```env
CHAT_HISTORY_STORAGE=chroma
CHAT_HISTORY_WINDOW_SIZE=15
```

- **CHAT_HISTORY_STORAGE**: Set to `chroma` for vector database storage
- **CHAT_HISTORY_WINDOW_SIZE**: Number of messages to retrieve with semantic search

## How It Works

### LangChain Memory Storage

1. **User sends message** → Stored in ConversationBufferWindowMemory
2. **Agent executes tools** → Tool calls and results stored in memory
3. **Assistant responds** → Response stored in memory
4. **Next message** → Agent has access to last N messages in sequential order
5. **Tool context retained** → Agent can reference previous tool results

Example flow:
```
User: "list ado projects"
→ Tool called: get_projects()
→ Result: [{org: "ascendionava", projects: [...]}]
→ Stored in memory

User: "filter tickets by state Active"
→ Agent sees previous tool result in memory
→ Extracts org and project from previous result
→ Calls filter_tickets with extracted parameters
→ No need to ask user again!
```

### ChromaDB Storage (when enabled)

1. **User sends message** → Embedded and stored in ChromaDB
2. **Semantic search** → Retrieves relevant messages based on similarity
3. **Agent executes** → Uses retrieved context
4. **Tool results** → Stored with embeddings

## API Usage

### Clear Session Memory

For LangChain storage, you can clear a specific session's memory:

```python
from agent_service import agent_service

# Clear memory for a specific user/chat session
agent_service.clear_session_memory(user_id="user123", chat_id="chat456")
```

### Memory Lifecycle

- **LangChain**: Memory persists as long as the service is running
- **ChromaDB**: Persistent storage, survives restarts

## Best Practices

### For Development
- Use **LangChain memory** for faster iteration and debugging
- Set window size to 20-30 messages for good context

### For Production
- Use **LangChain memory** for most use cases
- Consider ChromaDB only if you need:
  - Persistent storage across service restarts
  - Semantic search across large conversation histories
  - Long-term conversation analytics

### Memory Window Size

| Use Case | Recommended Size |
|----------|-----------------|
| Quick chats | 10-15 messages |
| Standard conversations | 20-30 messages |
| Complex multi-tool workflows | 30-50 messages |

**Note**: Larger windows = more context but higher token costs

## Tool Context Retention

Both storage types now properly retain tool execution results:

### LangChain Memory
```python
# Tool result stored as:
[Context] [Tool: get_projects] Args: {...} | Result: {...}
```

### ChromaDB
```python
# Two entries stored:
ToolCall: get_projects with args: {...}
ToolResult: get_projects returned: {...}
```

## Troubleshooting

### Agent keeps asking for the same information

**Symptom**: Agent asks for organization/project again after you already provided it.

**Solution**: Ensure you're using LangChain memory:
```env
CHAT_HISTORY_STORAGE=langchain
```

### Out of memory errors

**Symptom**: Service crashes with memory errors.

**Solution**: Reduce window size:
```env
CHAT_HISTORY_WINDOW_SIZE=10
```

### Context not retained across restarts

**Symptom**: Previous conversations lost after service restart.

**Expected Behavior**: 
- LangChain memory is in-memory only (by design)
- Use ChromaDB if you need persistence:
```env
CHAT_HISTORY_STORAGE=chroma
```

## Performance Comparison

| Feature | LangChain | ChromaDB |
|---------|-----------|----------|
| Speed | ⚡ Instant | 🐢 Requires embedding |
| Memory | Low | High (embeddings) |
| Reliability | ✅ 100% | ⚠️ Depends on semantic match |
| Order | ✅ Sequential | ⚠️ By relevance |
| Persistence | ❌ In-memory | ✅ Database |
| Setup | ✅ None | ⚠️ Requires ChromaDB |

## Migration Guide

### Switching from ChromaDB to LangChain

1. Update `.env`:
```env
CHAT_HISTORY_STORAGE=langchain
```

2. Restart the service

3. Start a new conversation (old ChromaDB history won't be migrated)

### Switching from LangChain to ChromaDB

1. Update `.env`:
```env
CHAT_HISTORY_STORAGE=chroma
```

2. Restart the service

3. Previous in-memory conversations will be lost (expected)

## Examples

### Example 1: Multi-step Tool Workflow (LangChain)

```
User: "list all my projects"
Assistant: [Lists 4 projects from organization "ascendionava"]

User: "get tickets from the AAVA project"
Assistant: [Uses org="ascendionava" and project="AAVA" from previous result]

User: "filter by state Active"
Assistant: [Uses project info from previous tool call, doesn't ask again]
```

### Example 2: Same Flow with ChromaDB (Old Behavior)

```
User: "list all my projects"
Assistant: [Lists 4 projects]

User: "get tickets from the AAVA project"
Assistant: [Might ask for organization again if not semantically matched]

User: "filter by state Active"
Assistant: "I need the organization name and project name"
```

## Conclusion

**Recommendation**: Use **LangChain memory** (`CHAT_HISTORY_STORAGE=langchain`) for:
- ✅ Reliable tool context retention
- ✅ Fast performance
- ✅ Simple setup
- ✅ Professional-grade conversational AI

Only use ChromaDB if you specifically need persistent storage across service restarts or semantic search capabilities.
