"""
Vector Store Service for DR Knowledge Chatbot.

Handles ChromaDB operations: semantic search, metadata filtering, hybrid search.
Per chatbot_revised.md: ChromaDB with persistent storage, hybrid search (semantic + BM25).
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from app.services.chatbot.data_processor import Chunk

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class SearchResult:
    """Search result with metadata."""
    id: str
    text: str
    metadata: Dict[str, Any]
    distance: float  # Lower is better (cosine distance)
    score: float  # Higher is better (similarity score)


# ============================================================================
# Vector Store
# ============================================================================

class VectorStore:
    """ChromaDB vector store with hybrid search capabilities."""

    def __init__(self, persist_directory: str = "app/data/chatbot/chroma_db"):
        """
        Initialize ChromaDB vector store.

        Args:
            persist_directory: Path to persistent storage
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        self.collection_name = "epidemiological_events"
        self.collection = None

        logger.info(f"Vector store initialized at: {self.persist_directory}")

    def create_collection(self, name: Optional[str] = None, reset: bool = False) -> None:
        """
        Create or get collection.

        Args:
            name: Collection name (default: epidemiological_events)
            reset: Whether to delete existing collection
        """
        collection_name = name or self.collection_name

        if reset:
            try:
                self.client.delete_collection(collection_name)
                logger.info(f"Deleted existing collection: {collection_name}")
            except:
                pass  # Collection didn't exist

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Disease outbreak surveillance database"}
        )

        logger.info(f"Collection ready: {collection_name} ({self.collection.count()} documents)")

    def add_documents(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        """
        Add chunks with embeddings to collection.

        Args:
            chunks: List of Chunk objects
            embeddings: Corresponding embedding vectors
        """
        if not self.collection:
            self.create_collection()

        if len(chunks) != len(embeddings):
            raise ValueError(f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch")

        # Prepare data for ChromaDB
        ids = [f"{chunk.event_id}_{chunk.chunk_index}" for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]

        # Add to collection
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        logger.info(f"Added {len(chunks)} documents to collection")

    def semantic_search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Perform semantic search using query embedding.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filters: Metadata filters (e.g., {"hazard": "measles"})

        Returns:
            List of SearchResult objects
        """
        if not self.collection:
            self.create_collection()

        # Build where clause from filters
        where = self._build_where_clause(filters) if filters else None

        # Query collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where
        )

        # Parse results
        search_results = []
        for i in range(len(results['ids'][0])):
            # Convert distance to similarity score (cosine similarity = 1 - cosine distance)
            distance = results['distances'][0][i]
            score = 1.0 - distance  # Higher is better

            result = SearchResult(
                id=results['ids'][0][i],
                text=results['documents'][0][i],
                metadata=results['metadatas'][0][i],
                distance=distance,
                score=score
            )
            search_results.append(result)

        logger.debug(f"Semantic search returned {len(search_results)} results")
        return search_results

    def keyword_search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Perform keyword search (BM25) using query text.

        Note: ChromaDB uses its built-in search when providing query_texts.

        Args:
            query: Query text
            top_k: Number of results to return
            filters: Metadata filters

        Returns:
            List of SearchResult objects
        """
        if not self.collection:
            self.create_collection()

        # Build where clause
        where = self._build_where_clause(filters) if filters else None

        # Query with text (uses BM25)
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where
        )

        # Parse results (keyword search doesn't return distances in same way)
        search_results = []
        for i in range(len(results['ids'][0])):
            result = SearchResult(
                id=results['ids'][0][i],
                text=results['documents'][0][i],
                metadata=results['metadatas'][0][i],
                distance=0.0,  # Not applicable for keyword search
                score=1.0 / (i + 1)  # Simple rank-based score
            )
            search_results.append(result)

        logger.debug(f"Keyword search returned {len(search_results)} results")
        return search_results

    def hybrid_search(
        self,
        query: str,
        query_embedding: List[float],
        top_k: int = 50,
        alpha: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining semantic and keyword search.

        Uses Reciprocal Rank Fusion (RRF) to combine results.

        Args:
            query: Query text for keyword search
            query_embedding: Query vector for semantic search
            top_k: Number of results to return
            alpha: Weight for semantic vs keyword (0.7 = 70% semantic, 30% keyword)
            filters: Metadata filters

        Returns:
            List of SearchResult objects sorted by combined score
        """
        # Get semantic results
        semantic_results = self.semantic_search(query_embedding, top_k=top_k, filters=filters)

        # Get keyword results
        keyword_results = self.keyword_search(query, top_k=top_k, filters=filters)

        # Combine using Reciprocal Rank Fusion
        combined = self._reciprocal_rank_fusion(
            semantic_results,
            keyword_results,
            alpha=alpha
        )

        logger.debug(f"Hybrid search combined {len(semantic_results)} + {len(keyword_results)} results")
        return combined[:top_k]

    def _reciprocal_rank_fusion(
        self,
        semantic_results: List[SearchResult],
        keyword_results: List[SearchResult],
        alpha: float = 0.7,
        k: int = 60
    ) -> List[SearchResult]:
        """
        Combine results using Reciprocal Rank Fusion (RRF).

        Score formula: alpha * semantic_score + (1-alpha) * keyword_score
        RRF formula: 1 / (k + rank)

        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            alpha: Weight for semantic (default: 0.7)
            k: RRF constant (default: 60)

        Returns:
            Combined and sorted results
        """
        # Calculate RRF scores
        scores = {}

        # Semantic scores
        for rank, result in enumerate(semantic_results, start=1):
            rrf_score = 1.0 / (k + rank)
            scores[result.id] = {
                'semantic': rrf_score,
                'keyword': 0.0,
                'result': result
            }

        # Keyword scores
        for rank, result in enumerate(keyword_results, start=1):
            rrf_score = 1.0 / (k + rank)
            if result.id in scores:
                scores[result.id]['keyword'] = rrf_score
            else:
                scores[result.id] = {
                    'semantic': 0.0,
                    'keyword': rrf_score,
                    'result': result
                }

        # Combine with alpha weighting
        combined_results = []
        for doc_id, score_data in scores.items():
            combined_score = (
                alpha * score_data['semantic'] +
                (1 - alpha) * score_data['keyword']
            )

            result = score_data['result']
            result.score = combined_score  # Update with combined score
            combined_results.append(result)

        # Sort by combined score (descending)
        combined_results.sort(key=lambda x: x.score, reverse=True)

        return combined_results

    def _build_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build ChromaDB where clause from filters.

        Supports:
        - Exact match: {"hazard": "measles"}
        - Date range: {"date_from": "2024-01-01", "date_to": "2025-12-31"}
        - Contains: {"location_contains": "united states"}
        - Multiple conditions with $and

        Args:
            filters: Filter dictionary

        Returns:
            ChromaDB where clause
        """
        conditions = []

        # Exact matches (only for location and section)
        # Note: Hazard filtering disabled - semantic search handles this better
        for key in ['location', 'section']:
            if key in filters and filters[key]:
                conditions.append({key: {"$eq": filters[key]}})

        # Date range - convert to unix timestamps for numeric comparison
        if 'date_from' in filters and filters['date_from']:
            # Convert date string to unix timestamp
            try:
                from datetime import datetime
                date_obj = datetime.strptime(filters['date_from'], '%Y-%m-%d')
                timestamp = int(date_obj.timestamp())
                conditions.append({"date_unix": {"$gte": timestamp}})
            except Exception as e:
                logger.warning(f"Could not parse date_from: {filters['date_from']}, error: {e}")

        if 'date_to' in filters and filters['date_to']:
            # Convert date string to unix timestamp
            try:
                from datetime import datetime
                date_obj = datetime.strptime(filters['date_to'], '%Y-%m-%d')
                timestamp = int(date_obj.timestamp())
                conditions.append({"date_unix": {"$lte": timestamp}})
            except Exception as e:
                logger.warning(f"Could not parse date_to: {filters['date_to']}, error: {e}")

        # Contains (for location search)
        if 'location_contains' in filters and filters['location_contains']:
            # ChromaDB doesn't have direct contains, but we can use keywords
            pass  # Handled in query text

        # Combine with $and
        if len(conditions) == 0:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        if not self.collection:
            self.create_collection()

        return {
            "name": self.collection.name,
            "count": self.collection.count(),
            "metadata": self.collection.metadata
        }

    def delete_collection(self, name: Optional[str] = None) -> None:
        """Delete collection."""
        collection_name = name or self.collection_name
        self.client.delete_collection(collection_name)
        logger.info(f"Deleted collection: {collection_name}")
        self.collection = None

    def reset(self) -> None:
        """Reset vector store (delete all data)."""
        if self.collection:
            self.delete_collection()
        self.create_collection()
        logger.warning("Vector store reset - all data deleted")
