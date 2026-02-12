# VS Code Agent - Quick Reference

## 🚀 Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn langchain-openai langchain pydantic

# Start server
uvicorn main:app --reload --port 6080

# Test health
curl http://localhost:6080/health
```

## 📡 API Endpoints

### Execute Task
```bash
POST /vscode/execute

{
  "query": "read package.json",
  "user_id": "user123",
  "chat_id": "chat456",
  "workspace_context": {
    "workspaceRoot": "/path/to/project",
    "currentFile": "src/main.py",
    "workspaceStructure": "file tree..."
  }
}
```

### Clear Session Memory
```bash
DELETE /vscode/memory/{user_id}/{chat_id}
```

### Clear All Memory
```bash
DELETE /vscode/memory
```

### List Tools
```bash
GET /vscode/tools
```

## 🔧 Available Tools

| Tool | Description | Input |
|------|-------------|-------|
| `read_file` | Read file contents | `path: str` |
| `write_to_file` | Create/overwrite file | `path: str, content: str` |
| `replace_in_file` | Edit file with SEARCH/REPLACE | `path: str, diff: str` |
| `list_files` | List directory | `path: str, recursive: bool` |
| `search_files` | Regex search | `path: str, regex: str, file_pattern: str?` |
| `execute_command` | Run shell command | `command: str, requires_approval: bool` |
| `ask_followup_question` | Ask user | `question: str, options: List[str]?` |
| `attempt_completion` | Complete task | `result: str, command: str?` |

## 🔄 Request/Response Flow

### Step 1: User Query
```
Request → Backend:
{
  "query": "read README.md",
  "user_id": "user123",
  "chat_id": "chat456"
}

Response ← Backend:
{
  "response": "{\"tool\": \"read_file\", \"path\": \"README.md\"}",
  "user_id": "user123",
  "chat_id": "chat456"
}
```

### Step 2: Tool Execution Result
```
Request → Backend:
{
  "query": "TOOL EXECUTION RESULT:\nFile contents of README.md:\n# Title\n...",
  "user_id": "user123",
  "chat_id": "chat456"
}

Response ← Backend:
{
  "response": "{\"tool\": \"attempt_completion\", \"result\": \"Analysis...\"}",
  "user_id": "user123",
  "chat_id": "chat456"
}
```

## ⚙️ Critical Configuration

### Dynamic Max Iterations (Prevents Loops, Allows Multi-Step)
```python
# Get max_iterations based on query complexity (2-3)
max_iters = self._get_max_iterations(user_query)

