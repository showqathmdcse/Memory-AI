"""
LangChain Agent for VS Code/IDE Extension
Professional implementation using StructuredTool with Pydantic schemas
Enhanced with DeepAgents (LangGraph) and real-time streaming
"""

import logging
import json
from typing import Dict, Optional, List
from pydantic import BaseModel, Field

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain.tools import StructuredTool
from langchain_openai import AzureChatOpenAI
from langchain.memory import ConversationBufferWindowMemory

# DeepAgents imports for advanced reasoning
try:
    from langgraph.prebuilt import create_react_agent
    from langgraph.checkpoint.memory import MemorySaver
    DEEPAGENTS_AVAILABLE = True
except ImportError:
    DEEPAGENTS_AVAILABLE = False
    logging.warning("DeepAgents (langgraph) not available for VSCode agent. Using standard agent mode.")

from config import settings
from nats_producer import stream_producer
from streaming_callbacks import ToolCallStreamingCallback

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Schemas for Tool Input Validation
# ============================================================================

class ReadFileInput(BaseModel):
    """Input schema for read_file tool"""
    path: str = Field(description="The relative path to the file from workspace root")


class WriteFileInput(BaseModel):
    """Input schema for write_to_file tool"""
    path: str = Field(description="The relative path to the file")
    content: str = Field(description="The complete content to write to the file")


class ReplaceInFileInput(BaseModel):
    """Input schema for replace_in_file tool"""
    path: str = Field(description="The relative path to the file")
    diff: str = Field(description="SEARCH/REPLACE blocks in the format:\n"
                     "------- SEARCH\n[exact content to find]\n=======\n"
                     "[new content to replace with]\n+++++++ REPLACE")


class ListFilesInput(BaseModel):
    """Input schema for list_files tool"""
    path: str = Field(description="The directory path to list")
    recursive: bool = Field(default=False, description="Whether to list files recursively")


class SearchFilesInput(BaseModel):
    """Input schema for search_files tool"""
    path: str = Field(description="The directory path to search in")
    regex: str = Field(description="The regex pattern to search for")
    file_pattern: Optional[str] = Field(default=None, description="Optional glob pattern to filter files (e.g., '*.ts', '*.py')")


class ExecuteCommandInput(BaseModel):
    """Input schema for execute_command tool"""
    command: str = Field(description="The shell command to execute")
    requires_approval: bool = Field(default=False, description="Whether this command requires user approval")


class AskFollowupQuestionInput(BaseModel):
    """Input schema for ask_followup_question tool"""
    question: str = Field(description="The question to ask the user")
    options: Optional[List[str]] = Field(default=None, description="Optional list of choices for the user")


class AttemptCompletionInput(BaseModel):
    """Input schema for attempt_completion tool"""
    result: str = Field(description="The final result message to present to the user")
    command: Optional[str] = Field(default=None, description="Optional command to suggest running")


# ============================================================================
# Tool Implementation Functions (Return JSON for IDE Execution)
# ============================================================================

def read_file_func(path: str) -> str:
    """Read the contents of a file in the user's workspace.
    
    This returns a JSON command that the IDE will execute.
    """
    return json.dumps({
        "tool": "read_file",
        "path": path
    })


def write_to_file_func(path: str, content: str) -> str:
    """Write content to a file (creates or overwrites).
    
    This returns a JSON command that the IDE will execute.
    """
    return json.dumps({
        "tool": "write_to_file",
        "path": path,
        "content": content
    })


def replace_in_file_func(path: str, diff: str) -> str:
    """Replace content in a file using SEARCH/REPLACE blocks.
    
    This returns a JSON command that the IDE will execute.
    """
    return json.dumps({
        "tool": "replace_in_file",
        "path": path,
        "diff": diff
    })


def list_files_func(path: str, recursive: bool = False) -> str:
    """List files in a directory.
    
    This returns a JSON command that the IDE will execute.
    """
    return json.dumps({
        "tool": "list_files",
        "path": path,
        "recursive": recursive
    })


def search_files_func(path: str, regex: str, file_pattern: Optional[str] = None) -> str:
    """Search for text in files using regex.
    
    This returns a JSON command that the IDE will execute.
    """
    tool_data = {
        "tool": "search_files",
        "path": path,
        "regex": regex
    }
    if file_pattern:
        tool_data["file_pattern"] = file_pattern
    return json.dumps(tool_data)


