# CrewAI Integration Guide

## Overview

The current service uses **LangChain** agents, but you can also use **CrewAI** agents with the same API structure. This guide shows both approaches.

---

## Current Implementation (LangChain)

### Architecture
```
FastAPI → vscode_agent_service.py (LangChain Agent) → Tools → JSON Response
```

### How It Works
1. User sends request to `/vscode/execute`
2. LangChain agent processes the query
3. Agent calls tools (read_file, write_to_file, etc.)
4. Tools return JSON for VS Code to execute
5. Response sent back to user

---

## CrewAI Alternative Implementation

### Option 1: Replace LangChain with CrewAI

Create `crewai_vscode_agent_service.py`:

```python
"""
CrewAI-based VS Code Agent Service
"""

import logging
import json
from typing import Dict
from crewai import Agent, Task, Crew
from langchain_openai import AzureChatOpenAI
from langchain.memory import ConversationBufferWindowMemory

from config import settings
from tools import get_tools_by_names

logger = logging.getLogger(__name__)


class CrewAIVSCodeAgentService:
    """
    CrewAI-based agent service for VS Code file operations.
    """
    
    def __init__(self):
        """Initialize the CrewAI VS Code agent service."""
        # Initialize Azure OpenAI LLM
        self.llm = AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
