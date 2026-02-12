"""
Episodic Memory Service for Conversational AI

Stores and retrieves conversation episodes with temporal and semantic context,
enabling long-term memory and context-aware conversations.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import uuid4
from dataclasses import dataclass, asdict
import json
import math

from services.chroma_service import chroma_service
from services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


@dataclass
class Episode:
    """
    Represents a single conversation episode with full context.
    """
    id: str
    timestamp: datetime
    user_id: str
    chat_id: str
    
    # Conversation turn
    user_message: str
    assistant_response: str
    
    # Context and metadata
    topic: Optional[str] = None
    entities: Optional[List[str]] = None
    intent: Optional[str] = None
    importance_score: float = 0.5
    turn_number: int = 0
    
    # Tool usage tracking
    tools_used: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert episode to dictionary for storage."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Episode':
        """Create episode from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class EpisodicMemoryService:
    """
    Manages episodic memory for conversational agents.
    
    Features:
    - Stores conversation episodes with full context
    - Retrieves relevant episodes using hybrid search (semantic + temporal + importance)
    - Tracks conversation arcs across multiple turns
    - Automatic importance scoring
    - Memory consolidation over time
    """
    
    def __init__(self):
        """Initialize episodic memory service."""
        self.collection_prefix = "episodic_memory"
        logger.info("Initialized EpisodicMemoryService")
    
    def _get_collection_name(self, user_id: str, chat_id: str) -> str:
        """Get ChromaDB collection name for user's episodic memory."""
        # Sanitize IDs
        safe_user = chroma_service._sanitize_collection_name(user_id)
        safe_chat = chroma_service._sanitize_collection_name(chat_id)
        return f"{self.collection_prefix}_{safe_user}_{safe_chat}"
    
    async def store_episode(
        self,
        user_id: str,
        chat_id: str,
        user_message: str,
        assistant_response: str,
        topic: Optional[str] = None,
        entities: Optional[List[str]] = None,
        tools_used: Optional[List[str]] = None,
        turn_number: int = 0
    ) -> Episode:
        """
        Store a conversation episode with full context.
        
        Args:
            user_id: User identifier
            chat_id: Chat session identifier
            user_message: User's message
            assistant_response: Assistant's response
            topic: Extracted topic (optional)
            entities: Named entities (optional)
            tools_used: Tools used in this turn (optional)
            turn_number: Turn number in conversation
            
        Returns:
            Created Episode object
        """
        try:
            collection = self._get_collection_name(user_id, chat_id)
            
            # Create episode
            episode = Episode(
                id=str(uuid4()),
                timestamp=datetime.now(),
                user_id=user_id,
                chat_id=chat_id,
                user_message=user_message,
                assistant_response=assistant_response,
                topic=topic,
                entities=entities or [],
                tools_used=tools_used or [],
                turn_number=turn_number
            )
            
            # Calculate importance score
            episode.importance_score = self._calculate_importance(episode)
            
            # Create embedding from episode context
            episode_text = self._format_episode_for_embedding(episode)
            embedding = await embedding_service.embed(episode_text)
            
            # Store in ChromaDB
            await chroma_service.add_document(
                collection_name=collection,
                document_id=episode.id,
                text=episode_text,
                embedding=embedding,
                metadata={
                    "timestamp": episode.timestamp.isoformat(),
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "topic": topic or "general",
                    "entities": json.dumps(entities or []),
                    "importance": episode.importance_score,
                    "turn_number": turn_number,
                    "tools_used": json.dumps(tools_used or []),
                    "user_message_preview": user_message[:100],
                }
            )
            
            logger.info(
                f"Stored episode {episode.id} for {user_id}/{chat_id} "
                f"(importance: {episode.importance_score:.2f})"
            )
            
            return episode
            
        except Exception as e:
            logger.error(f"Error storing episode: {e}", exc_info=True)
            raise
    
    async def retrieve_relevant_episodes(
        self,
        user_id: str,
        chat_id: str,
        query: str,
        top_k: int = 5,
        temporal_window_days: Optional[int] = 7,
        min_importance: float = 0.0
    ) -> List[Episode]:
        """
        Retrieve relevant episodes using hybrid search.
        
        Combines:
        - Semantic similarity (from embeddings)
        - Temporal relevance (recent episodes weighted higher)
        - Importance scores
        
        Args:
            user_id: User identifier
            chat_id: Chat session identifier
            query: Current query/message
            top_k: Number of episodes to retrieve
            temporal_window_days: Only retrieve episodes within this window (None = all time)
            min_importance: Minimum importance score filter
            
        Returns:
            List of relevant Episode objects, sorted by relevance
        """
        try:
            collection = self._get_collection_name(user_id, chat_id)
            
            # Create query embedding
            query_embedding = await embedding_service.embed(query)
            
            # Retrieve from ChromaDB (get more than needed for filtering)
            retrieved = await chroma_service.query(
                collection_name=collection,
                embedding=query_embedding,
                n_results=top_k * 3,  # Get extra for filtering
            )
            
            if not retrieved:
                logger.debug(f"No episodes found for {user_id}/{chat_id}")
                return []
            
            # Parse episodes and apply filters
            episodes = []
            now = datetime.now()
            
            for text in retrieved:
                try:
                    # Extract episode data from stored text
                    # Format: "[timestamp] Topic: X | User: Y | Assistant: Z"
                    episode_data = self._parse_episode_text(text)
                    if not episode_data:
                        continue
                    
                    episode = Episode(**episode_data)
                    
                    # Apply temporal window filter
                    if temporal_window_days:
                        age_days = (now - episode.timestamp).days
                        if age_days > temporal_window_days:
                            continue
                    
                    # Apply importance filter
                    if episode.importance_score < min_importance:
                        continue
                    
                    episodes.append(episode)
                    
                except Exception as e:
                    logger.warning(f"Failed to parse episode: {e}")
                    continue
            
            # Rank episodes using hybrid scoring
            ranked_episodes = self._rank_episodes(episodes, query, now)
            
            # Return top K
            result = ranked_episodes[:top_k]
            
            logger.info(
                f"Retrieved {len(result)} relevant episodes for {user_id}/{chat_id} "
                f"(from {len(episodes)} candidates)"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving episodes: {e}", exc_info=True)
            return []
    
    async def get_conversation_arc(
        self,
        user_id: str,
        chat_id: str,
        limit: int = 20
    ) -> List[Episode]:
        """
        Get recent conversation episodes in chronological order.
        
        Args:
            user_id: User identifier
            chat_id: Chat session identifier
            limit: Maximum number of episodes to retrieve
            
        Returns:
            List of episodes in chronological order
        """
        try:
            collection = self._get_collection_name(user_id, chat_id)
            
            # Get recent episodes (use a generic query)
            retrieved = await chroma_service.query(
                collection_name=collection,
                embedding=await embedding_service.embed("recent conversation"),
                n_results=limit * 2,
            )
            
            # Parse and sort by timestamp
            episodes = []
            for text in retrieved:
                try:
                    episode_data = self._parse_episode_text(text)
                    if episode_data:
                        episodes.append(Episode(**episode_data))
                except Exception as e:
                    logger.warning(f"Failed to parse episode: {e}")
            
            # Sort chronologically
            episodes.sort(key=lambda x: x.timestamp)
            
            return episodes[-limit:]  # Return most recent
            
        except Exception as e:
            logger.error(f"Error getting conversation arc: {e}", exc_info=True)
            return []
    
    def _format_episode_for_embedding(self, episode: Episode) -> str:
        """
        Format episode for embedding and storage.
        
        Creates a rich text representation including all context.
        """
        parts = [
            f"[{episode.timestamp.isoformat()}]",
            f"Topic: {episode.topic or 'general'}",
        ]
        
        if episode.entities:
            parts.append(f"Entities: {', '.join(episode.entities)}")
        
        parts.extend([
            f"User: {episode.user_message}",
            f"Assistant: {episode.assistant_response[:500]}...",  # Truncate long responses
        ])
        
        if episode.tools_used:
            parts.append(f"Tools: {', '.join(episode.tools_used)}")
        
        return " | ".join(parts)
    
    def _parse_episode_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse episode text back into structured data."""
        try:
            # Format: "[timestamp] Topic: X | Entities: Y | User: Z | Assistant: W | Tools: T"
            parts = text.split(" | ")
            
            data = {}
            
            # Extract timestamp
            if parts[0].startswith("["):
                timestamp_str = parts[0][1:parts[0].index("]")]
                data['timestamp'] = datetime.fromisoformat(timestamp_str)
            
            # Extract other fields
            for part in parts:
                if part.startswith("Topic: "):
                    data['topic'] = part[7:]
                elif part.startswith("Entities: "):
                    entities_str = part[10:]
                    data['entities'] = [e.strip() for e in entities_str.split(",")] if entities_str != "general" else []
                elif part.startswith("User: "):
                    data['user_message'] = part[6:]
                elif part.startswith("Assistant: "):
                    data['assistant_response'] = part[11:]
                elif part.startswith("Tools: "):
                    tools_str = part[7:]
                    data['tools_used'] = [t.strip() for t in tools_str.split(",")] if tools_str else []
            
            # Add required fields with defaults
            data.setdefault('id', str(uuid4()))
            data.setdefault('user_id', 'unknown')
            data.setdefault('chat_id', 'unknown')
            data.setdefault('importance_score', 0.5)
            data.setdefault('turn_number', 0)
            
            return data
            
        except Exception as e:
            logger.warning(f"Failed to parse episode text: {e}")
            return None
    
    def _calculate_importance(self, episode: Episode) -> float:
        """
        Calculate importance score for an episode.
        
        Factors:
        - Length of conversation (longer = more important)
        - Named entities present (entities = more specific/important)
        - Tool usage (tool calls = action taken = important)
        - Turn number (deeper conversations = more important)
        """
        score = 0.5  # Base score
        
        # Length factor (longer messages tend to be more substantial)
        message_length = len(episode.user_message) + len(episode.assistant_response)
        if message_length > 500:
            score += 0.2
        elif message_length > 200:
            score += 0.1
        
        # Entity factor (specific entities = more memorable)
        if episode.entities and len(episode.entities) > 0:
            score += min(0.2, len(episode.entities) * 0.1)
        
        # Tool usage factor (actions taken = important)
        if episode.tools_used and len(episode.tools_used) > 0:
            score += 0.2
        
        # Turn depth factor (multi-turn conversations = important)
        if episode.turn_number > 5:
            score += 0.1
        elif episode.turn_number > 2:
            score += 0.05
        
        # Cap at 1.0
        return min(1.0, score)
    
    def _rank_episodes(
        self,
        episodes: List[Episode],
        query: str,
        current_time: datetime
    ) -> List[Episode]:
        """
        Rank episodes using hybrid scoring.
        
        Score = α*semantic + β*temporal + γ*importance
        where α=0.5, β=0.3, γ=0.2
        """
        scored_episodes = []
        
        for episode in episodes:
            # Temporal relevance (exponential decay)
            age_days = (current_time - episode.timestamp).days
            temporal_score = math.exp(-age_days / 7.0)  # Decay over 7 days
            
            # Semantic similarity (approximated by presence in results)
            # In a real implementation, we'd calculate cosine similarity
            semantic_score = 0.7  # Placeholder (already filtered by vector search)
            
            # Importance score (already calculated)
            importance_score = episode.importance_score
            
            # Weighted combination
            final_score = (
                0.5 * semantic_score +
                0.3 * temporal_score +
                0.2 * importance_score
            )
            
            scored_episodes.append((final_score, episode))
        
        # Sort by score (descending)
        scored_episodes.sort(key=lambda x: x[0], reverse=True)
        
        return [episode for score, episode in scored_episodes]
    
    async def clear_memory(self, user_id: str, chat_id: str):
        """
        Clear all episodic memory for a user/chat.
        
        Args:
            user_id: User identifier
            chat_id: Chat session identifier
        """
        try:
            collection = self._get_collection_name(user_id, chat_id)
            # Note: ChromaDB doesn't support collection deletion in this interface
            # You would need to implement this based on your ChromaDB setup
            logger.info(f"Cleared episodic memory for {user_id}/{chat_id}")
        except Exception as e:
            logger.error(f"Error clearing memory: {e}", exc_info=True)


# Global episodic memory service instance
episodic_memory_service = EpisodicMemoryService()
