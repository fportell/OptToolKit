"""
Text Revision Service using OpenAI GPT-4.1.

Provides AI-powered text revision and improvement suggestions.
Per FR-007: AI-powered content revision using OpenAI GPT-4.1 models.
"""

import logging
import os
import time
import difflib
from typing import Dict, Any, Optional, List
from openai import OpenAI
from flask import current_app

logger = logging.getLogger(__name__)

# Editing guidelines for text revision
EDITING_GUIDELINES = """**EDITING GUIDELINES:**

## Numbers
- Use Arabic numerals to write the number of cases, units of time, dosing information, etc.
	- e.g., There have been 5 confirmed cases over a 3-month period. These cases have received 2 doses of vaccine.

## Dates
- Acceptable formats: Month Date, Year or Month Date.
	- e.g., January 1, 2022, or January 1.

## Foreign Words
- Remove accents from foreign words, except for French words which should retain their original accents.
	- e.g., Write "Sao Paulo" instead of "São Paulo," "Malaga" instead of "Málaga"
	- e.g., Keep French accents: "Montréal," "Québec," "Saint-Étienne"

## Scientific Names
- All scientific names (genus, species, and subspecies) must be italicized using HTML <em> tags.
- Genus names should be capitalized; species names should be lowercase.
	- e.g., "<em>Escherichia coli</em>" or "<em>E. coli</em>"
	- e.g., "<em>Plasmodium falciparum</em>"
	- e.g., "<em>Aedes aegypti</em>" (the mosquito species)
	- e.g., "Infection with <em>Salmonella</em> species was confirmed"
- Verify that all organism names, virus names, and bacterial species are properly formatted with italics.

## Tense Usage
- Use appropriate English tenses based on whether there is a connection with the present:
	- **Simple Past**: For completed actions with no present connection
		- e.g., "The study concluded in 2020"
	- **Present Perfect**: For completed actions with present relevance or ongoing effects
		- e.g., "The research has shown significant improvements in patient outcomes"
	- **Present Perfect Continuous**: For actions that started in the past and continue to the present
		- e.g., "Researchers have been monitoring patient progress for six months"
	- **Past Perfect**: For actions completed before another past action
		- e.g., "Participants had completed the baseline assessment before treatment began"
	- **Past Perfect Continuous**: For ongoing actions in the past that were completed before another past action
		- e.g., "Scientists had been studying the virus for years before the outbreak occurred"
	- **Past Continuous**: For ongoing actions in the past
		- e.g., "Researchers were collecting data throughout the trial period"
"""


