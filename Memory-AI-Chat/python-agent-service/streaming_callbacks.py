"""
Streaming callbacks for capturing and streaming tool calls in real-time.
"""
import logging
import json
from typing import Any, Dict, List, Optional
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.agents import AgentAction, AgentFinish
from nats_producer import stream_producer

logger = logging.getLogger(__name__)


class ToolCallStreamingCallback(BaseCallbackHandler):
    """
    Callback handler that streams each tool call to NATS as it happens.
    
    This ensures the IDE receives ALL tool calls, not just the final one.
    """
    
    def __init__(self, user_id: str, chat_id: str, enabled: bool = False):
        """
        Initialize the callback handler.
        
        Args:
            user_id: User identifier for streaming
            chat_id: Chat identifier for streaming
            enabled: Whether streaming is enabled
        """
        self.user_id = user_id
        self.chat_id = chat_id
        self.enabled = enabled
        self.tool_calls_sent = []
        logger.info(f"ToolCallStreamingCallback initialized (enabled={enabled})")
    
    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> Any:
        """
        Called when the agent takes an action (calls a tool).
        
        This is where we capture and stream each tool call.
        
        Args:
            action: The agent action containing tool name and input
        """
        if not self.enabled or not stream_producer.enabled or not stream_producer._initialized:
            return
        
        try:
            tool_name = action.tool
            tool_input = action.tool_input
            
            logger.info(f"Agent calling tool: {tool_name} with input: {tool_input}")
            
            # Create tool JSON (matching the format returned by tool functions)
            tool_json = json.dumps({
                "tool": tool_name,
                **tool_input
            })
            
            # Track that we sent this tool call
            self.tool_calls_sent.append(tool_name)
            
            # Stream the tool call immediately
            import asyncio
            
            async def stream_tool():
                await stream_producer.stream_agent_message(
                    user_id=self.user_id,
                    chat_id=self.chat_id,
                    message_type="tool_call",
                    content={
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_json": tool_json,
                        "sequence": len(self.tool_calls_sent)
                    }
                )
            
            # Run the async function
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                # If loop is already running, create a task
                asyncio.create_task(stream_tool())
            else:
                # Otherwise run it
                loop.run_until_complete(stream_tool())
            
            logger.info(f"Streamed tool call #{len(self.tool_calls_sent)}: {tool_name}")
            
        except Exception as e:
            logger.error(f"Error streaming tool call: {e}", exc_info=True)
    
    def on_tool_end(self, output: str, **kwargs: Any) -> Any:
        """
        Called when a tool finishes execution.
        
        Args:
            output: The tool's output
        """
        if not self.enabled or not stream_producer.enabled or not stream_producer._initialized:
            return
        
        try:
            logger.info(f"Tool completed with output length: {len(output)} chars")
            
            # Stream the tool result
            import asyncio
            
            async def stream_result():
                await stream_producer.stream_agent_message(
                    user_id=self.user_id,
                    chat_id=self.chat_id,
                    message_type="tool_result",
                    content={
                        "output": output[:500],  # Limit size for streaming
                        "output_length": len(output),
                        "sequence": len(self.tool_calls_sent)
                    }
                )
            
            # Run the async function
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                asyncio.create_task(stream_result())
            else:
                loop.run_until_complete(stream_result())
            
        except Exception as e:
            logger.error(f"Error streaming tool result: {e}", exc_info=True)
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs: Any) -> Any:
        """
        Called when the agent finishes its execution.
        
        Args:
            finish: The agent finish object with final output
        """
        if not self.enabled or not stream_producer.enabled or not stream_producer._initialized:
            return
        
        try:
            logger.info(f"Agent finished. Total tool calls sent: {len(self.tool_calls_sent)}")
            
            # Stream completion message
            import asyncio
            
            async def stream_finish():
                await stream_producer.stream_agent_message(
                    user_id=self.user_id,
                    chat_id=self.chat_id,
                    message_type="agent_finish",
                    content={
                        "total_tool_calls": len(self.tool_calls_sent),
                        "tools_used": self.tool_calls_sent,
                        "final_output": str(finish.return_values)[:200]
                    }
                )
            
            # Run the async function
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            if loop.is_running():
                asyncio.create_task(stream_finish())
            else:
                loop.run_until_complete(stream_finish())
            
        except Exception as e:
            logger.error(f"Error streaming agent finish: {e}", exc_info=True)
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> Any:
        """Called when LLM starts processing."""
        if self.enabled:
            logger.debug(f"LLM started with {len(prompts)} prompts")
    
    def on_llm_end(self, response, **kwargs: Any) -> Any:
        """Called when LLM finishes processing."""
        if self.enabled:
            logger.debug("LLM finished processing")