agent_executor = AgentExecutor(
    agent=agent,
    tools=self.tools,
    max_iterations=max_iters,  # ← 2 for simple, 3 for complex
    early_stopping_method="generate"  # ← Graceful handling
)
```

**Iteration Strategy:**
- Simple tasks (read, write): 2 iterations
- Complex tasks (search, analyze): 3 iterations  
- Tool results: 2 iterations
- Prevents infinite loops while allowing multi-step workflows

### Azure OpenAI Configuration
```python
# config.py
AZURE_OPENAI_ENDPOINT = "https://your-endpoint.openai.azure.com/"
AZURE_OPENAI_API_KEY = "your-api-key"
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
```

## 🐛 Debugging Checklist

- [ ] Dynamic `max_iterations` logic implemented in `vscode_agent_service.py`
- [ ] `early_stopping_method="generate"` set (graceful handling)
- [ ] System prompt explains workflow clearly
- [ ] VS Code extension sends "TOOL EXECUTION RESULT:" prefix
- [ ] Workspace context included in initial requests
- [ ] Session memory working (check with `/vscode/memory`)
- [ ] Logs show 2-3 tool calls max per request (not infinite loops)

## 📊 Expected Log Output

### ✅ Good (Proper Multi-Step)
```
INFO - Processing VS Code task: search for function...
DEBUG - Complex search query detected, max_iterations=3
INFO - Task completed for session user123_chat456
INFO - VS Code task completed. Response length: 245 chars
```

### ✅ Good (Simple Task)
```
INFO - Processing VS Code task: read README.md...
DEBUG - Simple query detected, max_iterations=2
INFO - Task completed for session user123_chat456
INFO - VS Code task completed. Response length: 52 chars
```

### ❌ Bad (Infinite Loop - Shouldn't Happen Now)
```
INFO - Processing VS Code task: read README.md...
WARNING - Tool called: read_file (iteration 1)
WARNING - Tool called: read_file (iteration 2)
WARNING - Tool called: read_file (iteration 3)
WARNING - Tool called: read_file (iteration 4)
ERROR - Agent stuck in loop
```

## 🔍 Common Issues

### Issue: Agent calls tool repeatedly in infinite loop
**Solution:** Check dynamic `max_iterations` is working (should be 2-3 max)

### Issue: Agent doesn't understand results
**Solution:** Ensure VS Code sends "TOOL EXECUTION RESULT:" prefix

### Issue: No workspace context
**Solution:** Include `workspace_context` in request

### Issue: Memory not persisting
**Solution:** Check session_id format: `{user_id}_{chat_id}`

## 📝 Tool Response Format

All tools return JSON:
```json
{
  "tool": "tool_name",
  "param1": "value1",
  "param2": "value2"
}
```

Example responses:
```json
{"tool": "read_file", "path": "src/main.py"}
{"tool": "write_to_file", "path": "test.txt", "content": "Hello"}
{"tool": "list_files", "path": ".", "recursive": true}
{"tool": "attempt_completion", "result": "Task complete!"}
```

## 🧪 Test Commands

### Test read_file
```bash
curl -X POST http://localhost:6080/vscode/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "read README.md",
    "user_id": "test",
    "chat_id": "test"
  }'
```

### Test with tool result
```bash
curl -X POST http://localhost:6080/vscode/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "TOOL EXECUTION RESULT:\nContents: Hello World",
    "user_id": "test",
    "chat_id": "test"
  }'
```

### List tools
```bash
curl http://localhost:6080/vscode/tools | jq
```

### Check health
```bash
curl http://localhost:6080/health | jq
```

## 💡 Best Practices

1. **Use dynamic max_iterations (2-3)** - Prevents loops, allows multi-step tasks
2. **Set early_stopping_method="generate"** - Graceful handling of max iterations
3. **Include workspace context** - Helps agent understand project structure
4. **Use session IDs consistently** - Maintains conversation history
5. **Clear memory periodically** - Prevents memory bloat
6. **Monitor logs** - Watch for iteration counts and query complexity detection
7. **Test with curl first** - Verify backend works before testing extension

## 📚 Documentation Files

- `VSCODE_AGENT_FIX.md` - Detailed explanation of the fix
- `VSCODE_AGENT_GUIDE.md` - General usage guide
- `QUICK_REFERENCE.md` - This file
- `README.md` - Project overview

## 🎯 Success Criteria

Your backend is working correctly if:

✅ Each request triggers 1-3 tool calls based on complexity (not infinite loops)
✅ Simple queries use 2 iterations, complex queries use 3 iterations
✅ Tool responses are valid JSON
✅ Session memory persists across requests
✅ "TOOL EXECUTION RESULT:" messages are processed correctly
✅ Graceful handling when max iterations reached (generates response)
✅ VS Code extension can execute tools successfully
✅ Multi-step tasks work: search → read → complete

## 🚨 Emergency Fixes

### Reset Everything
```bash
# Stop server
# Clear all memory
curl -X DELETE http://localhost:6080/vscode/memory

# Restart server
uvicorn main:app --reload --port 6080
```

### Check Configuration
```python
# Verify in Python console
from vscode_agent_service import vscode_agent_service
print(len(vscode_agent_service.tools))  # Should be 8
print(vscode_agent_service._memory_store)  # Shows active sessions
```

---

**Need more help?** See `VSCODE_AGENT_FIX.md` for detailed explanations.
