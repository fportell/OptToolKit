"""
Retrieval Service for DR Knowledge Chatbot.

Implements hybrid search with cross-encoder re-ranking.
Per chatbot_revised.md: Top-50 hybrid retrieval → re-rank to top-10.
"""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass

from sentence_transformers import CrossEncoder

from app.services.chatbot.vector_store import VectorStore, SearchResult
from app.services.chatbot.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Final retrieval result with event details."""
    event_id: str
    text: str
    score: float
    metadata: Dict[str, Any]


class RetrievalService:
    """Retrieve and rank relevant documents for queries."""

    def __init__(self, vector_store: VectorStore, embedding_service: EmbeddingService):
        """
        Initialize retrieval service.

        Args:
            vector_store: Vector store instance
            embedding_service: Embedding service instance
        """
        self.vector_store = vector_store
        self.embedding_service = embedding_service

        # Initialize cross-encoder for re-ranking
        try:
            # Explicitly specify device='cpu' to avoid meta tensor issues with newer transformers
            self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device='cpu')
            self.reranking_enabled = True
            logger.info("Cross-encoder re-ranker loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load re-ranker: {e}. Re-ranking disabled.")
            self.reranking_enabled = False

    def retrieve(
        self,
        query: str,
        filters: Dict[str, Any] = None,
        top_k: int = 10,
        use_hybrid: bool = True,
        use_reranking: bool = True
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant documents for query.

        Args:
            query: User query
            filters: Metadata filters
            top_k: Number of final results
            use_hybrid: Use hybrid search (semantic + keyword)
            use_reranking: Apply cross-encoder re-ranking

        Returns:
            List of RetrievalResult objects
        """
        # Generate query embedding
        logger.info(f"Retrieval query: '{query}', Filters: {filters}")
        query_embedding = self.embedding_service.embed_single(query)

        # Retrieve candidates
        if use_hybrid:
            # Hybrid search: retrieve top-50 for re-ranking
            candidates = self.vector_store.hybrid_search(
                query=query,
                query_embedding=query_embedding,
                top_k=100,  # Increased to get more candidates for re-ranking
                alpha=0.7,  # 70% semantic, 30% keyword
                filters=filters
            )
        else:
            # Pure semantic search - retrieve more candidates for better coverage
            candidates = self.vector_store.semantic_search(
                query_embedding=query_embedding,
                top_k=100,  # Increased from 50 to cast wider net
                filters=filters
            )

        logger.info(f"Retrieved {len(candidates)} candidates before re-ranking")
        if len(candidates) > 0:
            logger.info(f"Top 3 candidates: {[(c.metadata.get('event_id'), c.metadata.get('hazard'), round(c.score, 3)) for c in candidates[:3]]}")

        # Re-rank if enabled
        if use_reranking and self.reranking_enabled and len(candidates) > 0:
            logger.info(f"Re-ranking {len(candidates)} candidates to top {top_k}")
            results = self.rerank(query, candidates, top_k=top_k)
            logger.info(f"After re-ranking: {len(results)} results. Top scores: {[round(r.score, 3) for r in results[:3]]}")
        else:
            results = candidates[:top_k]
            logger.info(f"No re-ranking, returning top {len(results)} candidates")

        # Convert to RetrievalResult
        retrieval_results = [
            RetrievalResult(
                event_id=r.metadata.get('event_id', 'unknown'),
                text=r.text,
                score=r.score,
                metadata=r.metadata
            )
            for r in results
        ]

        logger.info(f"Retrieval returned {len(retrieval_results)} results")
        return retrieval_results

    def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        Re-rank results using cross-encoder.

        Args:
            query: User query
            results: Initial search results
            top_k: Number of results to return after re-ranking

        Returns:
            Re-ranked SearchResult list
        """
        if not self.reranking_enabled:
            return results[:top_k]

        # Prepare query-document pairs
        pairs = [(query, result.text) for result in results]

        # Score with cross-encoder
        scores = self.reranker.predict(pairs)

        # Combine results with new scores
        reranked = sorted(
            zip(results, scores),
            key=lambda x: x[1],
            reverse=True
        )

        # Update scores and return top-k
        final_results = []
        for result, score in reranked[:top_k]:
            result.score = float(score)  # Update with re-ranker score
            final_results.append(result)

        logger.debug(f"Re-ranked {len(results)} results to top-{top_k}")
        return final_results

    def format_context(
        self,
        results: List[RetrievalResult],
        include_metadata: bool = True
    ) -> str:
        """
        Format retrieval results as context for LLM.

        Args:
            results: Retrieval results
            include_metadata: Include event metadata in context

        Returns:
            Formatted context string
        """
        context_parts = []

        for i, result in enumerate(results, 1):
            context_parts.append(f"=== Document {i} (Event #{result.event_id}) ===\n")

            if include_metadata:
                meta = result.metadata
                context_parts.append(f"Date: {meta.get('date', 'Unknown')}\n")
                context_parts.append(f"Location: {meta.get('location', 'Unknown')}\n")
                context_parts.append(f"Disease: {meta.get('hazard', 'Unknown')}\n\n")

            context_parts.append(result.text)
            context_parts.append("\n\n")

        return "".join(context_parts)
