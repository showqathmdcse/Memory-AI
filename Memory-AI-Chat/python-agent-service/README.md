# Python Agent Service

A FastAPI-based chat agent service with LangChain, embeddings, and multiple agent implementations.

## Features

### Main Chat Agent (`agent_service.py`)
- Multi-provider LLM support (Azure OpenAI, AWS Bedrock, Google Gemini)
- MCP (Model Context Protocol) tool integration
- Conversation memory with ChromaDB or LangChain memory
- Semantic search for chat history
- Tool execution with context retention

### VS Code LangChain Agent (`vscode_agent_service.py`) ✨ NEW
- Separate LangChain agent for file operations
- VS Code extension-style tools:
  - read_file
  - write_to_file
  - replace_in_file
  - list_files
  - search_files
  - execute_command
  - ask_followup_question
  - attempt_completion
- Independent API endpoints
- Conversation memory per execution session
- Returns JSON tool calls for client execution

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                        (main.py)                             │
├─────────────────────────────────────────────────────────────┤
│  Endpoints:                                                  │
│  - POST /chat                    (Main Agent)                │
│  - POST /vscode/execute          (VS Code Agent) ✨          │
│  - GET  /vscode/tools            (List Tools) ✨             │
│  - DELETE /vscode/memory/{id}    (Clear Memory) ✨           │
│  - DELETE /vscode/memory         (Clear All) ✨              │
└─────────────────────────────────────────────────────────────┘
           │                                  │
           │                                  │
           ▼                                  ▼
┌──────────────────────┐          ┌──────────────────────┐
│   Agent Service      │          │ VS Code Agent Service│
│ (agent_service.py)   │          │(vscode_agent_service.py)│
├──────────────────────┤          ├──────────────────────┤
│ - LangChain Agent    │          │ - LangChain Agent    │
│ - MCP Tools          │          │ - File Operation Tools│
│ - ChromaDB/Memory    │          │ - Conversation Memory│
└──────────────────────┘          └──────────────────────┘
```

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd python-agent-service
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=your-deployment-name

# Server Configuration
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# MCP Configuration (for main agent)
MCP_ENABLED=true
MCP_SERVER_URL=http://localhost:8080/mcp

# Chat History Storage
CHAT_HISTORY_STORAGE=langchain  # or 'chroma'
CHAT_HISTORY_WINDOW_SIZE=20
```

## Running the Service

Start the FastAPI server:
```bash
python3 main.py
```

The server will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Usage Examples

### Main Chat Agent

```python
import httpx
import asyncio

async def chat_example():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/chat",
            json={
                "user_id": "user123",
                "chat_id": "chat456",
                "message": "Hello, what tools do you have?",
                "authorization": "Bearer token"
            }
        )
        result = response.json()
        print(result['reply'])

asyncio.run(chat_example())
```

### VS Code Agent ✨

```python
import httpx
import asyncio

async def vscode_example():
    async with httpx.AsyncClient() as client:
        # Execute a task
        response = await client.post(
            "http://localhost:8000/vscode/execute",
            json={
                "query": "List all Python files in the current directory",
                "execution_id": "session_123"
            }
        )
        result = response.json()
        print(result['response'])
        
        # List available tools
        tools_response = await client.get(
            "http://localhost:8000/vscode/tools"
        )
        print(tools_response.json())

asyncio.run(vscode_example())
```

For more detailed examples, see `vscode_agent_example.py`

## Documentation

- [VS Code Agent Guide](VSCODE_AGENT_GUIDE.md) - Comprehensive guide for the VS Code agent
- [Chat History Guide](CHAT_HISTORY_GUIDE.md) - Memory and chat history management
- [Logging Guide](LOGGING_GUIDE.md) - Logging configuration

## Project Structure

```
python-agent-service/
├── main.py                      # FastAPI application
├── agent_service.py             # Main chat agent with MCP
├── vscode_agent_service.py      # VS Code file operations agent ✨
├── config.py                    # Configuration management
├── logging_callbacks.py         # Logging utilities
├── services/
│   ├── embedding_service.py     # Azure OpenAI embeddings
│   └── chroma_service.py        # ChromaDB operations
├── vscode_agent_example.py      # VS Code agent examples ✨
├── requirements.txt             # Python dependencies
├── .env                         # Environment variables
├── README.md                    # This file
├── VSCODE_AGENT_GUIDE.md        # VS Code agent documentation ✨
├── CHAT_HISTORY_GUIDE.md        # Chat history guide
└── LOGGING_GUIDE.md             # Logging guide
```