class RevisionService:
    """
    AI-powered text revision service using OpenAI GPT-4.1.

    Provides text improvement, grammar correction, and clarity enhancement.
    """

    # Available models
    AVAILABLE_MODELS = {
        'gpt-4.1': {
            'name': 'GPT-4.1',
            'description': 'Superior quality - Most advanced language model'
        },
        'gpt-4.1-mini': {
            'name': 'GPT-4.1-mini',
            'description': 'Very good quality - Optimized GPT-4.1 variant'
        }
    }

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the revision service.

        Args:
            api_key: OpenAI API key. If None, will try to get from current_app.config
        """
        self.client = None
        self.api_key = api_key

    def _ensure_client(self):
        """Ensure OpenAI client is initialized."""
        if self.client is None:
            # Use provided API key or get from current_app
            api_key = self.api_key
            if not api_key:
                try:
                    api_key = current_app.config.get('OPENAI_API_KEY')
                except RuntimeError:
                    # If we're outside application context, try environment variable
                    api_key = os.getenv('OPENAI_API_KEY')

            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured")

            # Debug log
            logger.info(f"Initializing OpenAI client with api_key type: {type(api_key)}, length: {len(api_key) if api_key else 0}")

            # Ensure api_key is a string and strip whitespace/quotes
            if isinstance(api_key, str):
                api_key = api_key.strip().strip('"').strip("'")

            try:
                self.client = OpenAI(api_key=api_key)
                logger.info("Initialized OpenAI client successfully")
            except TypeError as e:
                logger.error(f"TypeError initializing OpenAI client: {e}")
                # Try with minimal parameters
                self.client = OpenAI(api_key=api_key)
                raise

    def revise_text(self,
                    text: str,
                    model_name: str = 'gpt-4.1',
                    use_canadian_english: bool = True) -> Dict[str, Any]:
        """
        Revise text using OpenAI GPT-4.1.

        Args:
            text: The text to revise
            model_name: Model to use ('gpt-4.1' or 'gpt-4.1-mini')
            use_canadian_english: Apply Canadian English spelling and grammar

        Returns:
            dict: Revision results with keys:
                - success: bool
                - revised_text: str (if successful)
                - original_text: str
                - model: str
                - use_canadian_english: bool
                - usage: dict (tokens used)
                - processing_time: float (seconds)
                - error: str (if failed)
        """
        start_time = time.time()

        result = {
            'success': False,
            'original_text': text,
            'revised_text': None,
            'model': model_name,
            'use_canadian_english': use_canadian_english,
            'usage': None,
            'processing_time': 0,
            'error': None
        }

        try:
            # Initialize client
            self._ensure_client()

            # Validate input
            if not text or not text.strip():
                result['error'] = 'Input text is empty'
                return result

            # Check text length
            if len(text) > 50000:  # ~12,500 words
                result['error'] = 'Text is too long (maximum ~12,500 words)'
                return result

            # Validate model
            if model_name not in self.AVAILABLE_MODELS:
                result['error'] = f'Invalid model: {model_name}'
                return result

            # Build prompt
            system_prompt = "You are a professional editor. Correct grammar, improve clarity, and eliminate redundancy. Maintain the original meaning and tone. When formatting scientific names (bacteria, viruses, organisms), you MUST use HTML <em> tags for italics. Return plain text with HTML <em> tags where italics are needed."

            if use_canadian_english:
                user_prompt = f"Here is a revised version with Canadian English, improved clarity, and no redundancy considering these guidelines:\n{EDITING_GUIDELINES}\n**Summary to review:**\n{text}"
            else:
                user_prompt = f"Here is a revised version with improved clarity and no redundancy:\n\n{text}"

            # Make API call
            logger.info(f"Requesting revision (model: {model_name}, canadian: {use_canadian_english}, length: {len(text)} chars)")

            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=min(len(text) * 2, 4000)
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

    def highlight_changes(self, original: str, revised: str) -> str:
        """
        Create HTML with highlighted changes between original and revised text.

        Args:
            original: Original text
            revised: Revised text

        Returns:
            str: HTML string with highlighted changes
                - Deletions: red background (#ffcccc) with strikethrough
                - Additions: green background (#ccffcc) with bold
        """
        d = difflib.Differ()
        diff = list(d.compare(original.split(), revised.split()))

        html_output = []
        for word in diff:
            if word.startswith('- '):
                # Deletion: red background with strikethrough
                html_output.append(f'<span style="background-color: #ffcccc; text-decoration: line-through;">{word[2:]}</span>')
            elif word.startswith('+ '):
                # Addition: green background with bold
                html_output.append(f'<span style="background-color: #ccffcc; font-weight: bold;">{word[2:]}</span>')
            elif word.startswith('  '):
                # Unchanged
                html_output.append(word[2:])

        return ' '.join(html_output)

    def convert_to_markdown(self, text: str) -> str:
        """
        Convert HTML em tags to Markdown italics format.

        Args:
            text: Text with HTML <em> tags

        Returns:
            str: Text with Markdown *italics* format
        """
        import re
        # Convert <em>...</em> to *...*
        markdown_text = re.sub(r'<em>(.*?)</em>', r'*\1*', text)
        return markdown_text


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
        # Try to get API key from current_app, fallback to environment variable
        api_key = None
        try:
            api_key = current_app.config.get('OPENAI_API_KEY')
        except RuntimeError:
            # Outside application context, use environment variable
            api_key = os.getenv('OPENAI_API_KEY')

        _revision_service = RevisionService(api_key=api_key)

    return _revision_service
