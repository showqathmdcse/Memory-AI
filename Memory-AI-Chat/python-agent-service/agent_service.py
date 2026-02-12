"""
Agent service with LLM orchestration, embeddings, and MCP tool integration.

Uses official langchain-mcp-adapters for seamless MCP integration with LangChain agents.
Supports multiple LLM providers: Azure OpenAI, AWS Bedrock, Google Gemini.
"""

import logging
from datetime import datetime
from typing import Dict, Optional
from uuid import uuid4
import warnings

# Suppress MCP JSON-RPC validation warnings (non-critical initialization messages)
logging.getLogger("mcp.client.streamable_http").setLevel(logging.CRITICAL)

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.agents import AgentStep
from langchain.memory import ConversationBufferWindowMemory
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import AzureChatOpenAI
import json
from typing import Dict, List, Any

# DeepAgents imports for advanced reasoning
try:
    from langgraph.prebuilt import create_react_agent
    from langgraph.checkpoint.memory import MemorySaver
    DEEPAGENTS_AVAILABLE = True
except ImportError:
    DEEPAGENTS_AVAILABLE = False
    logger.warning("DeepAgents (langgraph) not available. Using standard agent mode.")

from services.chroma_service import chroma_service
from services.embedding_service import embedding_service
from services.episodic_memory import episodic_memory_service, Episode
from config import settings
from logging_callbacks import get_logging_callback
from nats_producer import stream_producer
import re

logger = logging.getLogger(__name__)


