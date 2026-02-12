# VS Code LangChain Agent Guide

## Overview

The VS Code LangChain Agent is a separate agent service that provides file operation capabilities similar to VS Code extensions. It uses LangChain's tool-calling agents to interact with files, execute commands, and assist with coding tasks.

## Features

- **File Operations**: Read, write, and modify files
- **Search Capabilities**: Search files using regex patterns
- **Command Execution**: Execute shell commands
- **Interactive Queries**: Ask follow-up questions to users
- **Task Completion**: Complete tasks and present results
- **Conversation Memory**: Maintains context across multiple interactions
- **Separate API**: Independent API endpoints from the main chat agent

## Architecture

```
┌─────────────────────────────────────────┐
│         VS Code Agent Service           │
│  (vscode_agent_service.py)              │
├─────────────────────────────────────────┤
│  LangChain Tools:                       │
│  - read_file                            │
│  - write_to_file                        │
│  - replace_in_file                      │
│  - list_files                           │
│  - search_files                         │
│  - execute_command                      │
│  - ask_followup_question                │
│  - attempt_completion                   │
└─────────────────────────────────────────┘
           │
           │ Uses
           ▼
┌─────────────────────────────────────────┐
│      Azure OpenAI (LangChain)           │
│      - Tool Calling Agent               │
│      - Conversation Memory              │
└─────────────────────────────────────────┘
```

## Available Tools

### 1. read_file
Read the contents of a file from the workspace.

**Input:**
- `path` (str): Relative path to the file

**Returns:** JSON tool call instruction

### 2. write_to_file
Write content to a file (creates or overwrites).

**Input:**
- `path` (str): Relative path to the file
- `content` (str): Complete content to write

**Returns:** JSON tool call instruction

### 3. replace_in_file
Replace specific content in a file using SEARCH/REPLACE blocks.

**Input:**
- `path` (str): Relative path to the file
- `diff` (str): SEARCH/REPLACE blocks in the format:
  ```
  ------- SEARCH
  [exact content to find]
  =======
  [new content to replace with]
  +++++++ REPLACE
  ```

**Returns:** JSON tool call instruction

### 4. list_files
List files and directories in a specified path.

**Input:**
- `path` (str): Directory path
- `recursive` (bool): Whether to list recursively

**Returns:** JSON tool call instruction

### 5. search_files
Search for text in files using regex patterns.

**Input:**
- `path` (str): Directory path to search
- `regex` (str): Regular expression pattern
- `file_pattern` (str, optional): Glob pattern to filter files (e.g., "*.py")

**Returns:** JSON tool call instruction

### 6. execute_command
Execute a shell command.

**Input:**
- `command` (str): Shell command to execute
- `requires_approval` (bool): Whether user approval is needed

**Returns:** JSON tool call instruction

### 7. ask_followup_question
Ask the user a clarifying question.

**Input:**
- `question` (str): The question to ask
- `options` (list, optional): List of options to choose from

**Returns:** JSON tool call instruction

### 8. attempt_completion
Complete the task and present results.

**Input:**
- `result` (str): Final result message
- `command` (str, optional): Command to suggest running

**Returns:** JSON tool call instruction

## API Endpoints

### 1. Execute Task
**POST** `/vscode/execute`

Execute a task using the VS Code agent.

**Request Body:**
```json
{
  "query": "List all Python files in the current directory",
  "execution_id": "session_123"
}
```

**Response:**
```json
{
  "response": "Agent's response or tool call JSON",
  "execution_id": "session_123"
}
```

### 2. List Tools
**GET** `/vscode/tools`

Get information about all available tools.

**Response:**
```json
{
  "tools_count": 8,
  "tools": [
    {
      "name": "read_file",
      "description": "Read the contents of a file...",
      "args_schema": "..."
    }
  ]
}
```

### 3. Clear Execution Memory
**DELETE** `/vscode/memory/{execution_id}`

Clear conversation memory for a specific execution session.

**Response:**
```json
{
  "message": "Memory cleared for execution session_123"
}
```

### 4. Clear All Memory
**DELETE** `/vscode/memory`

Clear all execution session memories.

**Response:**
```json
{
  "message": "All VS Code execution memories cleared"
}
```

## Usage Examples

### Direct Usage (Python)

