"""
NATS JetStream producer for streaming agent responses and code changes.
"""
import json
import logging
import asyncio
from typing import Optional
import nats
from nats.js import JetStreamContext
from nats.js.api import StreamConfig, RetentionPolicy

from nats_config import nats_settings

logger = logging.getLogger(__name__)


class AgentStreamProducer:
    """NATS JetStream producer for streaming agent messages and code changes."""
    
    def __init__(self):
        """Initialize NATS producer."""
        self.enabled = nats_settings.streaming_enabled
        self.nc: Optional[nats.NATS] = None
        self.js: Optional[JetStreamContext] = None
        self._initialized = False
    
    async def initialize(self):
        """Connect to NATS and set up JetStream."""
        if not self.enabled:
            logger.info("NATS streaming is disabled")
            return
        
        try:
            # Wait for NATS to be ready (in Docker, it takes a moment to start)
            logger.info("Waiting for NATS to be ready...")
            await asyncio.sleep(3)
            
            # Connect to NATS with retry
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    self.nc = await nats.connect(
                        nats_settings.nats_url,
                        max_reconnect_attempts=5,
                        reconnect_time_wait=2,
                        connect_timeout=5
                    )
                    logger.info(f"Connected to NATS at {nats_settings.nats_url}")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"NATS connection attempt {attempt + 1} failed, retrying in 2s...")
                        await asyncio.sleep(2)
                    else:
                        raise
            
            self.js = self.nc.jetstream()
            
            # Wait a moment for JetStream to be ready
            await asyncio.sleep(1)
            
            # Create stream if it doesn't exist
            try:
                stream_config = StreamConfig(
                    name=nats_settings.nats_stream_name,
                    subjects=[
                        f"{nats_settings.nats_subject_messages}.>",
                        f"{nats_settings.nats_subject_code_changes}.>"
                    ],
                    retention=RetentionPolicy.LIMITS,
                    max_age=nats_settings.nats_max_age_seconds,
                    max_msgs=nats_settings.nats_max_msgs,
                    max_bytes=nats_settings.nats_max_bytes
                )
                await self.js.add_stream(config=stream_config)
                logger.info(f"Created JetStream: {nats_settings.nats_stream_name}")
                
                # Wait for stream to be ready
                await asyncio.sleep(0.5)
                
            except Exception as e:
                # Stream might already exist, try to get info
                try:
                    stream_info = await self.js.stream_info(nats_settings.nats_stream_name)
                    logger.info(f"Using existing JetStream: {stream_info.config.name}")
                except Exception as info_error:
                    logger.error(f"Stream error: {e}, Info error: {info_error}")
                    raise
            
            self._initialized = True
            logger.info("NATS producer initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize NATS producer: {e}")
            self.enabled = False
            self._initialized = False
    
    async def stream_agent_message(
        self,
        user_id: str,
        chat_id: str,
        message_type: str,
        content: any,
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Stream an agent message to NATS.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
            message_type: Type of message (start, response, error, end)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enabled or not self._initialized or not self.js:
            return False
        
        try:
            message = {
                "type": message_type,
                "user_id": user_id,
                "chat_id": chat_id,
                "content": content,
                "metadata": metadata or {},
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Publish to subject with user_id:chat_id as suffix for filtering
            subject = f"{nats_settings.nats_subject_messages}.{user_id}.{chat_id}"
            
            await self.js.publish(
                subject,
                json.dumps(message).encode(),
                timeout=10.0  # 10 second timeout
            )
            
            logger.debug(f"Sent message to NATS: {message_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message to NATS: {e}")
            return False
    
    async def stream_code_changes(
        self,
        user_id: str,
        chat_id: str,
        file_path: str,
        changes: list,
        operation: str = "modify"
    ) -> bool:
        """
        Stream code changes line-by-line to NATS.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
            file_path: Path to the file being changed
            changes: List of changes (line_number, content)
            operation: Type of operation (create, modify, delete)
            
        Returns:
            True if all changes sent successfully
        """
        if not self.enabled or not self._initialized or not self.js:
            return False
        
        try:
            subject = f"{nats_settings.nats_subject_code_changes}.{user_id}.{chat_id}"
            
            # Send each change
            for i, change in enumerate(changes):
                message = {
                    "type": "line",
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "file_path": file_path,
                    "line_number": change.get("line_number", i),
                    "content": change.get("content", ""),
                    "operation": operation,
                    "total_lines": len(changes),
                    "current_line": i + 1
                }
                
                await self.js.publish(
                    subject,
                    json.dumps(message).encode()
                )
                
                # Small delay for animation effect
                await asyncio.sleep(0.05)
            
            # Send completion message
            end_message = {
                "type": "done",
                "user_id": user_id,
                "chat_id": chat_id,
                "file_path": file_path,
                "operation": operation,
                "total_lines": len(changes)
            }
            
            await self.js.publish(
                subject,
                json.dumps(end_message).encode()
            )
            
            logger.info(f"Streamed {len(changes)} lines for {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error streaming code changes: {e}")
            return False
    
    async def stream_tool_execution(
        self,
        user_id: str,
        chat_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: any,
        status: str = "success"
    ) -> bool:
        """
        Stream tool execution details.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
            tool_name: Name of the tool
            tool_input: Tool input parameters
            tool_output: Tool output/result
            status: Execution status (success, error, progress)
            
        Returns:
            True if message sent successfully
        """
        return await self.stream_agent_message(
            user_id=user_id,
            chat_id=chat_id,
            message_type="tool",
            content={
                "tool_name": tool_name,
                "input": tool_input,
                "output": tool_output,
                "status": status
            }
        )
    
    async def close(self):
        """Close the NATS connection."""
        if self.nc and self._initialized:
            try:
                await self.nc.drain()
                await self.nc.close()
                logger.info("NATS producer closed")
            except Exception as e:
                logger.error(f"Error closing NATS producer: {e}")


# Global producer instance
stream_producer = AgentStreamProducer()
