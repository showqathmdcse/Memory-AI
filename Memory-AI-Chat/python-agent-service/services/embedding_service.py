"""Embedding service for generating text embeddings using Azure OpenAI."""

import logging
from typing import List

from openai import AsyncAzureOpenAI

from config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using Azure OpenAI."""

    def __init__(self):
        """Initialize the embedding service."""
        logger.info(f"Initializing EmbeddingService with endpoint: {settings.azure_openai_endpoint}")
        logger.info(f"API version: {settings.azure_openai_api_version}")
        logger.info(f"Deployment: {settings.azure_openai_embedding_deployment}")
        
        self.client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        self.deployment = settings.azure_openai_embedding_deployment

    async def embed(self, text: str) -> List[float]:
        """
        Generate embeddings for the given text.

        Args:
            text: The text to embed

        Returns:
            List of embedding values
        """
        try:
            logger.debug(f"Generating embedding for text: {text[:100]}...")
            
            response = await self.client.embeddings.create(
                input=text,
                model=self.deployment,
            )
            
            embeddings = response.data[0].embedding
            logger.debug(f"Generated embedding with {len(embeddings)} dimensions")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise RuntimeError(f"Failed to get embeddings: {str(e)}") from e


# Global embedding service instance
embedding_service = EmbeddingService()