class AgentService:
    """
    Agent service that orchestrates LLM calls with memory and MCP tools.
    
    Uses LangChain's official MCP adapters to connect to the Spring MCP server.
    Provides conversation memory via LangChain's built-in memory or ChromaDB.
    """
    
    def __init__(self):
        """Initialize the agent service."""
        # Initialize Azure OpenAI LLM (can be switched to AWS Bedrock or Google Gemini)
        self.llm = AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            deployment_name=settings.azure_openai_deployment,
            temperature=0.7,
        )
        
        # MCP configuration
        self.mcp_enabled = getattr(settings, 'mcp_enabled', True)
        self.mcp_server_url = getattr(settings, 'mcp_server_url', 'http://localhost:8080/mcp')
        self.mcp_client: Optional[MultiServerMCPClient] = None
        
        # Chat history configuration
        self.chat_history_storage = getattr(settings, 'chat_history_storage', 'langchain')
        self.chat_history_window_size = getattr(settings, 'chat_history_window_size', 20)
        
        # In-memory storage for LangChain memory (session_id -> memory)
        self._memory_store: Dict[str, ConversationBufferWindowMemory] = {}
    
    def _sanitize_collection_name(self, user_id: str, chat_id: str) -> str:
        """
        Create sanitized collection name for ChromaDB.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
            
        Returns:
            Sanitized collection name
        """
        sanitized_user = chroma_service._sanitize_collection_name(user_id)
        sanitized_chat = chroma_service._sanitize_collection_name(chat_id or "default")
        return f"conv_{sanitized_user}_{sanitized_chat}"
    
    async def _get_mcp_client(self, authorization: str = "") -> MultiServerMCPClient:
        """
        Get or create MCP client.
        
        Args:
            authorization: Authorization header value
            
        Returns:
            MCP client instance
        """
        if self.mcp_client is None:
            # Configure MCP server connection using official langchain-mcp-adapters
            mcp_config = {
                "spring-mcp": {
                    "transport": "streamable_http",  # HTTP-based connection to Spring MCP server
                    "url": self.mcp_server_url,
                    "headers": {"Authorization": authorization} if authorization else {},
                }
            }
            
            self.mcp_client = MultiServerMCPClient(mcp_config)
            logger.info(f"Initialized MCP client for server: {self.mcp_server_url}")
        
        return self.mcp_client
    
    async def chat(
        self, 
        user_id: str, 
        chat_id: str, 
        message: str,
        authorization: str = ""
    ) -> str:
        """
        Handle a chat message with memory, LLM, and MCP tool orchestration.
        
        Supports both LangChain's built-in memory (default) and ChromaDB storage.
        Streams LLM response chunks to NATS in real-time for progressive UI updates.
        
        Args:
            user_id: User identifier
            chat_id: Chat/conversation identifier  
            message: User message
            authorization: Authorization header for MCP server
            
        Returns:
            Assistant's response
        """
        session_id = f"{user_id}_{chat_id}"
        
        try:
            logger.info(f"Processing message for user {user_id}, chat {chat_id}, storage: {self.chat_history_storage}")
            
            # Stream start message to NATS
            if stream_producer.enabled and stream_producer._initialized:
                await stream_producer.stream_agent_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_type="start",
                    content={"message": message}
                )
            
            # EPISODIC MEMORY: Retrieve relevant past episodes
            relevant_episodes = await episodic_memory_service.retrieve_relevant_episodes(
                user_id=user_id,
                chat_id=chat_id,
                query=message,
                top_k=5,
                temporal_window_days=7,  # Last 7 days
                min_importance=0.3
            )
            
            # Get conversation history based on storage type
            if self.chat_history_storage == "langchain":
                chat_history = await self._get_langchain_history(session_id, message)
            else:  # chroma
                chat_history = await self._get_chroma_history(user_id, chat_id, message)
            
            # Build episodic context from relevant episodes
            episodic_context = ""
            if relevant_episodes:
                episodic_context = "\n\nRELEVANT PAST EPISODES (Episodic Memory):\n"
                for i, episode in enumerate(relevant_episodes, 1):
                    time_ago = self._format_time_ago(episode.timestamp)
                    episodic_context += f"\n{i}. [{time_ago}] {episode.topic or 'Conversation'}\n"
                    episodic_context += f"   User: {episode.user_message[:150]}...\n"
                    episodic_context += f"   Assistant: {episode.assistant_response[:150]}...\n"
                    if episode.entities:
                        episodic_context += f"   Key entities: {', '.join(episode.entities)}\n"
                
                logger.info(f"Retrieved {len(relevant_episodes)} episodic memories for context")
            
            # Build system prompt with context awareness and episodic memory
            system_message = (
                "You are an intelligent, conversational AI assistant with access to powerful tools and real-time information. "
                "Your role is to provide comprehensive, accurate, and helpful responses to all user queries.\n\n"
                
                "CAPABILITIES:\n"
                "- You have access to various tools that can fetch real-time information, search databases, and perform actions\n"
                "- You can use these tools to get current information about world events, news, weather, and any up-to-date data\n"
                "- When users ask about current events, recent news, or 'what's happening now', actively use available tools to retrieve this information\n"
                "- You maintain conversation history and context from previous messages and tool results\n\n"
                
                "RESPONSE GUIDELINES:\n"
                "- Provide complete, detailed responses that fully address the user's question\n"
                "- Be conversational, friendly, and natural in your communication style\n"
                "- When information is available from previous tool calls in the conversation history, reference and use it\n"
                "- For follow-up questions, extract parameters from previous tool results instead of asking again\n"
                "- If you need current information (news, events, real-time data), use available tools to fetch it\n"
                "- Synthesize information from multiple sources when needed to provide comprehensive answers\n"
                "- Always aim to give the most helpful, accurate, and complete response possible\n\n"
                
                "CONTEXT HANDLING:\n"
                "- Carefully analyze the conversation history before responding\n"
                "- Previous tool results contain structured data - extract and use relevant information from them\n"
                "- Maintain continuity across the conversation by referencing earlier context when relevant\n"
                "- If the user's question can be answered using data from previous tool calls, use that data\n"
                f"{episodic_context}\n"
                
                "Remember: Your goal is to be as helpful and informative as possible, providing complete answers "
                "and using all available resources to give the user the best possible response."
            )
            
            # Execute with LangChain agent and MCP tools (WITH STREAMING)
            if self.mcp_enabled:
                try:
                    # Get MCP client and tools
                    mcp_client = await self._get_mcp_client(authorization)
                    tools = await mcp_client.get_tools()
                    
                    # Sanitize tool descriptions to escape template variables
                    tools = self._sanitize_tools(tools)
                    
                    logger.info(f"Retrieved {len(tools)} tools from MCP server")
                    reply = await self._execute_with_tools_streaming(
                        session_id, system_message, message, tools, chat_history, user_id, chat_id
                    )
                except Exception as e:
                    # MCP server unavailable or error - continue without tools
                    logger.warning(f"MCP tools unavailable, continuing without tools: {e}")
                    reply = await self._execute_without_tools_streaming(
                        system_message, message, user_id, chat_id
                    )
            else:
                # Execute without tools (WITH STREAMING)
                reply = await self._execute_without_tools_streaming(
                    system_message, message, user_id, chat_id
                )
            
            # EPISODIC MEMORY: Store this conversation episode
            turn_number = len(chat_history) // 2 if chat_history else 0
            await episodic_memory_service.store_episode(
                user_id=user_id,
                chat_id=chat_id,
                user_message=message,
                assistant_response=reply,
                topic=self._extract_topic(message, reply),
                entities=self._extract_entities(message),
                turn_number=turn_number
            )
            
            # Save conversation to storage
            if self.chat_history_storage == "langchain":
                await self._save_langchain_history(session_id, message, reply)
            else:  # chroma
                await self._save_chroma_history(user_id, chat_id, message, reply)
            
            # Stream end message to NATS
            if stream_producer.enabled and stream_producer._initialized:
                await stream_producer.stream_agent_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_type="end",
                    content={"status": "completed", "full_response": reply}
                )
            
            return reply
            
        except Exception as e:
            logger.error(f"Error in chat method: {e}", exc_info=True)
            
            # Stream error message to NATS
            if stream_producer.enabled and stream_producer._initialized:
                await stream_producer.stream_agent_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_type="error",
                    content={"error": str(e)}
                )
            
            raise
    
    def _sanitize_tools(self, tools: list) -> list:
        """
        Sanitize MCP tools by escaping template variables in descriptions.
        
        MCP tool descriptions may contain placeholders like {organization} which
        LangChain interprets as prompt template variables. This escapes them.
        
        Args:
            tools: List of LangChain tools from MCP server
            
        Returns:
            List of tools with sanitized descriptions
        """
        for tool in tools:
            if hasattr(tool, 'description') and tool.description:
                # Escape single curly braces by doubling them
                # {organization} becomes {{organization}}
                tool.description = tool.description.replace('{', '{{').replace('}', '}}')
                logger.debug(f"Sanitized tool: {tool.name}")
        
        return tools
    
    def _parse_conversation_history(self, retrieved_history: list) -> list:
        """
        Parse retrieved conversation history into LangChain message objects.
        
        Args:
            retrieved_history: List of conversation strings from ChromaDB
            
        Returns:
            List of LangChain message objects including tool calls and results
        """
        messages = []
        
        for entry in retrieved_history:
            if entry.startswith("User: "):
                content = entry[6:]  # Remove "User: " prefix
                messages.append(HumanMessage(content=content))
            elif entry.startswith("Assistant: "):
                content = entry[11:]  # Remove "Assistant: " prefix
                messages.append(AIMessage(content=content))
            elif entry.startswith("ToolCall: "):
                # Parse tool call information
                try:
                    tool_data = entry[10:]  # Remove "ToolCall: " prefix
                    # Store as AIMessage with tool call information embedded
                    messages.append(AIMessage(content=f"[Tool was called: {tool_data}]"))
                except Exception as e:
                    logger.warning(f"Failed to parse tool call: {e}")
            elif entry.startswith("ToolResult: "):
                # Parse tool result - this is the key for context retention
                try:
                    result_data = entry[12:]  # Remove "ToolResult: " prefix
                    # Add as AIMessage so the agent can see the raw tool output
                    messages.append(AIMessage(content=f"[Previous tool result: {result_data}]"))
                except Exception as e:
                    logger.warning(f"Failed to parse tool result: {e}")
        
        return messages
    
    def _get_or_create_memory(self, session_id: str) -> ConversationBufferWindowMemory:
        """
        Get or create LangChain memory for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            ConversationBufferWindowMemory instance
        """
        if session_id not in self._memory_store:
            self._memory_store[session_id] = ConversationBufferWindowMemory(
                k=self.chat_history_window_size,
                return_messages=True,
                memory_key="chat_history"
            )
            logger.info(f"Created new memory for session: {session_id}")
        
        return self._memory_store[session_id]
    
    async def _get_langchain_history(self, session_id: str, message: str) -> List:
        """
        Get conversation history from LangChain's in-memory storage.
        
        Args:
            session_id: Session identifier
            message: Current user message
            
        Returns:
            List of message objects
        """
        memory = self._get_or_create_memory(session_id)
        
        # Load messages from memory
        memory_vars = memory.load_memory_variables({})
        chat_history = memory_vars.get("chat_history", [])
        
        logger.debug(f"Retrieved {len(chat_history)} messages from LangChain memory")
        return chat_history
    
    async def _save_langchain_history(self, session_id: str, user_message: str, assistant_reply: str):
        """
        Save conversation to LangChain's in-memory storage.
        
        Args:
            session_id: Session identifier
            user_message: User's message
            assistant_reply: Assistant's response
        """
        memory = self._get_or_create_memory(session_id)
        
        # Save to memory (it will automatically manage the window)
        memory.save_context(
            {"input": user_message},
            {"output": assistant_reply}
        )
        
        logger.debug(f"Saved conversation to LangChain memory for session: {session_id}")
    
    async def _get_chroma_history(self, user_id: str, chat_id: str, message: str) -> List:
        """
        Get conversation history from ChromaDB with semantic search.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
            message: Current user message
            
        Returns:
            List of message objects
        """
        collection = self._sanitize_collection_name(user_id, chat_id)
        
        # Embed and retrieve relevant history
        user_embedding = await embedding_service.embed(message)
        retrieved_history = await chroma_service.query(
            collection_name=collection,
            embedding=user_embedding,
            n_results=15,
        )
        
        # Parse into message objects
        chat_history = self._parse_conversation_history(retrieved_history)
        
        logger.debug(f"Retrieved {len(chat_history)} messages from ChromaDB")
        return chat_history
    
    async def _save_chroma_history(self, user_id: str, chat_id: str, user_message: str, assistant_reply: str):
        """
        Save conversation to ChromaDB with embeddings.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
            user_message: User's message
            assistant_reply: Assistant's response
        """
        collection = self._sanitize_collection_name(user_id, chat_id)
        
        # Save user message
        user_embedding = await embedding_service.embed(user_message)
        await chroma_service.add_document(
            collection_name=collection,
            document_id=str(uuid4()),
            text=f"User: {user_message}",
            embedding=user_embedding,
            metadata={
                "role": "user",
                "timestamp": datetime.now().isoformat(),
            },
        )
        
        # Save assistant response
        assistant_embedding = await embedding_service.embed(assistant_reply)
        await chroma_service.add_document(
            collection_name=collection,
            document_id=str(uuid4()),
            text=f"Assistant: {assistant_reply}",
            embedding=assistant_embedding,
            metadata={
                "role": "assistant",
                "timestamp": datetime.now().isoformat(),
            },
        )
        
        logger.debug(f"Saved conversation to ChromaDB for user {user_id}, chat {chat_id}")
    
    async def _execute_with_tools_streaming(
        self,
        session_id: str,
        system_message: str, 
        user_message: str,
        tools: list,
        chat_history: list = None,
        user_id: str = "",
        chat_id: str = ""
    ) -> str:
        """
        Execute agent with MCP tools using streaming for real-time updates.
        
        Args:
            session_id: Session identifier
            system_message: System prompt with conversation history
            user_message: User message
            tools: List of LangChain tools from MCP server
            chat_history: Previous conversation messages
            user_id: User identifier for streaming
            chat_id: Chat identifier for streaming
            
        Returns:
            Agent response
        """
        # For tools, we can't easily stream intermediate steps
        # So we execute normally but still stream the final response
        logger.info("Executing with tools (tools don't support streaming, but final response will)")
        
        # Execute agent normally to get full response
        result = await self._execute_with_tools(
            session_id, system_message, user_message, tools, chat_history
        )
        
        # Stream the complete response as chunks
        if stream_producer.enabled and stream_producer._initialized:
            # Split response into chunks for streaming effect
            chunk_size = 50  # characters per chunk
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i+chunk_size]
                await stream_producer.stream_agent_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_type="chunk",
                    content={"chunk": chunk, "accumulated": result[:i+len(chunk)]}
                )
                logger.debug(f"Streamed tool response chunk: {len(chunk)} chars")
        
        return result
    
    async def _execute_with_tools(
        self,
        session_id: str,
        system_message: str, 
        user_message: str,
        tools: list,
        chat_history: list = None
    ) -> str:
        """
        Execute agent with MCP tools using DeepAgents (LangGraph) for advanced reasoning.
        Falls back to standard LangChain agent if DeepAgents is unavailable.
        
        Args:
            session_id: Session identifier
            system_message: System prompt with conversation history
            user_message: User message
            tools: List of LangChain tools from MCP server
            chat_history: Previous conversation messages
            
        Returns:
            Agent response
        """
        # Use DeepAgents (LangGraph) if available for advanced reasoning
        if DEEPAGENTS_AVAILABLE:
            try:
                return await self._execute_with_deepagents(
                    session_id, system_message, user_message, tools, chat_history
                )
            except Exception as e:
                logger.warning(f"DeepAgents execution failed, falling back to standard agent: {e}")
                # Fall through to standard agent
        
        # Standard LangChain agent (fallback)
        return await self._execute_with_standard_agent(
            session_id, system_message, user_message, tools, chat_history
        )
    
    async def _execute_with_deepagents(
        self,
        session_id: str,
        system_message: str,
        user_message: str,
        tools: list,
        chat_history: list = None
    ) -> str:
        """
        Execute using LangGraph's ReAct agent for advanced reasoning and planning.
        
        DeepAgents provides:
        - Advanced reasoning with chain-of-thought
        - Better planning and task decomposition
        - Self-reflection and error correction
        - State management with checkpoints
        
        Args:
            session_id: Session identifier
            system_message: System prompt
            user_message: User message
            tools: Available tools
            chat_history: Previous messages
            
        Returns:
            Agent response
        """
        logger.info("Using DeepAgents (LangGraph) for advanced reasoning")
        
        # Prepare messages for DeepAgents
        messages = []
        
        # Add system message
        messages.append(SystemMessage(content=system_message))
        
        # Add chat history if available
        if chat_history:
            messages.extend(chat_history)
        
        # Add current user message
        messages.append(HumanMessage(content=user_message))
        
        # Create ReAct agent with memory checkpointing (NO state_modifier!)
        memory = MemorySaver()
        agent_executor = create_react_agent(
            model=self.llm,
            tools=tools,
            checkpointer=memory
        )
        
        # Execute with thread-based memory for conversation continuity
        config = {"configurable": {"thread_id": session_id}}
        
        logger.debug(f"Executing DeepAgents with {len(tools)} tools and {len(messages)} messages in history")
        logger.debug(f"Messages include: System + {len(chat_history) if chat_history else 0} history + Current message")
        
        # Invoke the agent - system message and history are in the messages list
        result = await agent_executor.ainvoke(
            {"messages": messages},
            config=config
        )
        
        # Extract the final response
        if "messages" in result and result["messages"]:
            last_message = result["messages"][-1]
            response = last_message.content if hasattr(last_message, 'content') else str(last_message)
            
            # Store tool executions for context
            if "messages" in result:
                await self._store_deepagents_context(session_id, result["messages"])
            
            return response
        
        return "I apologize, but I couldn't generate a response."
    
    async def _execute_with_standard_agent(
        self,
        session_id: str,
        system_message: str,
        user_message: str,
        tools: list,
        chat_history: list = None
    ) -> str:
        """
        Execute using standard LangChain agent (fallback mode).
        
        Args:
            session_id: Session identifier
            system_message: System prompt
            user_message: User message
            tools: Available tools
            chat_history: Previous messages
            
        Returns:
            Agent response
        """
        logger.info("Using standard LangChain agent")
        
        # Sanitize system message to escape any curly braces
        sanitized_system_message = system_message.replace('{', '{{').replace('}', '}}')
        
        # Create prompt template for tool-calling agent with chat history
        prompt_messages = [("system", sanitized_system_message)]
        
        # Add chat history if available
        if chat_history:
            prompt_messages.append(MessagesPlaceholder("chat_history"))
        
        prompt_messages.extend([
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])
        
        prompt = ChatPromptTemplate.from_messages(prompt_messages)
        
        # Create tool-calling agent
        agent = create_tool_calling_agent(self.llm, tools, prompt)
        
        # Create agent executor with detailed logging
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10,
            callbacks=[get_logging_callback("detailed")],
        )
        
        # Execute agent with chat history
        logger.debug(f"Executing standard agent with {len(tools)} tools")
        invoke_input = {"input": user_message}
        if chat_history:
            invoke_input["chat_history"] = chat_history
        
        result = await agent_executor.ainvoke(invoke_input)
        
        # Store tool calls and results for future context
        if self.chat_history_storage == "chroma" and "intermediate_steps" in result:
            collection = session_id.replace("_", "__")
            await self._store_tool_executions(collection, result["intermediate_steps"])
        elif self.chat_history_storage == "langchain" and "intermediate_steps" in result:
            await self._store_tool_results_in_memory(session_id, result["intermediate_steps"])
        
        return result.get("output", "I apologize, but I couldn't generate a response.")
    
    async def _store_deepagents_context(self, session_id: str, messages: list):
        """
        Store DeepAgents execution context for future reference.
        
        Args:
            session_id: Session identifier
            messages: List of messages from DeepAgents execution
        """
        try:
            if self.chat_history_storage == "langchain":
                memory = self._get_or_create_memory(session_id)
                
                # Extract tool calls and results from messages
                for msg in messages:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_info = f"[DeepAgent Tool: {tool_call.get('name', 'unknown')}]"
                            memory.chat_memory.add_message(
                                AIMessage(content=f"[Context] {tool_info}")
                            )
                            logger.debug(f"Stored DeepAgent tool context: {tool_call.get('name')}")
            
        except Exception as e:
            logger.error(f"Error storing DeepAgents context: {e}", exc_info=True)
    
    async def _execute_without_tools_streaming(
        self, 
        system_message: str, 
        user_message: str,
        user_id: str,
        chat_id: str
    ) -> str:
        """
        Execute direct LLM call without tools with streaming to NATS.
        
        Args:
            system_message: System prompt with conversation history
            user_message: User message
            user_id: User identifier for streaming
            chat_id: Chat identifier for streaming
            
        Returns:
            Complete LLM response
        """
        messages = [
            ("system", system_message),
            ("human", user_message),
        ]
        
        logger.debug("Executing LLM without tools (streaming mode)")
        
        full_response = ""
        chunk_buffer = ""
        
        # Stream response chunks to NATS as they arrive
        async for chunk in self.llm.astream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                chunk_text = chunk.content
                full_response += chunk_text
                chunk_buffer += chunk_text
                
                # Stream chunk to NATS immediately
                if stream_producer.enabled and stream_producer._initialized:
                    await stream_producer.stream_agent_message(
                        user_id=user_id,
                        chat_id=chat_id,
                        message_type="chunk",
                        content={"chunk": chunk_text, "accumulated": full_response}
                    )
                    logger.debug(f"Streamed chunk: {len(chunk_text)} chars")
        
        return full_response
    
    async def _execute_without_tools(
        self, 
        system_message: str, 
        user_message: str
    ) -> str:
        """
        Execute direct LLM call without tools (non-streaming fallback).
        
        Args:
            system_message: System prompt with conversation history
            user_message: User message
            
        Returns:
            LLM response
        """
        messages = [
            ("system", system_message),
            ("human", user_message),
        ]
        
        logger.debug("Executing LLM without tools")
        response = await self.llm.ainvoke(messages)
        
        return response.content
    
    async def _store_tool_results_in_memory(self, session_id: str, intermediate_steps: list):
        """
        Store tool results in LangChain memory for context retention.
        
        Args:
            session_id: Session identifier
            intermediate_steps: List of (AgentAction, tool_result) tuples
        """
        try:
            memory = self._get_or_create_memory(session_id)
            
            for step in intermediate_steps:
                if isinstance(step, tuple) and len(step) == 2:
                    agent_action, tool_result = step
                    
                    # Format tool result for memory
                    tool_context = f"[Tool: {agent_action.tool}] Args: {json.dumps(agent_action.tool_input)} | Result: {str(tool_result)[:500]}"
                    
                    # Add to memory as a special context message
                    memory.chat_memory.add_message(
                        AIMessage(content=f"[Context] {tool_context}")
                    )
                    
                    logger.debug(f"Stored tool result in memory: {agent_action.tool}")
        except Exception as e:
            logger.error(f"Error storing tool results in memory: {e}", exc_info=True)
    
    async def _store_tool_executions(
        self, 
        collection_name: str, 
        intermediate_steps: list
    ):
        """
        Store tool calls and their results in ChromaDB for future context.
        
        Args:
            collection_name: ChromaDB collection name
            intermediate_steps: List of (AgentAction, tool_result) tuples
        """
        try:
            for step in intermediate_steps:
                if isinstance(step, tuple) and len(step) == 2:
                    agent_action, tool_result = step
                    
                    # Store tool call info
                    tool_call_text = f"ToolCall: {agent_action.tool} with args: {json.dumps(agent_action.tool_input)}"
                    tool_call_embedding = await embedding_service.embed(tool_call_text)
                    await chroma_service.add_document(
                        collection_name=collection_name,
                        document_id=str(uuid4()),
                        text=tool_call_text,
                        embedding=tool_call_embedding,
                        metadata={
                            "role": "tool_call",
                            "tool_name": agent_action.tool,
                            "timestamp": datetime.now().isoformat(),
                        },
                    )
                    
                    # Store tool result - THIS IS CRITICAL for context retention
                    tool_result_text = f"ToolResult: {agent_action.tool} returned: {str(tool_result)}"
                    tool_result_embedding = await embedding_service.embed(tool_result_text)
                    await chroma_service.add_document(
                        collection_name=collection_name,
                        document_id=str(uuid4()),
                        text=tool_result_text,
                        embedding=tool_result_embedding,
                        metadata={
                            "role": "tool_result",
                            "tool_name": agent_action.tool,
                            "timestamp": datetime.now().isoformat(),
                        },
                    )
                    
                    logger.debug(f"Stored tool execution: {agent_action.tool}")
        except Exception as e:
            logger.error(f"Error storing tool executions: {e}", exc_info=True)
    
    def _format_time_ago(self, timestamp: datetime) -> str:
        """
        Format a timestamp as human-readable 'time ago' string.
        
        Args:
            timestamp: Datetime to format
            
        Returns:
            Human-readable string like '2 hours ago' or '3 days ago'
        """
        now = datetime.now()
        delta = now - timestamp
        
        seconds = delta.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    
    def _extract_topic(self, user_message: str, assistant_response: str) -> Optional[str]:
        """
        Extract a topic/subject from the conversation.
        
        Simple keyword extraction - could be enhanced with NLP.
        
        Args:
            user_message: User's message
            assistant_response: Assistant's response
            
        Returns:
            Extracted topic or None
        """
        # Simple heuristic: use first noun phrase or key terms from user message
        message_lower = user_message.lower()
        
        # Check for common question patterns
        if "intro song" in message_lower or "song" in message_lower:
            return "music composition"
        elif "code" in message_lower or "class" in message_lower or "function" in message_lower:
            return "programming"
        elif "news" in message_lower or "latest" in message_lower:
            return "current events"
        elif "weather" in message_lower:
            return "weather info"
        
        # Default: use first few words as topic
        words = user_message.split()[:3]
        if len(words) > 0:
            return " ".join(words)
        
        return None
    
    def _extract_entities(self, message: str) -> List[str]:
        """
        Extract named entities from a message.
        
        Simple regex-based extraction - could be enhanced with NER models.
        
        Args:
            message: Message text
            
        Returns:
            List of extracted entities
        """
        entities = []
        
        # Extract capitalized words/phrases (potential proper nouns)
        # Pattern: words starting with capital letter
        capitalized_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        matches = re.findall(capitalized_pattern, message)
        
        # Filter out common words
        common_words = {'I', 'The', 'A', 'An', 'This', 'That', 'These', 'Those', 
                       'My', 'Your', 'His', 'Her', 'It', 'We', 'They'}
        
        for match in matches:
            if match not in common_words and len(match) > 2:
                entities.append(match)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_entities = []
        for entity in entities:
            if entity.lower() not in seen:
                seen.add(entity.lower())
                unique_entities.append(entity)
        
        return unique_entities[:5]  # Return max 5 entities
    
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
    
    async def close(self):
        """Close any open connections and cleanup."""
        if self.mcp_client:
            await self.mcp_client.close()
            logger.info("Closed MCP client")
        
        # Clear all memory stores
        self._memory_store.clear()
        logger.info("Cleared all session memories")


# Global agent service instance
agent_service = AgentService()
