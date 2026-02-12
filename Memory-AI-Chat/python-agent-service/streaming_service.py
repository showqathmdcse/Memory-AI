"""
Streaming service that wraps the agent execution with Kafka streaming.
"""
import logging
from typing import Optional
from kafka_producer import stream_producer
from vscode_agent_service import vscode_agent_service

logger = logging.getLogger(__name__)


class StreamingService:
    """Service for streaming agent responses via Kafka."""
    
    def __init__(self):
        """Initialize streaming service."""
        self.producer = stream_producer
        self.agent = vscode_agent_service
    
    async def execute_with_streaming(
        self,
        user_query: str,
        user_id: str,
        chat_id: str,
        workspace_context: Optional[dict] = None
    ) -> str:
        """
        Execute agent task with optional Kafka streaming.
        
        If streaming is enabled, sends progress updates to Kafka.
        If streaming is disabled, works like normal execution.
        
        Args:
            user_query: User's query
            user_id: User identifier
            chat_id: Chat identifier
            workspace_context: Optional workspace context
            
        Returns:
            Agent's response (tool JSON or completion message)
        """
        try:
            # Stream start message
            if self.producer.enabled:
                await self.producer.stream_agent_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_type="start",
                    content={"query": user_query}
                )
            
            # Execute agent task
            response = await self.agent.execute_task(
                user_query=user_query,
                user_id=user_id,
                chat_id=chat_id
            )
            
            # Stream response
            if self.producer.enabled:
                await self.producer.stream_agent_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_type="response",
                    content={"response": response}
                )
            
            return response
            
        except Exception as e:
            logger.error(f"Error in streaming execution: {e}")
            
            # Stream error
            if self.producer.enabled:
                await self.producer.stream_agent_message(
                    user_id=user_id,
                    chat_id=chat_id,
                    message_type="error",
                    content={"error": str(e)}
                )
            
            raise
    
    async def stream_file_changes(
        self,
        user_id: str,
        chat_id: str,
        file_path: str,
        content: str,
        operation: str = "modify"
    ) -> bool:
        """
        Stream file changes line-by-line.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
            file_path: Path to file
            content: New file content
            operation: Operation type (create, modify, delete)
            
        Returns:
            True if streaming succeeded
        """
        if not self.producer.enabled:
            return False
        
        # Split content into lines
        lines = content.split('\n')
        changes = [
            {"line_number": i, "content": line}
            for i, line in enumerate(lines)
        ]
        
        return await self.producer.stream_code_changes(
            user_id=user_id,
            chat_id=chat_id,
            file_path=file_path,
            changes=changes,
            operation=operation
        )


# Global streaming service instance
streaming_service = StreamingService()
