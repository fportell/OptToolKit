"""
DR Knowledge Chatbot Service.

Provides conversational AI interface to DR knowledge base using
sentence-transformers for semantic search and OpenAI for response generation.
Per FR-009: Interactive chatbot with natural language querying.
"""

import logging
import time
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
from openai import OpenAI
from flask import current_app

logger = logging.getLogger(__name__)


class DRChatbotService:
    """
    DR knowledge base chatbot using semantic search and OpenAI.

    Combines sentence-transformers for finding relevant context and
    OpenAI GPT-4 for generating natural language responses.
    """

    def __init__(self):
        """Initialize the chatbot service."""
        self.model = None  # Sentence transformer model
        self.openai_client = None
        self.gpt_model = None
        self.knowledge_base = None
        self.embeddings = None
        self.documents = []

    def _ensure_sentence_model(self):
        """Ensure sentence transformer model is loaded."""
        if self.model is None:
            logger.info("Loading sentence-transformer model...")
            # Use a compact, efficient model
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Sentence-transformer model loaded")

    def _ensure_openai_client(self):
        """Ensure OpenAI client is initialized."""
        if self.openai_client is None:
            api_key = current_app.config.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured")

            self.openai_client = OpenAI(api_key=api_key)
            self.gpt_model = current_app.config.get('CHATBOT_MODEL', 'gpt-4')
            logger.info(f"Initialized OpenAI client with model: {self.gpt_model}")

    def load_knowledge_base(self, file_path: Path) -> Dict[str, Any]:
        """
        Load DR knowledge base from Excel file.

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

            # Read Excel file
            df = pd.read_excel(file_path)

            # Extract documents (combine relevant columns into text)
            self.documents = []

            for idx, row in df.iterrows():
                # Combine all non-null string fields into a document
                doc_parts = []

                for col in df.columns:
                    value = row[col]
                    if pd.notna(value) and isinstance(value, (str, int, float)):
                        doc_parts.append(f"{col}: {value}")

                if doc_parts:
                    document = " | ".join(doc_parts)
                    self.documents.append({
                        'text': document,
                        'row_index': idx,
                        'data': row.to_dict()
                    })

            # Generate embeddings
            self._ensure_sentence_model()

            logger.info(f"Generating embeddings for {len(self.documents)} documents...")
            doc_texts = [doc['text'] for doc in self.documents]
            self.embeddings = self.model.encode(doc_texts, convert_to_numpy=True)

            self.knowledge_base = df
            result['success'] = True
            result['document_count'] = len(self.documents)

            logger.info(f"Knowledge base loaded: {result['document_count']} documents")

        except FileNotFoundError:
            result['error'] = f'Knowledge base file not found: {file_path}'
            logger.error(result['error'])
        except Exception as e:
            result['error'] = f'Error loading knowledge base: {str(e)}'
            logger.error(result['error'], exc_info=True)

        return result

    def semantic_search(self,
                       query: str,
                       top_k: int = 5,
                       similarity_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """
        Perform semantic search on knowledge base.

        Args:
            query: User query
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            list: List of result dictionaries with keys:
                - text: Document text
                - score: Similarity score (0-1)
                - data: Original row data
        """
        if not self.documents or self.embeddings is None:
            logger.warning("Knowledge base not loaded")
            return []

        self._ensure_sentence_model()

        # Encode query
        query_embedding = self.model.encode([query], convert_to_numpy=True)[0]

        # Calculate cosine similarities
        similarities = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Get top-k results above threshold
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= similarity_threshold:
                results.append({
                    'text': self.documents[idx]['text'],
                    'score': score,
                    'data': self.documents[idx]['data']
                })

        logger.info(f"Semantic search for '{query[:50]}...': {len(results)} results above threshold")

        return results

    def chat(self,
             message: str,
             chat_history: Optional[List[Dict[str, str]]] = None,
             include_context: bool = True) -> Dict[str, Any]:
        """
        Generate chatbot response to user message.

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
            self._ensure_openai_client()

            # Perform semantic search if context is requested
            if include_context and self.documents:
                search_results = self.semantic_search(message, top_k=3)
                result['context_used'] = search_results

                # Build context string
                if search_results:
                    context_parts = []
                    for idx, res in enumerate(search_results, 1):
                        context_parts.append(f"[Source {idx}] {res['text']}")

                    context_str = "\n\n".join(context_parts)

                    system_prompt = f"""You are a helpful assistant with access to a DR (Discrepancy Report) knowledge base.
Use the following context to answer the user's question. If the context doesn't contain relevant information, say so and provide a general helpful response.

Context from knowledge base:
{context_str}

Guidelines:
- Answer based on the provided context when relevant
- Be concise and specific
- If asked about data in the knowledge base, reference it specifically
- If the context doesn't help, acknowledge that and provide general assistance
- Use natural, conversational language"""
                else:
                    system_prompt = """You are a helpful assistant for a DR (Discrepancy Report) tracking system.
The knowledge base search didn't find directly relevant information for this query.
Provide general helpful guidance about DR tracking, discrepancy management, or related topics."""
            else:
                system_prompt = """You are a helpful assistant for a DR (Discrepancy Report) tracking system.
Help users understand DR tracking, discrepancy management, and related topics."""

            # Build messages
            messages = [{"role": "system", "content": system_prompt}]

            # Add chat history (limit to last 10 messages)
            if chat_history:
                messages.extend(chat_history[-10:])

            # Add current message
            messages.append({"role": "user", "content": message})

            # Generate response
            logger.info(f"Generating response for: '{message[:50]}...'")

            response = self.openai_client.chat.completions.create(
                model=self.gpt_model,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
                top_p=1.0
            )

            ai_response = response.choices[0].message.content.strip()

            result['response'] = ai_response
            result['success'] = True

            logger.info(f"Response generated ({len(ai_response)} chars)")

        except Exception as e:
            logger.error(f"Error generating chat response: {e}", exc_info=True)
            result['error'] = f'Chat failed: {str(e)}'

        finally:
            result['processing_time'] = time.time() - start_time

        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        Get knowledge base statistics.

        Returns:
            dict: Statistics including document count, model info, etc.
        """
        return {
            'loaded': self.knowledge_base is not None,
            'document_count': len(self.documents) if self.documents else 0,
            'model_loaded': self.model is not None,
            'model_name': 'all-MiniLM-L6-v2' if self.model else None,
            'embedding_dimension': self.embeddings.shape[1] if self.embeddings is not None else None
        }


# Global service instance
_chatbot_service: Optional[DRChatbotService] = None


def get_chatbot_service() -> DRChatbotService:
    """
    Get the global chatbot service instance.

    Returns:
        DRChatbotService: The service instance
    """
    global _chatbot_service

    if _chatbot_service is None:
        _chatbot_service = DRChatbotService()

        # Auto-load knowledge base if configured
        kb_path = current_app.config.get('CHATBOT_KNOWLEDGE_BASE_PATH')
        if kb_path and Path(kb_path).exists():
            logger.info(f"Auto-loading knowledge base from config: {kb_path}")
            result = _chatbot_service.load_knowledge_base(Path(kb_path))
            if result['success']:
                logger.info(f"Knowledge base loaded: {result['document_count']} documents")
            else:
                logger.warning(f"Failed to auto-load knowledge base: {result.get('error')}")

    return _chatbot_service
