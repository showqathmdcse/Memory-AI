"""
FastAPI application for chat agent with MCP tools integration.

This is the Python equivalent of the Spring Boot application.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent_service import agent_service
from vscode_agent_service import vscode_agent_service
from services.chroma_service import chroma_service
from config import settings
from nats_producer import stream_producer
from nats_config import nats_settings

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """Chat request model matching Java ChatController."""
    user_id: str
    chat_id: str
    message: str
    authorization: str = ""


class ChatResponse(BaseModel):
    """Chat response model."""
    reply: str


class VSCodeTaskRequest(BaseModel):
    """VS Code task request model."""
    query: str
    user_id: str
    chat_id: str
    workspace_context: dict = None
    enable_streaming: bool = False  # Enable real-time streaming to NATS


class VSCodeTaskResponse(BaseModel):
    """VS Code task response model."""
    response: str
    user_id: str
    chat_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown."""
    logger.info("Starting up application...")
    logger.info(f"NATS streaming: {'ENABLED' if nats_settings.streaming_enabled else 'DISABLED'}")
    
    # Initialize NATS if enabled
    if nats_settings.streaming_enabled:
        try:
            await stream_producer.initialize()
        except Exception as e:
            logger.warning(f"Failed to initialize NATS: {e}. Continuing without streaming.")
    
    yield
    
    logger.info("Shutting down application...")
    # Cleanup resources
    await chroma_service.close()
    
    # Close NATS connection if enabled
    if nats_settings.streaming_enabled:
        await stream_producer.close()


# Create FastAPI app
app = FastAPI(
    title="Agent Chat API",
    description="Chat agent with LLM, embeddings, and MCP tools",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Agent Chat API",
        "status": "running",
        "mcp_enabled": settings.mcp_enabled,
        "mcp_server_url": settings.mcp_server_url,
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - Python equivalent of Java ChatController.post().
    
    Args:
        request: Chat request with user_id, chat_id, message, and authorization
        
    Returns:
        Chat response with reply
    """
    try:
        logger.info(f"Received chat request from user {request.user_id}")
        
        reply = await agent_service.chat(
            user_id=request.user_id,
            chat_id=request.chat_id,
            message=request.message,
            authorization=request.authorization,
        )
        
        return ChatResponse(reply=reply)
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vscode/execute", response_model=VSCodeTaskResponse)
async def vscode_execute(request: VSCodeTaskRequest):
    """
    VS Code agent execution endpoint.
    
    Executes tasks using the LangChain VS Code agent with file operation tools.
    
    Flow:
    1. If query starts with "TOOL EXECUTION RESULT:", agent analyzes the result
    2. Otherwise, agent processes the user's request
    3. Agent returns ONE tool call (max_iterations=1) or final answer
    4. Response goes back to VS Code extension for execution
    
    Args:
        request: Task request with query, user_id, chat_id, and optional workspace_context
        
    Returns:
        Task response with agent output (JSON tool command or completion message)
    """
    try:
        # Log the request
        query_preview = request.query[:100] if len(request.query) > 100 else request.query
        logger.info(f"VS Code task from user {request.user_id}, chat {request.chat_id}: {query_preview}...")
        
        # Format workspace context if provided and not a tool result
        workspace_info = ""
        if request.workspace_context and not request.query.startswith("TOOL EXECUTION RESULT:"):
            ws = request.workspace_context
            workspace_info = f"""

=== WORKSPACE CONTEXT ===
Workspace Root: {ws.get('workspaceRoot', 'N/A')}
Current File: {ws.get('currentFile', 'None')}

Files in workspace:
{ws.get('workspaceStructure', 'No structure provided')}
"""
            # Append workspace context to query if not already a tool result
            query_with_context = request.query + workspace_info
        else:
            query_with_context = request.query
        
        # Execute the agent with optional streaming
        response = await vscode_agent_service.execute_task(
            user_query=query_with_context,
            user_id=request.user_id,
            chat_id=request.chat_id,
            enable_streaming=request.enable_streaming,
        )
        
        logger.info(f"VS Code task completed. Response length: {len(response)} chars")
        
        return VSCodeTaskResponse(
            response=response,
            user_id=request.user_id,
            chat_id=request.chat_id
        )
        
    except Exception as e:
        logger.error(f"Error executing VS Code task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/vscode/memory/{user_id}/{chat_id}")
async def vscode_clear_memory(user_id: str, chat_id: str):
    """
    Clear memory for a specific VS Code session.
    
    Args:
        user_id: User identifier
        chat_id: Chat identifier
        
    Returns:
        Success message
    """
    try:
        vscode_agent_service.clear_session_memory(user_id, chat_id)
        return {"message": f"Memory cleared for user {user_id}, chat {chat_id}"}
    except Exception as e:
        logger.error(f"Error clearing memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/vscode/memory")
async def vscode_clear_all_memory():
    """
    Clear all VS Code session memories.
    
    Returns:
        Success message
    """
    try:
        vscode_agent_service.clear_all_memory()
        return {"message": "All VS Code session memories cleared"}
    except Exception as e:
        logger.error(f"Error clearing all memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/vscode/tools")
async def vscode_list_tools():
    """
    List all available VS Code agent tools.
    
    Returns:
        List of available tools with descriptions
    """
    try:
        tools_info = []
        for tool in vscode_agent_service.tools:
            tools_info.append({
                "name": tool.name,
                "description": tool.description,
                "args_schema": str(tool.args_schema.schema()) if hasattr(tool, 'args_schema') else None
            })
        
        return {
            "tools_count": len(tools_info),
            "tools": tools_info
        }
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