```python
from vscode_agent_service import vscode_agent_service
import asyncio

async def main():
    # Execute a simple task
    response = await vscode_agent_service.execute_task(
        user_query="List all Python files in the current directory",
        execution_id="my_session"
    )
    print(response)
    
    # Follow-up query with context
    response = await vscode_agent_service.execute_task(
        user_query="Read the first Python file you found",
        execution_id="my_session"  # Same session maintains context
    )
    print(response)
    
    # Clear memory when done
    vscode_agent_service.clear_execution_memory("my_session")

asyncio.run(main())
```

### API Usage (cURL)

```bash
# Execute a task
curl -X POST http://localhost:8000/vscode/execute \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Create a file called hello.py with a hello world function",
    "execution_id": "curl_session"
  }'

# List available tools
curl http://localhost:8000/vscode/tools

# Clear session memory
curl -X DELETE http://localhost:8000/vscode/memory/curl_session
```

### API Usage (Python with httpx)

```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        # Execute task
        response = await client.post(
            "http://localhost:8000/vscode/execute",
            json={
                "query": "List all files in the services directory",
                "execution_id": "api_session"
            }
        )
        result = response.json()
        print(f"Response: {result['response']}")
        
        # Clear memory
        await client.delete(
            "http://localhost:8000/vscode/memory/api_session"
        )

asyncio.run(main())
```

## Configuration

The VS Code agent uses the same Azure OpenAI configuration as the main agent service. Ensure these environment variables are set in your `.env` file:

```env
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
```

## Memory Management

The VS Code agent maintains conversation memory per execution session:

- **Execution ID**: Each task execution can have an optional `execution_id`
- **Context Retention**: Tasks with the same `execution_id` share conversation history
- **Memory Window**: Keeps the last 10 messages per session
- **Memory Cleanup**: Use the DELETE endpoints to clear memory when done

## Tool Output Format

All tools return JSON in a standardized format:

```json
{
  "tool": "tool_name",
  "parameter1": "value1",
  "parameter2": "value2"
}
```

This JSON is meant to be interpreted by a VS Code extension or other client that can execute the actual file operations.

## Error Handling

The service includes comprehensive error handling:

- Invalid requests return HTTP 400
- Server errors return HTTP 500 with error details
- Tool execution errors are logged and returned in the response
- Connection errors are handled gracefully

## Best Practices

1. **Use Execution IDs**: Always provide an `execution_id` for tasks that need context
2. **Clear Memory**: Clear session memory when conversations are complete
3. **Handle Tool Output**: The agent returns JSON tool calls that need to be executed by your client
4. **Monitor Logs**: Check logs for detailed agent behavior and debugging
5. **Iterate Tasks**: For complex tasks, break them into smaller steps

## Differences from Main Agent

| Feature | Main Agent (agent_service.py) | VS Code Agent (vscode_agent_service.py) |
|---------|-------------------------------|----------------------------------------|
| Purpose | Chat with MCP tools | File operations and coding tasks |
| Tools | MCP server tools | Built-in file operation tools |
| API Endpoint | `/chat` | `/vscode/execute` |
| Memory | User/Chat based | Execution ID based |
| Integration | MCP server required | Standalone |

## Testing

Run the example script to test the VS Code agent:

```bash
# Start the server
python main.py

# In another terminal, run examples
python vscode_agent_example.py
```

## Troubleshooting

### Issue: "Error connecting to API"
**Solution**: Ensure the FastAPI server is running on port 8000

### Issue: "Agent not using tools"
**Solution**: Check that the LLM supports function/tool calling (Azure OpenAI does)

### Issue: "Memory not persisting"
**Solution**: Use the same `execution_id` for related tasks

### Issue: "Tool output not executing"
**Solution**: The tools return JSON instructions that need to be executed by your client application

## Future Enhancements

Potential improvements for the VS Code agent:

- Browser automation support
- Git operations (commit, push, pull)
- Code analysis and refactoring
- Test generation
- Documentation generation
- Integration with actual VS Code extension API

## Contributing

To add new tools:

1. Define a new tool using the `@tool` decorator
2. Add the tool to the `self.tools` list in `VSCodeAgentService.__init__`
3. Update this documentation
4. Add tests in the example script

## License

This component is part of the python-agent-service project.
