"""
Embedding Service for DR Knowledge Chatbot.

Handles OpenAI embeddings generation with batch processing and caching.
Per chatbot_revised.md: text-embedding-3-small, Batch API for >100 chunks.
"""

import logging
import hashlib
import json
import time
import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

import openai
from openai import OpenAI

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class BatchJob:
    """Batch embedding job tracking."""
    id: str
    status: str  # validating, in_progress, completed, failed, cancelled
    input_file_id: str
    output_file_id: Optional[str] = None
    error_file_id: Optional[str] = None
    created_at: int = 0
    completed_at: Optional[int] = None


# ============================================================================
# Embedding Service
# ============================================================================

class EmbeddingService:
    """Generate embeddings using OpenAI API with caching and batch support."""

    def __init__(self, api_key: Optional[str] = None, cache_dir: str = "app/data/chatbot/embedding_cache"):
        """
        Initialize embedding service.

        Args:
            api_key: OpenAI API key (defaults to env variable)
            cache_dir: Directory for caching embeddings
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "text-embedding-3-small"  # 1536 dimensions, $0.02/1M tokens
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.cache_file = self.cache_dir / "embedding_cache.json"
        self.cache = self._load_cache()

        logger.info(f"Embedding service initialized with model: {self.model}")

    def _load_cache(self) -> Dict[str, List[float]]:
        """Load embedding cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                logger.info(f"Loaded {len(cache)} cached embeddings")
                return cache
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        """Save embedding cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
            logger.debug(f"Saved {len(self.cache)} embeddings to cache")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    def _text_hash(self, text: str) -> str:
        """Calculate MD5 hash of text for caching."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def get_cached_embedding(self, text_hash: str) -> Optional[List[float]]:
        """
        Get cached embedding by text hash.

        Args:
            text_hash: MD5 hash of text

        Returns:
            Embedding vector or None if not cached
        """
        return self.cache.get(text_hash)

    def embed_single(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cache

        Returns:
            Embedding vector (1536 dimensions)
        """
        # Check cache
        text_hash = self._text_hash(text)
        if use_cache:
            cached = self.get_cached_embedding(text_hash)
            if cached is not None:
                logger.debug(f"Cache hit for text hash: {text_hash[:8]}")
                return cached

        # Generate embedding
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            embedding = response.data[0].embedding

            # Cache result
            if use_cache:
                self.cache[text_hash] = embedding
                self._save_cache()

            logger.debug(f"Generated embedding for text ({len(text)} chars)")
            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def embed_batch(self, texts: List[str], use_cache: bool = True) -> Dict[str, List[float]]:
        """
        Generate embeddings for multiple texts.

        Uses direct API for batches below CHATBOT_BATCH_THRESHOLD (default 500).
        Uses Batch API for larger batches (50% cost savings, 10-20 min processing time).

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cache

        Returns:
            Dict mapping text hash to embedding vector
        """
        import sys
        logger.info(f"embed_batch called with {len(texts)} texts, use_cache={use_cache}")
        sys.stdout.flush()

        # Separate cached and uncached texts
        results = {}
        uncached_texts = []
        uncached_hashes = []

        logger.info("Checking cache for existing embeddings...")
        sys.stdout.flush()

        for i, text in enumerate(texts):
            if (i + 1) % 20 == 0:
                logger.info(f"Cache check progress: {i + 1}/{len(texts)}")
                sys.stdout.flush()

            text_hash = self._text_hash(text)
            if use_cache:
                cached = self.get_cached_embedding(text_hash)
                if cached is not None:
                    results[text_hash] = cached
                    continue

            uncached_texts.append(text)
            uncached_hashes.append(text_hash)

        if not uncached_texts:
            logger.info("All embeddings found in cache")
            sys.stdout.flush()
            return results

        logger.info(f"Generating embeddings for {len(uncached_texts)} texts (cache hits: {len(results)})")
        sys.stdout.flush()

        # Check if Flask app context is available to get threshold from config
        try:
            from flask import current_app
            batch_threshold = current_app.config.get('CHATBOT_BATCH_THRESHOLD', 500)
        except:
            # Fallback if not in Flask context
            batch_threshold = 500

        logger.info(f"Batch API threshold: {batch_threshold}, uncached texts: {len(uncached_texts)}")
        sys.stdout.flush()

        # Use direct API for batches below threshold
        if len(uncached_texts) < batch_threshold:
            return self._embed_direct(uncached_texts, uncached_hashes, results, use_cache)

        # Use Batch API for large batches (50% discount)
        logger.info(f"Using Batch API because {len(uncached_texts)} >= {batch_threshold}")
        sys.stdout.flush()
        return self._embed_batch_api(uncached_texts, uncached_hashes, results, use_cache)

    def _embed_direct(self, texts: List[str], hashes: List[str],
                     results: Dict[str, List[float]], use_cache: bool) -> Dict[str, List[float]]:
        """Generate embeddings using direct API (for batches below threshold)."""
        import sys
        import tiktoken

        logger.info(f"_embed_direct: Generating {len(texts)} embeddings via direct API...")
        sys.stdout.flush()

        try:
            # OpenAI API limits: 2048 texts AND 300K tokens per request
            # Split into chunks if needed
            encoding = tiktoken.get_encoding("cl100k_base")

            # Calculate total tokens to determine if we need to split
            total_tokens = sum(len(encoding.encode(text)) for text in texts)
            logger.info(f"Total tokens in batch: {total_tokens:,}")
            sys.stdout.flush()

            # If under 250K tokens (safe buffer), send in one call
            if total_tokens <= 250000:
                logger.info(f"Calling OpenAI embeddings API with {len(texts)} texts ({total_tokens:,} tokens)...")
                sys.stdout.flush()

                response = self.client.embeddings.create(
                    model=self.model,
                    input=texts
                )

                logger.info(f"Received response from OpenAI API")
                sys.stdout.flush()

                for i, embedding_obj in enumerate(response.data):
                    embedding = embedding_obj.embedding
                    text_hash = hashes[i]
                    results[text_hash] = embedding

                    # Cache
                    if use_cache:
                        self.cache[text_hash] = embedding

            else:
                # Split into multiple API calls
                logger.info(f"Batch exceeds 250K tokens, splitting into multiple API calls...")
                sys.stdout.flush()

                chunk_size = 100  # Process 100 texts at a time
                num_chunks = (len(texts) + chunk_size - 1) // chunk_size

                logger.info(f"Splitting {len(texts)} texts into {num_chunks} API calls")
                sys.stdout.flush()

                for chunk_idx in range(num_chunks):
                    start = chunk_idx * chunk_size
                    end = min(start + chunk_size, len(texts))

                    chunk_texts = texts[start:end]
                    chunk_hashes = hashes[start:end]

                    logger.info(f"API call {chunk_idx + 1}/{num_chunks}: {len(chunk_texts)} texts")
                    sys.stdout.flush()

                    response = self.client.embeddings.create(
                        model=self.model,
                        input=chunk_texts
                    )

                    for i, embedding_obj in enumerate(response.data):
                        embedding = embedding_obj.embedding
                        text_hash = chunk_hashes[i]
                        results[text_hash] = embedding

                        # Cache
                        if use_cache:
                            self.cache[text_hash] = embedding

            if use_cache:
                self._save_cache()

            logger.info(f"Generated {len(results) - len([h for h in hashes if h in results and results[h]])} new embeddings via direct API")
            return results

        except Exception as e:
            logger.error(f"Error in batch embedding: {e}")
            raise

    def _embed_batch_api(self, texts: List[str], hashes: List[str],
                        results: Dict[str, List[float]], use_cache: bool) -> Dict[str, List[float]]:
        """
        Generate embeddings using Batch API (for >=100 texts, 50% discount).

        Note: Batch API requires JSONL file format and async processing.
        """
        import sys
        logger.info(f"_embed_batch_api: Using Batch API for {len(texts)} texts (50% cost savings)")
        sys.stdout.flush()

        # Create batch request file (JSONL)
        batch_file_path = self.cache_dir / f"batch_request_{int(time.time())}.jsonl"

        try:
            with open(batch_file_path, 'w') as f:
                for i, text in enumerate(texts):
                    request = {
                        "custom_id": hashes[i],
                        "method": "POST",
                        "url": "/v1/embeddings",
                        "body": {
                            "model": self.model,
                            "input": text
                        }
                    }
                    f.write(json.dumps(request) + '\n')

            # Upload batch file
            logger.info("Uploading batch file to OpenAI...")
            with open(batch_file_path, 'rb') as f:
                batch_input_file = self.client.files.create(
                    file=f,
                    purpose="batch"
                )

            # Create batch job
            logger.info("Creating batch job...")
            batch = self.client.batches.create(
                input_file_id=batch_input_file.id,
                endpoint="/v1/embeddings",
                completion_window="24h"  # Batch API processes within 24h
            )

            batch_job = BatchJob(
                id=batch.id,
                status=batch.status,
                input_file_id=batch_input_file.id,
                created_at=batch.created_at
            )

            logger.info(f"Batch job created: {batch_job.id}")
            logger.info("Batch processing typically completes in 10-20 minutes")

            return {'batch_job': batch_job, 'pending': True}

        except Exception as e:
            logger.error(f"Error in batch API: {e}")
            # Fallback to direct API
            logger.warning("Falling back to direct API")
            return self._embed_direct(texts, hashes, results, use_cache)

        finally:
            # Clean up batch file
            if batch_file_path.exists():
                batch_file_path.unlink()

    def wait_for_batch(self, batch_id: str, timeout: int = 3600, poll_interval: int = 30) -> Dict[str, List[float]]:
        """
        Wait for batch job to complete and retrieve results.

        Args:
            batch_id: Batch job ID
            timeout: Maximum wait time in seconds (default: 1 hour)
            poll_interval: Seconds between status checks (default: 30)

        Returns:
            Dict mapping text hash to embedding vector
        """
        start_time = time.time()
        results = {}

        logger.info(f"Waiting for batch {batch_id} to complete...")

        while time.time() - start_time < timeout:
            try:
                # Check batch status
                batch = self.client.batches.retrieve(batch_id)

                if batch.status == "completed":
                    logger.info(f"Batch {batch_id} completed!")

                    # Download results
                    if batch.output_file_id:
                        output_file = self.client.files.content(batch.output_file_id)
                        output_data = output_file.read().decode('utf-8')

                        # Parse results
                        for line in output_data.strip().split('\n'):
                            result = json.loads(line)
                            custom_id = result['custom_id']  # text hash
                            embedding = result['response']['body']['data'][0]['embedding']
                            results[custom_id] = embedding

                            # Cache
                            self.cache[custom_id] = embedding

                        self._save_cache()
                        logger.info(f"Retrieved {len(results)} embeddings from batch")

                    return results

                elif batch.status in ["failed", "cancelled", "expired"]:
                    error_msg = f"Batch {batch_id} failed with status: {batch.status}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # Still in progress
                logger.debug(f"Batch status: {batch.status} (elapsed: {int(time.time() - start_time)}s)")
                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error checking batch status: {e}")
                raise

        raise TimeoutError(f"Batch {batch_id} did not complete within {timeout} seconds")

    def get_stats(self) -> Dict[str, Any]:
        """Get embedding service statistics."""
        return {
            "cache_size": len(self.cache),
            "model": self.model,
            "cache_dir": str(self.cache_dir)
        }
