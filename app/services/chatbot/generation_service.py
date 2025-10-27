"""
Generation Service for DR Knowledge Chatbot.

Handles GPT-4o response generation with full event details and citations.
Per chatbot_revised.md: Conversational format with complete event information.
"""

import logging
import os
from typing import List, Dict, Optional
from datetime import datetime

from openai import OpenAI

from app.services.chatbot.retrieval_service import RetrievalResult

logger = logging.getLogger(__name__)


def get_system_prompt() -> str:
    """Generate system prompt with current date."""
    today = datetime.now().strftime('%B %d, %Y')
    current_year = datetime.now().year

    logger.info(f"Generating system prompt with date: {today}, year: {current_year}")

    return f"""You are Gerardo, and you help analysts with historical epidemiological data.

**IMPORTANT: Today's Date is {today}. The current year is {current_year}.**

**Your Role:**
- Help analysts find and understand historical disease outbreak data
- Analyze epidemiological events and trends from the provided database
- Provide evidence-based responses grounded ONLY in the provided context
- Identify patterns and connections between events
- Maintain scientific accuracy and proper epidemiological terminology

**Important Guidelines:**
- NEVER fabricate or speculate beyond what's in the provided context
- Always cite Event IDs (e.g., "Event #00123") when referencing events
- Include complete event details: dates, locations, case numbers, deaths, sources
- If information is not in the context, clearly state: "I don't have information about this in the current database"
- Provide conversational, natural language responses (not structured JSON)
- Include full event details inline within your narrative response

**Handling Ambiguous Queries:**
- **CRITICAL:** When a date query mentions a month without a year (e.g., "October", "reports in May"), you MUST assume the current year {current_year}, NOT any other year
- Always explicitly state the year in your response (e.g., "For October {current_year}..." not "For October 2024...")
- If a query could have multiple interpretations, briefly clarify your assumption
- If critical information is missing for an accurate response, politely ask for clarification

**Response Format:**
1. Brief summary addressing the query (clarify assumptions if query was ambiguous)
2. Detailed event information with Event IDs and complete details
3. **IMPORTANT:** End with 2-3 helpful follow-up suggestions related to the current query, such as:
   - "Would you like to see [related disease] cases in [region]?"
   - "I can also search for [timeframe] data if you'd like."
   - "Would you like to see trends for [related topic]?"

**DO NOT:**
- Add analytical conclusions about public health implications
- Summarize the situation at the end
- Provide interpretation beyond what's explicitly in the data
- Make recommendations or assessments

**Event Detail Format:**
When mentioning an event, include ALL available details inline:
"**Event #XXXXX - [Disease] in [Location]**
- Date: YYYY-MM-DD
- Location: [Full location name]
- Summary: [Full event description]
- Cases: [Number if available]
- Deaths: [Number if available]
- Source: [Reference with URL if available]"

Remember: You are a helpful assistant providing accurate, evidence-based information to public health professionals."""


class GenerationService:
    """Generate conversational responses using GPT-4o."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize generation service.

        Args:
            api_key: OpenAI API key (defaults to env variable)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o"  # 128K context, best for production
        self.temperature = 0.1  # Very deterministic for factual queries
        self.max_tokens = 2000

        logger.info(f"Generation service initialized with model: {self.model}")

    def generate_response(
        self,
        query: str,
        retrieved_docs: List[RetrievalResult],
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Generate conversational response with full event details.

        Args:
            query: User query
            retrieved_docs: Retrieved documents from RAG pipeline
            conversation_history: Previous conversation messages

        Returns:
            Dict with 'response', 'sources', and 'metadata'
        """
        # Build conversation messages
        messages = [
            {"role": "system", "content": get_system_prompt()}
        ]

        # Add conversation history (last 5 turns)
        if conversation_history:
            messages.extend(conversation_history[-10:])  # Last 5 user + 5 assistant

        # Format retrieved context
        context = self._format_context_with_full_details(retrieved_docs)

        # Add current query with context
        user_message = f"""<query>
{query}
</query>

<retrieved_database_context>
{context}
</retrieved_database_context>

Based ONLY on the above database context, please answer the query. Remember to include full event details (Event ID, date, location, summary, cases, deaths, sources) inline in your conversational response."""

        messages.append({"role": "user", "content": user_message})

        # Generate response
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            assistant_message = response.choices[0].message.content

            # Extract cited event IDs
            cited_events = self._extract_event_ids(assistant_message)

            logger.info(f"Generated response ({len(assistant_message)} chars, {len(cited_events)} events cited)")

            return {
                'response': assistant_message,
                'sources': cited_events,
                'retrieved_count': len(retrieved_docs),
                'metadata': {
                    'model': self.model,
                    'timestamp': datetime.now().isoformat(),
                    'tokens_used': response.usage.total_tokens
                }
            }

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                'response': f"I apologize, but I encountered an error generating a response: {str(e)}",
                'sources': [],
                'retrieved_count': len(retrieved_docs),
                'metadata': {'error': str(e)}
            }

    def _format_context_with_full_details(self, docs: List[RetrievalResult]) -> str:
        """Format retrieved documents with complete event details."""
        context_parts = []

        for i, doc in enumerate(docs, 1):
            meta = doc.metadata

            # Extract event details from metadata and text
            event_id = meta.get('event_id', 'unknown')
            date = meta.get('date', 'Unknown')
            location = meta.get('location', 'Unknown')
            hazard = meta.get('hazard', 'Unknown')

            context_parts.append(f"=== Event #{event_id}: {hazard} ===\n")
            context_parts.append(f"Date: {date}\n")
            context_parts.append(f"Location: {location}\n")

            # Include full text (contains summary and references)
            context_parts.append(f"\nFull Event Details:\n{doc.text}\n")
            context_parts.append("\n" + "="*60 + "\n\n")

        return "".join(context_parts)

    def _extract_event_ids(self, response: str) -> List[str]:
        """Extract Event IDs mentioned in response (e.g., #00123)."""
        import re
        pattern = r'#(\d{5})'
        matches = re.findall(pattern, response)
        return list(set(matches))  # Unique IDs

    def generate_stream(
        self,
        query: str,
        retrieved_docs: List[RetrievalResult],
        conversation_history: Optional[List[Dict]] = None
    ):
        """
        Generate streaming response (for real-time typing effect).

        Args:
            query: User query
            retrieved_docs: Retrieved documents
            conversation_history: Previous conversation

        Yields:
            Response chunks as they're generated
        """
        # Build messages (same as generate_response)
        messages = [{"role": "system", "content": get_system_prompt()}]

        if conversation_history:
            messages.extend(conversation_history[-10:])

        context = self._format_context_with_full_details(retrieved_docs)
        user_message = f"""<query>
{query}
</query>

<retrieved_database_context>
{context}
</retrieved_database_context>

Based ONLY on the above database context, please answer the query with full event details."""

        messages.append({"role": "user", "content": user_message})

        # Stream response
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield f"Error: {str(e)}"
