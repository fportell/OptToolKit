"""
RAG Orchestrator Service for DR Knowledge Chatbot.

Replaces the old chatbot_service.py with modern RAG architecture.
Provides same interface for backward compatibility with existing routes.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
from flask import current_app

from app.services.chatbot.data_processor import DataProcessor
from app.services.chatbot.embedding_service import EmbeddingService
from app.services.chatbot.vector_store import VectorStore
from app.services.chatbot.query_processor import QueryProcessor
from app.services.chatbot.retrieval_service import RetrievalService
from app.services.chatbot.generation_service import GenerationService
from app.services.chatbot.metadata_service import MetadataService
from app.services.chatbot.update_service import UpdateService

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """
    Orchestrates RAG pipeline for DR Knowledge Chatbot.

    Provides same interface as old DRChatbotService for backward compatibility.
    """

    def __init__(self, data_dir: str = "app/data/chatbot"):
        """
        Initialize RAG orchestrator.

        Args:
            data_dir: Data directory for chatbot
        """
        self.data_dir = data_dir

        # Initialize all services
        self.data_processor = DataProcessor()
        self.embedding_service = EmbeddingService(
            api_key=None,  # Will load from env
            cache_dir=f"{data_dir}/embedding_cache"
        )
        self.vector_store = VectorStore(
            persist_directory=f"{data_dir}/chroma_db"
        )
        self.query_processor = QueryProcessor()
        self.retrieval_service = RetrievalService(
            vector_store=self.vector_store,
            embedding_service=self.embedding_service
        )
        self.generation_service = GenerationService(api_key=None)  # Will load from env
        self.metadata_service = MetadataService(data_dir=data_dir)
        self.update_service = UpdateService(
            data_processor=self.data_processor,
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
            metadata_service=self.metadata_service,
            data_dir=data_dir
        )

        # Legacy compatibility
        self.knowledge_base = None

        logger.info("RAG Orchestrator initialized")

    def load_knowledge_base(self, file_path: Path) -> Dict[str, Any]:
        """
        Load DR knowledge base from Excel file.

        This replaces the old in-memory loading with ChromaDB persistence.
        If the database is already loaded in ChromaDB, this is a no-op.

        Args:
            file_path: Path to Excel knowledge base file

        Returns:
            dict: Load result with keys:
                - success: bool
                - document_count: int
                - error: str (if failed)
        """
        result = {
            'success': False,
            'document_count': 0,
            'error': None
        }

        try:
            logger.info(f"Loading knowledge base from: {file_path}")

            # Check if already loaded
            stats = self.metadata_service.get_statistics()
            if stats['total_chunks'] > 0:
                logger.info("Knowledge base already loaded in ChromaDB")
                result['success'] = True
                result['document_count'] = stats['total_events']
                self.knowledge_base = True  # Flag as loaded
                return result

            # Load and process Excel file
            df = self.data_processor.load_excel(str(file_path))

            # Validate
            validation = self.data_processor.validate_data(df)
            if not validation['valid']:
                result['error'] = f"Validation failed: {', '.join(validation['errors'])}"
                return result

            # Extract events and chunks
            events = self.data_processor.extract_events(df)
            chunks = self.data_processor.chunk_events(events)

            logger.info(f"Extracted {len(events)} events, {len(chunks)} chunks")

            # Generate embeddings (use batch API for efficiency)
            if len(chunks) >= 100:
                logger.info("Using Batch API for embeddings (>100 chunks)")
                texts = [chunk.text for chunk in chunks]
                embeddings_dict = self.embedding_service.embed_batch(texts)

                # Check for pending batch
                if 'batch_job' in embeddings_dict and embeddings_dict.get('pending'):
                    result['error'] = "Batch processing started - knowledge base will be ready in 10-20 minutes"
                    return result

                # Extract embeddings in order
                embeddings = []
                for chunk in chunks:
                    text_hash = self.embedding_service._text_hash(chunk.text)
                    embeddings.append(embeddings_dict[text_hash])
            else:
                logger.info("Using direct API for embeddings (<100 chunks)")
                embeddings = [self.embedding_service.embed_single(chunk.text) for chunk in chunks]

            # Create collection and add documents
            self.vector_store.create_collection(reset=True)
            self.vector_store.add_documents(chunks, embeddings)

            # Update metadata
            self.metadata_service.record_update(
                version_id="v_initial",
                source_file=str(file_path),
                total_events=len(events),
                total_chunks=len(chunks),
                changes={'new': len(events), 'modified': 0, 'deleted': 0},
                uploaded_by="system",
                status="completed"
            )

            self.knowledge_base = True
            result['success'] = True
            result['document_count'] = len(events)

            logger.info(f"Knowledge base loaded: {len(events)} events, {len(chunks)} chunks")

        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}", exc_info=True)
            result['error'] = str(e)

        return result

    def semantic_search(self,
                       query: str,
                       top_k: int = 5,
                       similarity_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """
        Perform semantic search on knowledge base.

        For backward compatibility with old interface.

        Args:
            query: User query
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            list: List of result dictionaries with keys:
                - text: Document text
                - score: Similarity score (0-1)
                - data: Metadata
        """
        try:
            # Use retrieval service
            results = self.retrieval_service.retrieve(
                query=query,
                top_k=top_k,
                use_hybrid=False,  # Pure semantic for backward compatibility
                use_reranking=False
            )

            # Filter by threshold and format
            formatted_results = []
            for res in results:
                if res.score >= similarity_threshold:
                    formatted_results.append({
                        'text': res.text,
                        'score': res.score,
                        'data': res.metadata
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def chat(self,
             message: str,
             chat_history: Optional[List[Dict[str, str]]] = None,
             include_context: bool = True) -> Dict[str, Any]:
        """
        Generate chatbot response to user message.

        Uses full RAG pipeline with hybrid search and re-ranking.

        Args:
            message: User message
            chat_history: Previous conversation history (list of {role, content} dicts)
            include_context: Whether to include knowledge base context

        Returns:
            dict: Response with keys:
                - success: bool
                - response: str (AI response)
                - context_used: list of relevant documents
                - processing_time: float (seconds)
                - error: str (if failed)
        """
        start_time = time.time()

        result = {
            'success': False,
            'response': None,
            'context_used': [],
            'processing_time': 0,
            'error': None
        }

        try:
            # Parse query and extract filters
            parsed_query = self.query_processor.parse_query(message)
            logger.info(f"Parsed query - Original: '{parsed_query.original}', Enhanced: '{parsed_query.enhanced}', Filters: {parsed_query.filters}")

            # Retrieve relevant documents
            if include_context:
                # Try with original query (query enhancement might be hurting retrieval)
                retrieved_docs = self.retrieval_service.retrieve(
                    query=parsed_query.original,  # Using original query for better matching
                    filters=parsed_query.filters,
                    top_k=10,
                    use_hybrid=False,  # Disabled hybrid search due to ChromaDB embedding dimension mismatch
                    use_reranking=True
                )

                logger.info(f"Retrieved {len(retrieved_docs)} documents. Scores: {[round(doc.score, 3) for doc in retrieved_docs[:5]]}")
                if len(retrieved_docs) > 0:
                    logger.info(f"Top result: Event {retrieved_docs[0].metadata.get('event_id')}, Hazard: {retrieved_docs[0].metadata.get('hazard')}, Score: {retrieved_docs[0].score:.3f}")
                else:
                    logger.warning("No documents retrieved! Database might be empty or query is too restrictive.")

                # Format for legacy interface
                result['context_used'] = [
                    {
                        'text': doc.text,
                        'score': doc.score,
                        'data': doc.metadata
                    }
                    for doc in retrieved_docs
                ]
            else:
                retrieved_docs = []

            # Generate response
            generation_result = self.generation_service.generate_response(
                query=message,
                retrieved_docs=retrieved_docs,
                conversation_history=chat_history
            )

            result['response'] = generation_result['response']
            result['success'] = True

            logger.info(f"Chat completed: {len(retrieved_docs)} docs retrieved, "
                       f"{len(generation_result['response'])} chars generated")

        except Exception as e:
            logger.error(f"Chat failed: {e}", exc_info=True)
            result['error'] = str(e)

        finally:
            result['processing_time'] = time.time() - start_time

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.

        Returns:
            dict: Statistics including document count, model info, etc.
        """
        logger.info("Getting RAG stats...")
        metadata_stats = self.metadata_service.get_statistics()
        logger.info(f"Metadata stats: {metadata_stats}")

        # Also check ChromaDB collection directly as fallback
        is_loaded = metadata_stats['total_chunks'] > 0

        # Double-check by trying to get collection info from ChromaDB
        try:
            # First, list all collections to see what exists
            all_collections = self.vector_store.client.list_collections()
            logger.info(f"Available ChromaDB collections: {[c.name for c in all_collections]}")

            collection = self.vector_store.client.get_collection(self.vector_store.collection_name)
            chroma_count = collection.count()
            logger.info(f"ChromaDB collection count: {chroma_count}, metadata shows loaded: {is_loaded}")

            if chroma_count > 0 and not is_loaded:
                # ChromaDB has data but metadata doesn't - sync metadata from ChromaDB
                logger.warning(f"ChromaDB has {chroma_count} chunks but metadata shows 0 - syncing metadata")
                if self.metadata_service.sync_from_chromadb(self.vector_store):
                    # Reload stats after sync
                    metadata_stats = self.metadata_service.get_statistics()
                    is_loaded = True
                    logger.info("Metadata synced successfully")
                else:
                    # Sync failed, but still show as loaded based on ChromaDB
                    is_loaded = True
                    logger.warning("Metadata sync failed, but showing as loaded based on ChromaDB")
        except Exception as e:
            logger.error(f"Could not check ChromaDB collection: {e}", exc_info=True)

        return {
            'loaded': is_loaded,
            'document_count': metadata_stats['total_events'],
            'chunk_count': metadata_stats['total_chunks'],
            'model_loaded': True,
            'model_name': 'text-embedding-3-small',
            'embedding_dimension': 1536,
            'last_update': metadata_stats.get('last_update'),
            'unique_hazards': metadata_stats.get('unique_hazards', 0),
            'unique_locations': metadata_stats.get('unique_locations', 0)
        }


# Global service instance
_rag_orchestrator: Optional[RAGOrchestrator] = None


def get_chatbot_service() -> RAGOrchestrator:
    """
    Get the global RAG orchestrator instance.

    Replaces get_chatbot_service() from old implementation.

    Returns:
        RAGOrchestrator: The service instance
    """
    global _rag_orchestrator

    if _rag_orchestrator is None:
        _rag_orchestrator = RAGOrchestrator()

        # Auto-load knowledge base if configured
        kb_path = current_app.config.get('CHATBOT_KNOWLEDGE_BASE_PATH')
        if kb_path and Path(kb_path).exists():
            logger.info(f"Auto-loading knowledge base from config: {kb_path}")
            result = _rag_orchestrator.load_knowledge_base(Path(kb_path))
            if result['success']:
                logger.info(f"Knowledge base loaded: {result['document_count']} events")
            else:
                logger.warning(f"Failed to auto-load knowledge base: {result.get('error')}")

    return _rag_orchestrator
