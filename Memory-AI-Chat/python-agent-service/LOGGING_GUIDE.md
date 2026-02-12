# How to View LLM Logs and Thought Process

This guide explains how to see the LLM's reasoning, tool usage, and thought process in your Python agent service.

## Current Configuration

Your agent service already has **verbose mode enabled** (`verbose=True` in `agent_service.py` line 170), which means LangChain will output agent thoughts to the console.

## Method 1: Change Log Level to DEBUG (Recommended)

### Option A: Environment Variable
Edit your `.env` file:
```bash
LOG_LEVEL=DEBUG
```

### Option B: Temporary Command Line
Run your server with debug logging:
```bash
LOG_LEVEL=DEBUG python main.py
```

This will show:
- Agent reasoning steps
- Tool calls and their arguments
- Tool responses
- LLM prompts and completions
- Internal LangChain operations

## Method 2: Enable LangChain Detailed Logging

Add this to your `main.py` or `agent_service.py`:

```python
import langchain
langchain.debug = True  # Enable LangChain debug mode
```

This provides even more detailed output including:
- Full prompts sent to the LLM
- Complete LLM responses
- Token usage
- Timing information

## Method 3: Structured Logging with Callbacks

For production-ready structured logging, add callbacks to capture agent thoughts:

```python
from langchain.callbacks import StdOutCallbackHandler

# In agent_service.py, modify _execute_with_tools:
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=10,
    callbacks=[StdOutCallbackHandler()],  # Add this
)
```

## Method 4: Custom Callback for Detailed Logs

For maximum control, create a custom callback handler:

```python
from langchain.callbacks.base import BaseCallbackHandler
from typing import Any, Dict

class DetailedLoggingCallback(BaseCallbackHandler):
    """Custom callback to log agent thoughts and actions."""
    
    def on_agent_action(self, action: Any, **kwargs: Any) -> Any:
        """Log when agent takes an action."""
        logger.info(f"🤖 AGENT THOUGHT: {action.log}")
        logger.info(f"🔧 TOOL: {action.tool}")
        logger.info(f"📥 TOOL INPUT: {action.tool_input}")
    
    def on_agent_finish(self, finish: Any, **kwargs: Any) -> Any:
        """Log when agent finishes."""
        logger.info(f"✅ AGENT FINAL ANSWER: {finish.return_values}")
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        """Log when a tool starts."""
        logger.info(f"🔨 TOOL START: {serialized.get('name')} with input: {input_str}")
    
    def on_tool_end(self, output: str, **kwargs: Any) -> Any:
        """Log when a tool completes."""
        logger.info(f"✅ TOOL RESULT: {output}")
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs: Any) -> Any:
        """Log when LLM starts."""
        logger.debug(f"💭 LLM PROMPT: {prompts}")
    
    def on_llm_end(self, response: Any, **kwargs: Any) -> Any:
        """Log when LLM completes."""
        logger.debug(f"🤖 LLM RESPONSE: {response}")

# Use it in your agent:
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=10,
    callbacks=[DetailedLoggingCallback()],
)
```

## What You'll See

With verbose logging enabled, you'll see output like:

```
> Entering new AgentExecutor chain...

🤖 AGENT THOUGHT: I need to use a tool to answer this question
🔧 TOOL: search_spring_mcp
📥 TOOL INPUT: {"query": "user information"}

🔨 TOOL START: search_spring_mcp with input: {"query": "user information"}
✅ TOOL RESULT: [search results here]

🤖 AGENT THOUGHT: Based on the tool output, I can now formulate an answer
✅ AGENT FINAL ANSWER: Here is the information you requested...

> Finished chain.
```

## Viewing Logs

### Console Output
Logs will appear in your terminal/console where you run the server.

### File Output
To save logs to a file, modify `main.py`:

```python
import logging
from logging.handlers import RotatingFileHandler

# Add file handler
file_handler = RotatingFileHandler(
    'agent.log',
    maxBytes=10485760,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(file_formatter)

# Add to root logger
logging.getLogger().addHandler(file_handler)
```

Now logs will be saved to `agent.log` and also shown in console.

## Quick Start

**Simplest way to see agent thoughts RIGHT NOW:**

1. Stop your server if running
2. Run: `LOG_LEVEL=DEBUG python main.py`
3. Make a chat request
4. Watch the console for detailed agent reasoning!

## Already Configured Features

Your codebase already has:
- ✅ `verbose=True` in AgentExecutor
- ✅ Logging framework configured
- ✅ Logger instances in agent_service.py
- ✅ Debug logging statements in key methods

You just need to change the log level to DEBUG to see everything!