## Testing

Run the example scripts:

```bash
# Test VS Code agent
python3 vscode_agent_example.py

# Test main chat agent (requires MCP server)
# Start your MCP server first, then:
python3 -c "
import asyncio
from agent_service import agent_service

async def test():
    reply = await agent_service.chat(
        user_id='test_user',
        chat_id='test_chat',
        message='Hello!',
        authorization=''
    )
    print(reply)

asyncio.run(test())
"
```

## Key Differences Between Agents

| Feature | Main Agent | VS Code Agent |
|---------|-----------|---------------|
| **Purpose** | Chat with MCP tools | File operations and coding tasks |
| **Tools** | MCP server tools (dynamic) | Built-in file tools (8 tools) |
| **API Endpoint** | `/chat` | `/vscode/execute` |
| **Memory Key** | `user_id` + `chat_id` | `execution_id` |
| **Integration** | Requires MCP server | Standalone |
| **Use Case** | General chat with external tools | VS Code extension integration |

## Dependencies

Key dependencies:
- `fastapi` - Web framework
- `langchain` - LLM orchestration
- `langchain-openai` - Azure OpenAI integration
- `langchain-mcp-adapters` - MCP integration (main agent)
- `chromadb` - Vector database for embeddings
- `pydantic` - Data validation
- `uvicorn` - ASGI server

See `requirements.txt` for complete list.

## Configuration Options

### Chat History Storage

Choose between two storage backends:

**LangChain Memory (default):**
```env
CHAT_HISTORY_STORAGE=langchain
CHAT_HISTORY_WINDOW_SIZE=20
```
- In-memory storage
- Fast and simple
- Lost on restart

**ChromaDB:**
```env
CHAT_HISTORY_STORAGE=chroma
```
- Persistent storage
- Semantic search
- Survives restarts

### LLM Provider

Currently configured for Azure OpenAI. To use other providers:

1. **AWS Bedrock**: Use `langchain-aws`
2. **Google Gemini**: Use `langchain-google-genai`

Modify `agent_service.py` and `vscode_agent_service.py` to use the desired provider.

## Error Handling

Both agents include comprehensive error handling:
- Invalid requests return HTTP 400
- Server errors return HTTP 500 with details
- Tool execution errors are logged and returned
- Connection errors are handled gracefully

## Contributing

To add new functionality:

1. **New Tools for VS Code Agent:**
   - Define tool in `vscode_agent_service.py` using `@tool` decorator
   - Add to `self.tools` list
   - Update documentation

2. **New API Endpoints:**
   - Add endpoint to `main.py`
   - Update API documentation
   - Add examples

3. **Testing:**
   - Add test cases to example scripts
   - Ensure error handling works

## Troubleshooting

### Module Import Errors
```bash
# Ensure dependencies are installed
pip install -r requirements.txt
```

### MCP Connection Issues (Main Agent)
- Verify MCP server is running
- Check `MCP_SERVER_URL` in `.env`
- Set `MCP_ENABLED=false` to run without MCP

### VS Code Agent Not Using Tools
- Verify Azure OpenAI supports function calling
- Check logs for tool execution details
- Ensure tool descriptions are clear

### Memory Not Persisting
- For LangChain memory: Use same `execution_id`/`session_id`
- For ChromaDB: Check database connection and permissions

## License

[Add your license here]

## Support

For issues or questions:
- Check the documentation in the `/docs` directory
- Review example scripts
- Check server logs for detailed error messages

## Roadmap

Future enhancements:
- [ ] Additional LLM provider support
- [ ] Browser automation for VS Code agent
- [ ] Git operations tools
- [ ] Code analysis and refactoring tools
- [ ] Test generation capabilities
- [ ] WebSocket support for streaming responses
- [ ] Docker containerization
- [ ] Kubernetes deployment configs
