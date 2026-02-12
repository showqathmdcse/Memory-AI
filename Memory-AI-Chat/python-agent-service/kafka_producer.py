"""
Kafka producer for streaming agent responses and code changes.
"""
import json
import logging
import asyncio
from typing import AsyncGenerator, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

from kafka_config import kafka_settings

logger = logging.getLogger(__name__)


class AgentStreamProducer:
    """Kafka producer for streaming agent messages and code changes."""
    
    def __init__(self):
        """Initialize Kafka producer."""
        self.enabled = kafka_settings.streaming_enabled
        self.producer: Optional[KafkaProducer] = None
        
        if self.enabled:
            try:
                self.producer = KafkaProducer(
                    bootstrap_servers=kafka_settings.kafka_bootstrap_servers.split(','),
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    key_serializer=lambda k: k.encode('utf-8') if k else None,
                    compression_type=kafka_settings.kafka_producer_compression,
                    max_request_size=kafka_settings.kafka_producer_max_request_size,
                    acks='all',  # Wait for all replicas
                    retries=3
                )
                logger.info("Kafka producer initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Kafka producer: {e}")
                self.enabled = False
                self.producer = None
        else:
            logger.info("Kafka streaming is disabled")
    
    async def stream_agent_message(
        self,
        user_id: str,
        chat_id: str,
        message_type: str,
        content: any,
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Stream an agent message to Kafka.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
            message_type: Type of message (message, tool, progress, end)
            content: Message content
            metadata: Optional metadata
            
        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.enabled or not self.producer:
            return False
        
        try:
            topic_key = f"{user_id}:{chat_id}"
            
            message = {
                "type": message_type,
                "user_id": user_id,
                "chat_id": chat_id,
                "content": content,
                "metadata": metadata or {},
                "timestamp": asyncio.get_event_loop().time()
            }
            
            future = self.producer.send(
                kafka_settings.kafka_topic_messages,
                key=topic_key,
                value=message
            )
            
            # Wait for send to complete (non-blocking)
            await asyncio.get_event_loop().run_in_executor(
                None,
                future.get,
                5  # 5 second timeout
            )
            
            logger.debug(f"Sent message to Kafka: {message_type}")
            return True
            
        except KafkaError as e:
            logger.error(f"Kafka error: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending message to Kafka: {e}")
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
        Stream code changes line-by-line to Kafka.
        
        Args:
            user_id: User identifier
            chat_id: Chat identifier
            file_path: Path to the file being changed
            changes: List of changes (line_number, content)
            operation: Type of operation (create, modify, delete)
            
        Returns:
            True if all changes sent successfully
        """
        if not self.enabled or not self.producer:
            return False
        
        try:
            topic_key = f"{user_id}:{chat_id}"
            
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
                
                self.producer.send(
                    kafka_settings.kafka_topic_code_changes,
                    key=topic_key,
                    value=message
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
            
            self.producer.send(
                kafka_settings.kafka_topic_code_changes,
                key=topic_key,
                value=end_message
            )
            
            self.producer.flush()
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
    
    def close(self):
        """Close the Kafka producer."""
        if self.producer:
            try:
                self.producer.flush()
                self.producer.close()
                logger.info("Kafka producer closed")
            except Exception as e:
                logger.error(f"Error closing Kafka producer: {e}")


# Global producer instance
stream_producer = AgentStreamProducer()
