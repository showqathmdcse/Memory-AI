"""
Custom logging callbacks for detailed agent execution tracking.

This module provides callback handlers that capture and log agent thoughts,
tool usage, and LLM interactions in a structured way.
"""

import logging
from typing import Any, Dict, List, Optional, Union

from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)


class DetailedAgentCallback(BaseCallbackHandler):
    """
    Comprehensive callback handler for logging agent execution details.
    
    Logs:
    - Agent thoughts and reasoning
    - Tool selection and inputs
    - Tool execution results
    - LLM prompts and responses
    - Error handling
    """
    
    def __init__(self, log_prompts: bool = True, log_responses: bool = True):
        """
        Initialize the callback handler.
        
        Args:
            log_prompts: Whether to log full LLM prompts (can be verbose)
            log_responses: Whether to log full LLM responses
        """
        self.log_prompts = log_prompts
        self.log_responses = log_responses
        self.step_count = 0
    
    def on_chain_start(
        self, 
        serialized: Dict[str, Any], 
        inputs: Dict[str, Any], 
        **kwargs: Any
    ) -> None:
        """Log when a chain starts."""
        chain_name = serialized.get("name", "Unknown Chain")
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 Starting {chain_name}")
        logger.info(f"{'='*80}")
        self.step_count = 0
    
    def on_chain_end(
        self, 
        outputs: Dict[str, Any], 
        **kwargs: Any
    ) -> None:
        """Log when a chain completes."""
        logger.info(f"\n{'='*80}")
        logger.info(f"✅ Chain completed successfully after {self.step_count} steps")
        logger.info(f"{'='*80}\n")
    
    def on_agent_action(
        self, 
        action: Any, 
        **kwargs: Any
    ) -> None:
        """Log when agent decides to take an action."""
        self.step_count += 1
        logger.info(f"\n{'─'*80}")
        logger.info(f"Step {self.step_count}: Agent Decision")
        logger.info(f"{'─'*80}")
        logger.info(f"🤖 THOUGHT PROCESS:")
        logger.info(f"{action.log}")
        logger.info(f"\n🔧 SELECTED TOOL: {action.tool}")
        logger.info(f"📥 TOOL INPUT: {action.tool_input}")
    
    def on_agent_finish(
        self, 
        finish: Any, 
        **kwargs: Any
    ) -> None:
        """Log when agent finishes execution."""
        logger.info(f"\n{'─'*80}")
        logger.info(f"Final Answer Generated")
        logger.info(f"{'─'*80}")
        logger.info(f"✅ AGENT FINAL ANSWER:")
        output = finish.return_values.get("output", str(finish.return_values))
        logger.info(f"{output}")
    
    def on_tool_start(
        self, 
        serialized: Dict[str, Any], 
        input_str: str, 
        **kwargs: Any
    ) -> None:
        """Log when a tool starts execution."""
        tool_name = serialized.get("name", "Unknown Tool")
        logger.info(f"\n🔨 EXECUTING TOOL: {tool_name}")
        logger.info(f"Input: {input_str}")
    
    def on_tool_end(
        self, 
        output: str, 
        **kwargs: Any
    ) -> None:
        """Log when a tool completes execution."""
        # Truncate long outputs for readability
        max_length = 500
        if len(output) > max_length:
            display_output = output[:max_length] + f"... (truncated, {len(output)} total chars)"
        else:
            display_output = output
        
        logger.info(f"✅ TOOL RESULT: {display_output}")
    
    def on_tool_error(
        self, 
        error: Union[Exception, KeyboardInterrupt], 
        **kwargs: Any
    ) -> None:
        """Log when a tool encounters an error."""
        logger.error(f"❌ TOOL ERROR: {str(error)}")
    
    def on_llm_start(
        self, 
        serialized: Dict[str, Any], 
        prompts: List[str], 
        **kwargs: Any
    ) -> None:
        """Log when LLM call starts."""
        if self.log_prompts:
            logger.debug(f"\n💭 LLM CALL STARTING")
            logger.debug(f"Model: {serialized.get('name', 'Unknown')}")
            for i, prompt in enumerate(prompts):
                logger.debug(f"Prompt {i+1}:\n{prompt[:500]}...")
    
    def on_llm_end(
        self, 
        response: LLMResult, 
        **kwargs: Any
    ) -> None:
        """Log when LLM call completes."""
        if self.log_responses:
            logger.debug(f"\n🤖 LLM RESPONSE RECEIVED")
            for i, generation in enumerate(response.generations):
                for j, gen in enumerate(generation):
                    text = gen.text[:500] if hasattr(gen, 'text') else str(gen)[:500]
                    logger.debug(f"Generation {i+1}.{j+1}: {text}...")
            
            # Log token usage if available
            if response.llm_output and "token_usage" in response.llm_output:
                usage = response.llm_output["token_usage"]
                logger.debug(f"📊 Token Usage: {usage}")
    
    def on_llm_error(
        self, 
        error: Union[Exception, KeyboardInterrupt], 
        **kwargs: Any
    ) -> None:
        """Log when LLM call encounters an error."""
        logger.error(f"❌ LLM ERROR: {str(error)}")
    
    def on_chain_error(
        self, 
        error: Union[Exception, KeyboardInterrupt], 
        **kwargs: Any
    ) -> None:
        """Log when chain encounters an error."""
        logger.error(f"\n{'='*80}")
        logger.error(f"❌ CHAIN ERROR: {str(error)}")
        logger.error(f"{'='*80}\n")


class CompactAgentCallback(BaseCallbackHandler):
    """
    Compact callback handler for production environments.
    
    Logs only essential information without verbose prompts/responses.
    """
    
    def on_agent_action(self, action: Any, **kwargs: Any) -> None:
        """Log agent action in compact format."""
        logger.info(f"🔧 Tool: {action.tool} | Input: {str(action.tool_input)[:100]}")
    
    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Log tool result in compact format."""
        logger.info(f"✅ Result: {output[:100]}{'...' if len(output) > 100 else ''}")
    
    def on_agent_finish(self, finish: Any, **kwargs: Any) -> None:
        """Log final answer in compact format."""
        output = finish.return_values.get("output", "")
        logger.info(f"✅ Final: {output[:150]}{'...' if len(output) > 150 else ''}")
    
    def on_tool_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """Log tool error."""
        logger.error(f"❌ Tool Error: {str(error)}")
    
    def on_llm_error(self, error: Union[Exception, KeyboardInterrupt], **kwargs: Any) -> None:
        """Log LLM error."""
        logger.error(f"❌ LLM Error: {str(error)}")


def get_logging_callback(mode: str = "detailed") -> BaseCallbackHandler:
    """
    Factory function to get appropriate callback handler.
    
    Args:
        mode: "detailed" for verbose logging, "compact" for production,
              "debug" for maximum verbosity including prompts/responses
              
    Returns:
        Appropriate callback handler instance
    """
    if mode == "detailed":
        return DetailedAgentCallback(log_prompts=False, log_responses=False)
    elif mode == "debug":
        return DetailedAgentCallback(log_prompts=True, log_responses=True)
    elif mode == "compact":
        return CompactAgentCallback()
    else:
        logger.warning(f"Unknown callback mode: {mode}, using compact")
        return CompactAgentCallback()
