"""
Text Revision Service using OpenAI GPT-4.

Provides AI-powered text revision and improvement suggestions.
Per FR-007: AI-powered content revision using OpenAI GPT-4 models.
"""

import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from openai import OpenAI
from flask import current_app

logger = logging.getLogger(__name__)


class RevisionService:
    """
    AI-powered text revision service using OpenAI GPT-4.

    Provides text improvement, grammar correction, clarity enhancement,
    and style suggestions.
    """

    # Revision types
    REVISION_TYPES = {
        'general': {
            'name': 'General Improvement',
            'description': 'Improve overall quality, grammar, and clarity',
            'system_prompt': (
                "You are an expert editor. Improve the following text by:\n"
                "1. Correcting grammar and spelling errors\n"
                "2. Enhancing clarity and readability\n"
                "3. Improving sentence structure\n"
                "4. Maintaining the original meaning and tone\n"
                "Provide only the revised text without explanations."
            )
        },
        'professional': {
            'name': 'Professional Tone',
            'description': 'Convert to professional business language',
            'system_prompt': (
                "You are an expert business writer. Revise the following text to:\n"
                "1. Use professional, business-appropriate language\n"
                "2. Maintain formal tone\n"
                "3. Improve clarity and conciseness\n"
                "4. Remove casual expressions\n"
                "Provide only the revised text without explanations."
            )
        },
        'concise': {
            'name': 'Make Concise',
            'description': 'Reduce wordiness while preserving meaning',
            'system_prompt': (
                "You are an expert editor specializing in conciseness. Revise the following text to:\n"
                "1. Remove unnecessary words and redundancy\n"
                "2. Make sentences more direct and clear\n"
                "3. Preserve all important information\n"
                "4. Maintain the original tone\n"
                "Provide only the revised text without explanations."
            )
        },
        'detailed': {
            'name': 'Add Detail',
            'description': 'Expand with more context and examples',
            'system_prompt': (
                "You are an expert writer. Enhance the following text by:\n"
                "1. Adding relevant details and context\n"
                "2. Including appropriate examples\n"
                "3. Expanding on key points\n"
                "4. Maintaining clarity and coherence\n"
                "Provide only the revised text without explanations."
            )
        },
        'grammar': {
            'name': 'Grammar Only',
            'description': 'Fix grammar and spelling errors only',
            'system_prompt': (
                "You are an expert proofreader. Correct the following text by:\n"
                "1. Fixing grammar errors\n"
                "2. Correcting spelling mistakes\n"
                "3. Fixing punctuation issues\n"
                "4. NOT changing the writing style or word choice\n"
                "Provide only the corrected text without explanations."
            )
        }
    }

    def __init__(self):
        """Initialize the revision service."""
        self.client = None
        self.model = None

    def _ensure_client(self):
        """Ensure OpenAI client is initialized."""
        if self.client is None:
            api_key = current_app.config.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured")

            self.client = OpenAI(api_key=api_key)
            self.model = current_app.config.get('SUMMARY_REVISION_MODEL', 'gpt-4')

            logger.info(f"Initialized OpenAI client with model: {self.model}")

    def revise_text(self,
                    text: str,
                    revision_type: str = 'general',
                    custom_instructions: Optional[str] = None) -> Dict[str, Any]:
        """
        Revise text using OpenAI GPT-4.

        Args:
            text: The text to revise
            revision_type: Type of revision ('general', 'professional', 'concise', etc.)
            custom_instructions: Optional custom instructions for revision

        Returns:
            dict: Revision results with keys:
                - success: bool
                - revised_text: str (if successful)
                - original_text: str
                - revision_type: str
                - model: str
                - usage: dict (tokens used)
                - processing_time: float (seconds)
                - error: str (if failed)
        """
        start_time = time.time()

        result = {
            'success': False,
            'original_text': text,
            'revised_text': None,
            'revision_type': revision_type,
            'model': None,
            'usage': None,
            'processing_time': 0,
            'error': None
        }

        try:
            # Initialize client
            self._ensure_client()
            result['model'] = self.model

            # Validate input
            if not text or not text.strip():
                result['error'] = 'Input text is empty'
                return result

            # Check text length
            if len(text) > 50000:  # ~12,500 words
                result['error'] = 'Text is too long (maximum ~12,500 words)'
                return result

            # Get system prompt
            if revision_type not in self.REVISION_TYPES:
                result['error'] = f'Invalid revision type: {revision_type}'
                return result

            system_prompt = self.REVISION_TYPES[revision_type]['system_prompt']

            # Add custom instructions if provided
            if custom_instructions:
                system_prompt += f"\n\nAdditional instructions: {custom_instructions}"

            # Make API call
            logger.info(f"Requesting revision (type: {revision_type}, length: {len(text)} chars)")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,  # Lower temperature for more consistent revisions
                max_tokens=4000,  # Allow longer responses
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )

            # Extract revised text
            revised_text = response.choices[0].message.content.strip()

            # Store usage information
            result['usage'] = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }

            result['revised_text'] = revised_text
            result['success'] = True

            logger.info(
                f"Revision complete (tokens: {result['usage']['total_tokens']}, "
                f"time: {time.time() - start_time:.2f}s)"
            )

        except Exception as e:
            logger.error(f"Error during revision: {e}", exc_info=True)
            result['error'] = f'Revision failed: {str(e)}'

        finally:
            result['processing_time'] = time.time() - start_time

        return result

    def compare_texts(self, original: str, revised: str) -> Dict[str, Any]:
        """
        Compare original and revised texts to highlight changes.

        Args:
            original: Original text
            revised: Revised text

        Returns:
            dict: Comparison statistics with keys:
                - original_length: int (characters)
                - revised_length: int (characters)
                - original_words: int
                - revised_words: int
                - length_change: int (characters difference)
                - words_change: int (words difference)
                - length_change_percent: float
                - words_change_percent: float
        """
        original_length = len(original)
        revised_length = len(revised)
        original_words = len(original.split())
        revised_words = len(revised.split())

        length_change = revised_length - original_length
        words_change = revised_words - original_words

        return {
            'original_length': original_length,
            'revised_length': revised_length,
            'original_words': original_words,
            'revised_words': revised_words,
            'length_change': length_change,
            'words_change': words_change,
            'length_change_percent': (length_change / original_length * 100) if original_length > 0 else 0,
            'words_change_percent': (words_change / original_words * 100) if original_words > 0 else 0
        }

    def get_suggestions(self, text: str) -> List[Dict[str, str]]:
        """
        Get improvement suggestions without full revision.

        Args:
            text: The text to analyze

        Returns:
            list: List of suggestion dictionaries with 'category' and 'suggestion' keys
        """
        try:
            self._ensure_client()

            system_prompt = (
                "You are an expert editor. Analyze the following text and provide "
                "3-5 specific, actionable improvement suggestions. Format each suggestion "
                "as 'CATEGORY: Suggestion text'. Categories can be: Grammar, Clarity, "
                "Style, Structure, Tone, etc."
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.5,
                max_tokens=500
            )

            suggestions_text = response.choices[0].message.content.strip()

            # Parse suggestions
            suggestions = []
            for line in suggestions_text.split('\n'):
                line = line.strip()
                if ':' in line and line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        category = parts[0].strip().lstrip('0123456789.-) ')
                        suggestion = parts[1].strip()
                        suggestions.append({
                            'category': category,
                            'suggestion': suggestion
                        })

            logger.info(f"Generated {len(suggestions)} suggestions")
            return suggestions

        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
            return []


# Global service instance
_revision_service: Optional[RevisionService] = None


def get_revision_service() -> RevisionService:
    """
    Get the global revision service instance.

    Returns:
        RevisionService: The service instance
    """
    global _revision_service

    if _revision_service is None:
        _revision_service = RevisionService()

    return _revision_service
