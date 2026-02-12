"""ChromaDB service for vector storage and retrieval."""

import logging
import re
from typing import Dict, List, Optional
from uuid import uuid4

import httpx

from config import settings

logger = logging.getLogger(__name__)


class ChromaService:
    """Service for interacting with ChromaDB."""

    def __init__(self):
        """Initialize the ChromaDB service."""
        self.chroma_url = settings.chroma_url
        self.collection_cache: Dict[str, str] = {}
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    def _sanitize_collection_name(self, name: str) -> str:
        """
        Sanitize collection name to meet ChromaDB requirements.
        
        Requirements:
        - 3-63 characters
        - Starts and ends with alphanumeric
        - Contains only alphanumeric, underscores, or hyphens
        
        Args:
            name: Original collection name
            
        Returns:
            Sanitized collection name
        """
        if not name:
            return "default"
        
        # Replace invalid characters with underscores
        sanitized = name.lower()
        sanitized = re.sub(r'[^a-z0-9_-]', '_', sanitized)
        sanitized = re.sub(r'_{2,}', '_', sanitized)
        sanitized = re.sub(r'^[^a-z0-9]+', '', sanitized)
        sanitized = re.sub(r'[^a-z0-9]+$', '', sanitized)
        
        if not sanitized:
            sanitized = "user"
        
        if not re.match(r'^[a-z0-9]', sanitized):
            sanitized = "u" + sanitized
        
        if len(sanitized) > 58:
            sanitized = sanitized[:58]
        
        while len(sanitized) < 3:
            sanitized += "0"
        
        return sanitized

    async def _get_collection_id(self, collection_name: str) -> Optional[str]:
        """
        Get or create a collection and return its ID.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Collection ID or None if failed
        """
        # Check cache first
        if collection_name in self.collection_cache:
            return self.collection_cache[collection_name]
        
        try:
            url = f"{self.chroma_url}/api/v1/collections"
            payload = {
                "name": collection_name,
                "metadata": {"description": "Conversation memory"},
                "get_or_create": True,
            }
            
            logger.debug(f"Getting/creating collection: {collection_name}")
            response = await self.client.post(url, json=payload)
            
            if response.status_code in (200, 201):
                data = response.json()
                collection_id = data["id"]
                self.collection_cache[collection_name] = collection_id
                logger.info(f"Got/created collection '{collection_name}' with ID: {collection_id}")
                return collection_id
            else:
                logger.error(f"Failed to get/create collection. Status: {response.status_code}, Body: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"ChromaDB get/create collection error: {e}")
            return None

    async def add_document(
        self,
        collection_name: str,
        document_id: str,
        text: str,
        embedding: List[float],
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Add a document to a collection.
        
        Args:
            collection_name: Name of the collection
            document_id: Unique ID for the document
            text: Document text
            embedding: Document embedding vector
            metadata: Optional metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        collection_id = await self._get_collection_id(collection_name)
        if not collection_id:
            logger.error(f"Failed to get collection ID for: {collection_name}")
            return False
        
        try:
            url = f"{self.chroma_url}/api/v1/collections/{collection_id}/add"
            payload = {
                "ids": [document_id],
                "documents": [text],
                "embeddings": [embedding],
                "metadatas": [metadata or {}],
            }
            
            response = await self.client.post(url, json=payload)
            
            if response.status_code == 201:
                logger.debug(f"Added document to collection '{collection_name}'")
                return True
            else:
                logger.error(f"Failed to add document. Status: {response.status_code}, Body: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"ChromaDB add error: {e}")
            return False

    async def query(
        self,
        collection_name: str,
        embedding: List[float],
        n_results: int = 6,
    ) -> List[str]:
        """
        Query a collection for similar documents.
        
        Args:
            collection_name: Name of the collection
            embedding: Query embedding vector
            n_results: Number of results to return
            
        Returns:
            List of document texts
        """
        collection_id = await self._get_collection_id(collection_name)
        if not collection_id:
            logger.error(f"Failed to get collection ID for: {collection_name}")
            return []
        
        try:
            url = f"{self.chroma_url}/api/v1/collections/{collection_id}/query"
            payload = {
                "query_embeddings": [embedding],
                "n_results": n_results,
            }
            
            response = await self.client.post(url, json=payload)
            
            if response.status_code != 200:
                logger.error(f"ChromaDB query failed. Status: {response.status_code}")
                return []
            
            data = response.json()
            
            if "documents" not in data or not data["documents"]:
                logger.debug("No documents found in ChromaDB response")
                return []
            
            documents = data["documents"][0] if data["documents"] else []
            return documents
            
        except Exception as e:
            logger.error(f"ChromaDB query error: {e}")
            return []


# Global ChromaDB service instance
chroma_service = ChromaService()