def execute_command_func(command: str, requires_approval: bool = False) -> str:
    """Execute a shell command.
    
    This returns a JSON command that the IDE will execute.
    """
    return json.dumps({
        "tool": "execute_command",
        "command": command,
        "requires_approval": requires_approval
    })


def ask_followup_question_func(question: str, options: Optional[List[str]] = None) -> str:
    """Ask the user a question.
    
    This returns a JSON command that the IDE will execute.
    """
    tool_data = {
        "tool": "ask_followup_question",
        "question": question
    }
    if options:
        tool_data["options"] = options
    return json.dumps(tool_data)


def attempt_completion_func(result: str, command: Optional[str] = None) -> str:
    """Complete the task and present the result.
    
    This returns a JSON command that the IDE will execute.
    """
    tool_data = {
        "tool": "attempt_completion",
        "result": result
    }
    if command:
        tool_data["command"] = command
    return json.dumps(tool_data)


# ============================================================================
# Create LangChain StructuredTools
# ============================================================================

def create_vscode_tools() -> List[StructuredTool]:
    """Create all VS Code/IDE tools with proper schemas."""
    
    tools = [
        StructuredTool.from_function(
            func=read_file_func,
            name="read_file",
            description="Read the contents of a file in the user's workspace. Returns a JSON command that the IDE will execute.",
            args_schema=ReadFileInput
        ),
        StructuredTool.from_function(
            func=write_to_file_func,
            name="write_to_file",
            description="Write content to a file (creates or overwrites). Returns a JSON command that the IDE will execute.",
            args_schema=WriteFileInput
        ),
        StructuredTool.from_function(
            func=replace_in_file_func,
            name="replace_in_file",
            description="Replace content in a file using SEARCH/REPLACE blocks. Returns a JSON command that the IDE will execute.",
            args_schema=ReplaceInFileInput
        ),
        StructuredTool.from_function(
            func=list_files_func,
            name="list_files",
            description="List files in a directory. Returns a JSON command that the IDE will execute.",
            args_schema=ListFilesInput
        ),
        StructuredTool.from_function(
            func=search_files_func,
            name="search_files",
            description="Search for text in files using regex. Returns a JSON command that the IDE will execute.",
            args_schema=SearchFilesInput
        ),
        StructuredTool.from_function(
            func=execute_command_func,
            name="execute_command",
            description="Execute a shell command. Returns a JSON command that the IDE will execute.",
            args_schema=ExecuteCommandInput
        ),
        StructuredTool.from_function(
            func=ask_followup_question_func,
            name="ask_followup_question",
            description="Ask the user a question. Returns a JSON command that the IDE will execute.",
            args_schema=AskFollowupQuestionInput
        ),
        StructuredTool.from_function(
            func=attempt_completion_func,
            name="attempt_completion",
            description="Complete the task and present the final result to the user. Returns a JSON command that the IDE will execute.",
            args_schema=AttemptCompletionInput
        ),
    ]
    
    return tools


# ============================================================================
# VS Code Agent Service Class
# ============================================================================

