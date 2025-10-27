"""
DR Knowledge Chatbot Service.

Modern RAG implementation using ChromaDB, OpenAI embeddings, and GPT-4o.
Replaces deprecated Assistants API with direct control over RAG pipeline.

This module provides backward compatibility with existing routes by
re-exporting the RAG orchestrator.
"""

# Re-export RAG orchestrator for backward compatibility
from app.services.chatbot.rag_orchestrator import (
    RAGOrchestrator,
    get_chatbot_service
)

# For backward compatibility, alias RAGOrchestrator as DRChatbotService
DRChatbotService = RAGOrchestrator

__all__ = ['RAGOrchestrator', 'DRChatbotService', 'get_chatbot_service']