class VSCodeAgentService:
    """
    Professional LangChain agent service for VS Code/IDE integration.
    
    Uses StructuredTool with Pydantic schemas for type-safe tool definitions.
    Maintains conversation history per user_id + chat_id session.
    Returns JSON commands for the IDE to execute.
    """
    
    def __init__(self):
        """Initialize the VS Code agent service."""
        # Initialize Azure OpenAI LLM
        self.llm = AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            deployment_name=settings.azure_openai_deployment,
            temperature=0,  # Use 0 for more deterministic tool calling
        )
        
        # Create all tools with Pydantic schemas
        self.tools = create_vscode_tools()
        
        # In-memory storage for conversation history (session_id -> memory)
        self._memory_store: Dict[str, ConversationBufferWindowMemory] = {}
        
        logger.info(f"VSCodeAgentService initialized with {len(self.tools)} structured tools")
    
    def _get_or_create_memory(self, session_id: str) -> ConversationBufferWindowMemory:
        """
        Get or create memory for a session.
        
        Args:
            session_id: Unique session identifier (user_id_chat_id)
            
        Returns:
            ConversationBufferWindowMemory instance
        """
        if session_id not in self._memory_store:
            self._memory_store[session_id] = ConversationBufferWindowMemory(
                k=10,  # Keep last 10 messages
                return_messages=True,
                memory_key="chat_history"
            )
            logger.info(f"Created new memory for session: {session_id}")
        
        return self._memory_store[session_id]
    
    def _get_max_iterations(self, query: str) -> int:
        """
        Determine max iterations based on query complexity.
        
        This allows complex multi-step tasks while still preventing infinite loops.
        
        Args:
            query: The user's query string
            
        Returns:
            Maximum number of iterations (10-25)
        """
        query_lower = query.lower()
        
        # Tool result processing - usually needs several iterations
        if query.startswith("TOOL EXECUTION RESULT:"):
            logger.debug("Tool result query detected, max_iterations=10")
            return 10
        
        # Explanation/analysis tasks need many steps
        # Example: read_file → analyze → read related files → attempt_completion
        explanation_keywords = ["explain", "describe", "what is", "tell me about", "how does", "analyze", "review"]
        if any(keyword in query_lower for keyword in explanation_keywords):
            logger.debug("Explanation query detected, max_iterations=25")
            return 25
        
        # Complex search tasks need many steps
        # Example: search_files → read multiple files → analyze → attempt_completion
        search_keywords = ["find", "search", "locate", "investigate", "look for"]
        if any(keyword in query_lower for keyword in search_keywords):
            logger.debug("Complex search query detected, max_iterations=25")
            return 25
        
        # Simple read/display tasks
        # Example: read_file → attempt_completion
        simple_keywords = ["read", "show", "display", "get", "fetch", "view"]
        if any(keyword in query_lower for keyword in simple_keywords):
            logger.debug("Simple query detected, max_iterations=10")
            return 10
        
        # Default: allow 15 iterations for most tasks
        logger.debug("Default max_iterations=15")
        return 15
    
    async def execute_task(self, user_query: str, user_id: str = None, chat_id: str = None, enable_streaming: bool = False) -> str:
        """
        Execute a task with the VS Code agent with optional streaming support.
        
        Args:
            user_query: The user's request
            user_id: User identifier
            chat_id: Chat/conversation identifier
            enable_streaming: Whether to enable real-time streaming to NATS
            
        Returns:
            Agent's response (either a message or tool call JSON)
        """
        try:
            logger.info(f"Processing VS Code task: {user_query[:100]}... (streaming={enable_streaming})")
            
            # Create session key from user_id and chat_id
            user_id = user_id or "default_user"
            chat_id = chat_id or "default_chat"
            session_id = f"{user_id}_{chat_id}"
            
            # Stream start message to NATS if enabled
            if enable_streaming and stream_producer.enabled and stream_producer._initialized:
                await stream_producer.stream_agent_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_type="start",
                    content={"message": user_query, "service": "vscode_agent"}
                )
            
            memory = self._get_or_create_memory(session_id)
            
            # Load chat history
            memory_vars = memory.load_memory_variables({})
            chat_history = memory_vars.get("chat_history", [])
            
            # Create enhanced system prompt for IDE integration
            # Note: Double curly braces escape them in ChatPromptTemplate
            system_message = """You are an expert coding assistant integrated into an IDE (VS Code, IntelliJ, etc.).

🔧 CRITICAL: YOU MUST USE TOOLS, NOT RETURN CODE IN CHAT!

❌ WRONG (returning code in chat):
User: "optimize UserService class"
You: "Here's the optimized code: public class UserService {{...}}"

✅ CORRECT (using tools):
User: "optimize UserService class"
You: Call read_file("UserService.java")
[Wait for file contents]
You: Call replace_in_file("UserService.java", diff="...")
You: Call attempt_completion("Optimized UserService by...")

🎯 MANDATORY BEHAVIOR:
1. NEVER return code blocks in your response
2. ALWAYS use tools to modify files
3. When asked to create/modify/optimize code:
   - Step 1: read_file (if modifying existing)
   - Step 2: write_to_file OR replace_in_file
   - Step 3: attempt_completion

📝 TOOL WORKFLOW:
- When you call a tool, it returns JSON like: {{"tool": "read_file", "path": "..."}}
- This JSON is a COMMAND for the IDE to execute
- After you return a tool call, the conversation ENDS temporarily
- The IDE executes the tool in the user's workspace
- The IDE sends you a NEW message starting with "TOOL EXECUTION RESULT:"
- That new message contains the ACTUAL file contents or execution result
- You then analyze that REAL result and decide the next action

💡 EXAMPLES OF CORRECT BEHAVIOR:

Example 1: Optimize existing class
User: "optimize the AdminService class"
You: read_file("src/AdminService.java")
[Receive file contents in next message]
You: replace_in_file("src/AdminService.java", diff="------- SEARCH\\n[old code]\\n=======\\n[new code]\\n+++++++ REPLACE")
You: attempt_completion("Optimized AdminService by adding caching and improving error handling")

Example 2: Create new class
User: "create a UserDTO class"
You: write_to_file("src/dto/UserDTO.java", content="package com.example.dto;\\n\\npublic class UserDTO {{\\n    private String name;\\n    private String email;\\n}}")
You: attempt_completion("Created UserDTO class with name and email fields")

Example 3: Add feature to existing code
User: "add logging to the processPayment method"
You: read_file("src/PaymentService.java")
[Receive file contents]
You: replace_in_file("src/PaymentService.java", diff="------- SEARCH\\npublic void processPayment() {{\\n=======\\npublic void processPayment() {{\\n    logger.info(\\"Processing payment\\");\\n+++++++ REPLACE")
You: attempt_completion("Added logging to processPayment method")

⚠️ CRITICAL RULES:
- If a message starts with "TOOL EXECUTION RESULT:", analyze that result and decide next action
- Do NOT call the same tool repeatedly
- Do NOT return code in your response - use write_to_file or replace_in_file
- ALWAYS use attempt_completion when the task is finished
- Be direct and technical - avoid phrases like "Great", "Certainly", "Okay"

📋 Available Tools:
- read_file: Read file contents (use before modifying)
- write_to_file: Create or overwrite entire file
- replace_in_file: Make targeted edits using SEARCH/REPLACE blocks
- list_files: List directory contents
- search_files: Search for patterns in files
- execute_command: Run shell commands
- ask_followup_question: Ask user for clarification
- attempt_completion: Complete the task and present final result

🎯 Remember:
- Read files BEFORE modifying them
- Use replace_in_file for existing files (surgical edits)
- Use write_to_file for new files or complete rewrites
- NEVER return code in chat - always use tools to modify workspace files"""
            
            # Create prompt template
            prompt_messages = [("system", system_message)]
            
            # Add chat history if available
            if chat_history:
                prompt_messages.append(MessagesPlaceholder(variable_name="chat_history"))
            
            prompt_messages.extend([
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            
            prompt = ChatPromptTemplate.from_messages(prompt_messages)
            
            # Create OpenAI tools agent (recommended for structured tools)
            agent = create_openai_tools_agent(self.llm, self.tools, prompt)
            
            # Create streaming callback for capturing all tool calls
            streaming_callback = ToolCallStreamingCallback(
                user_id=user_id,
                chat_id=chat_id,
                enabled=enable_streaming
            )
            
            # Create agent executor with max_iterations=1
            # CRITICAL: Agent must return ONE tool call at a time
            # VS Code executes the tool, then sends result back for next iteration
            agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=1,  # ONE tool per request - VS Code handles the iteration loop
                early_stopping_method="force",  # Stop gracefully at max iterations
                return_intermediate_steps=True,  # Useful for debugging
                callbacks=[streaming_callback] if enable_streaming else None,
            )
            
            # Execute agent with optional DeepAgents support
            if DEEPAGENTS_AVAILABLE and not user_query.startswith("TOOL EXECUTION RESULT:"):
                # Use DeepAgents for initial requests (better reasoning)
                result = await self._execute_with_deepagents(
                    session_id, system_message, user_query, chat_history, user_id, chat_id, enable_streaming
                )
                
                # Save to memory
                memory.save_context(
                    {"input": user_query},
                    {"output": result}
                )
                
                # Stream end message
                if enable_streaming and stream_producer.enabled and stream_producer._initialized:
                    await stream_producer.stream_agent_message(
                        user_id=user_id,
                        chat_id=chat_id,
                        message_type="end",
                        content={"status": "completed", "result": result}
                    )
                
                return result
            
            # Standard execution (tool results or fallback)
            invoke_input = {"input": user_query}
            if chat_history:
                invoke_input["chat_history"] = chat_history
            
            result = await agent_executor.ainvoke(invoke_input)
            
            # Extract the tool call JSON from intermediate steps
            # This is CRITICAL: Return the FIRST tool JSON only!
            if "intermediate_steps" in result and len(result["intermediate_steps"]) > 0:
                # Get the FIRST tool call (not the last!)
                # This ensures we return ONE tool at a time
                first_action, first_tool_output = result["intermediate_steps"][0]
                
                # CRITICAL: Sometimes multiple tools are concatenated
                # Parse and return ONLY the first JSON object
                try:
                    # Try to find the end of the first JSON object
                    # Count braces to find where first JSON ends
                    brace_count = 0
                    in_string = False
                    escape_next = False
                    first_json_end = -1
                    
                    for i, char in enumerate(first_tool_output):
                        if escape_next:
                            escape_next = False
                            continue
                        if char == '\\':
                            escape_next = True
                            continue
                        if char == '"':
                            in_string = not in_string
                        elif not in_string:
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    first_json_end = i + 1
                                    break
                    
                    if first_json_end > 0 and first_json_end < len(first_tool_output):
                        first_tool_output = first_tool_output[:first_json_end]
                        logger.info("Extracted FIRST JSON object from multiple tool calls")
                except Exception as e:
                    logger.warning(f"Could not parse JSON to extract first: {e}")
                
                logger.info(f"Returning FIRST tool JSON: {first_tool_output[:200]}...")
                
                # Stream tool decision if enabled
                if enable_streaming and stream_producer.enabled and stream_producer._initialized:
                    await stream_producer.stream_agent_message(
                        user_id=user_id,
                        chat_id=chat_id,
                        message_type="tool_call",
                        content={"tool_json": first_tool_output}
                    )
                
                # Save to memory
                memory.save_context(
                    {"input": user_query},
                    {"output": first_tool_output}
                )
                
                # Stream end message
                if enable_streaming and stream_producer.enabled and stream_producer._initialized:
                    await stream_producer.stream_agent_message(
                        user_id=user_id,
                        chat_id=chat_id,
                        message_type="end",
                        content={"status": "completed", "result": first_tool_output}
                    )
                
                logger.info(f"Task completed for session {session_id}")
                return first_tool_output  # Return the FIRST tool JSON only!
            
            # Fallback: If no intermediate steps, return the output
            output = result.get("output", "No response generated")
            
            # Stream response if it's not a tool call
            if enable_streaming and stream_producer.enabled and stream_producer._initialized:
                # Stream as chunks for progressive display
                chunk_size = 50
                for i in range(0, len(output), chunk_size):
                    chunk = output[i:i+chunk_size]
                    await stream_producer.stream_agent_message(
                        user_id=user_id,
                        chat_id=chat_id,
                        message_type="chunk",
                        content={"chunk": chunk, "accumulated": output[:i+len(chunk)]}
                    )
            
            memory.save_context(
                {"input": user_query},
                {"output": output}
            )
            
            # Stream end message
            if enable_streaming and stream_producer.enabled and stream_producer._initialized:
                await stream_producer.stream_agent_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_type="end",
                    content={"status": "completed", "result": output}
                )
            
            logger.info(f"Task completed for session {session_id}")
            return output
            
        except Exception as e:
            logger.error(f"Error executing VS Code task: {e}", exc_info=True)
            raise
    
    async def _execute_with_deepagents(
        self,
        session_id: str,
        system_message: str,
        user_query: str,
        chat_history: list,
        user_id: str,
        chat_id: str,
        enable_streaming: bool = False
    ) -> str:
        """
        Execute using LangGraph's ReAct agent for advanced reasoning (VSCode version).
        
        CRITICAL: For IDE integration, this returns tool JSON commands (not executed results)
        so the IDE can execute tools in the user's workspace.
        
        Args:
            session_id: Session identifier
            system_message: System prompt
            user_query: User's request
            chat_history: Previous messages
            user_id: User identifier for streaming
            chat_id: Chat identifier for streaming
            enable_streaming: Whether to stream responses
            
        Returns:
            Tool JSON command for IDE to execute (e.g. {"tool": "write_to_file", ...})
        """
        logger.info("Using DeepAgents (LangGraph) for VSCode task with streaming support")
        
        # Prepare messages
        messages = []
        messages.append(SystemMessage(content=system_message))
        
        if chat_history:
            messages.extend(chat_history)
        
        messages.append(HumanMessage(content=user_query))
        
        # Create ReAct agent with memory
        memory = MemorySaver()
        agent_executor = create_react_agent(
            model=self.llm,
            tools=self.tools,
            checkpointer=memory
        )
        
        config = {"configurable": {"thread_id": session_id}}
        
        # Track tool calls for streaming
        tool_call_sequence = 0
        final_result = None
        
        # Use LangGraph's streaming to capture tool calls
        try:
            if enable_streaming and stream_producer.enabled and stream_producer._initialized:
                # Stream events as they happen
                async for event in agent_executor.astream_events(
                    {"messages": messages},
                    config=config,
                    version="v1"
                ):
                    # Stream tool call events
                    if event["event"] == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk", {})
                        if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                            for tool_call in chunk.tool_calls:
                                tool_name = tool_call.get('name')
                                tool_args = tool_call.get('args', {})
                                
                                if tool_name:
                                    tool_call_sequence += 1
                                    tool_json = json.dumps({
                                        "tool": tool_name,
                                        **tool_args
                                    })
                                    
                                    logger.info(f"DeepAgents tool call #{tool_call_sequence}: {tool_name}")
                                    
                                    # Stream the tool call
                                    await stream_producer.stream_agent_message(
                                        user_id=user_id,
                                        chat_id=chat_id,
                                        message_type="tool_call",
                                        content={
                                            "tool_name": tool_name,
                                            "tool_input": tool_args,
                                            "tool_json": tool_json,
                                            "sequence": tool_call_sequence,
                                            "source": "deepagents"
                                        }
                                    )
                
                # Now get the final result
                result = await agent_executor.ainvoke(
                    {"messages": messages},
                    config=config
                )
            else:
                # No streaming, just execute
                result = await agent_executor.ainvoke(
                    {"messages": messages},
                    config=config
                )
            
            # Extract tool call from result
            if "messages" in result and result["messages"]:
                # Look through messages for tool calls
                for msg in reversed(result["messages"]):
                    # Check for tool calls (DeepAgents format)
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        tool_call = msg.tool_calls[0]
                        
                        # Convert to our tool JSON format
                        tool_name = tool_call.get('name', 'unknown')
                        tool_args = tool_call.get('args', {})
                        
                        # Build tool JSON that IDE expects
                        tool_json = json.dumps({
                            "tool": tool_name,
                            **tool_args
                        })
                        
                        logger.info(f"DeepAgents selected tool: {tool_name}")
                        
                        # Stream tool decision if enabled
                        if enable_streaming and stream_producer.enabled and stream_producer._initialized:
                            await stream_producer.stream_agent_message(
                                user_id=user_id,
                                chat_id=chat_id,
                                message_type="tool_call",
                                content={"tool_json": tool_json, "reasoning": "DeepAgents intelligent analysis"}
                            )
                        
                        return tool_json
                    
                    # Check for AIMessage with content (non-tool response)
                    if hasattr(msg, 'content') and msg.content and not hasattr(msg, 'tool_calls'):
                        response = msg.content
                        
                        # Stream response chunks if enabled
                        if enable_streaming and stream_producer.enabled and stream_producer._initialized:
                            chunk_size = 50
                            for i in range(0, len(response), chunk_size):
                                chunk = response[i:i+chunk_size]
                                await stream_producer.stream_agent_message(
                                    user_id=user_id,
                                    chat_id=chat_id,
                                    message_type="chunk",
                                    content={"chunk": chunk, "accumulated": response[:i+len(chunk)]}
                                )
                        
                        return response
            
            # Fallback: no tool calls or messages found
            logger.warning("DeepAgents did not return tool calls or messages")
            return "I need more information to proceed with this task."
            
        except Exception as e:
            logger.error(f"DeepAgents execution error: {e}", exc_info=True)
            # Fall back to standard agent if DeepAgents fails
            logger.info("Falling back to standard agent")
            raise
    
    def clear_session_memory(self, user_id: str, chat_id: str):
        """
        Clear memory for a specific session.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
        """
        session_id = f"{user_id}_{chat_id}"
        if session_id in self._memory_store:
            del self._memory_store[session_id]
            logger.info(f"Cleared memory for session: {session_id}")
    
    def clear_all_memory(self):
        """Clear all session memories."""
        self._memory_store.clear()
        logger.info("Cleared all session memories")


# Global VS Code agent service instance
vscode_agent_service = VSCodeAgentService()
