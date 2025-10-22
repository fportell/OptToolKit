"""
Concurrency Management for OpsToolKit.

Implements user concurrency tracking and OpenAI request queuing.
Per FR-016: Maximum 5 concurrent users with performance warning display.
Per clarifications: OpenAI request queuing to avoid rate limit conflicts.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from queue import Queue, Empty
from threading import Lock, Thread
from dataclasses import dataclass
from flask import session, current_app
from flask_login import current_user

logger = logging.getLogger(__name__)


# =========================================================================
# Active User Tracking
# =========================================================================

# In-memory storage for active users
# Format: {username: {'last_seen': datetime, 'session_id': str}}
# Note: In production with multiple workers, consider Redis for shared state
_active_users: Dict[str, Dict[str, Any]] = {}
_active_users_lock = Lock()

# Activity timeout for counting users as "active"
ACTIVITY_TIMEOUT_SECONDS = 60  # Consider user inactive after 1 minute


def update_active_user():
    """
    Update the active user registry with current user's activity.

    Should be called on every authenticated request to maintain accurate
    concurrent user count.
    """
    if not current_user.is_authenticated:
        return

    username = current_user.id
    session_id = session.get('_id', 'unknown')

    with _active_users_lock:
        _active_users[username] = {
            'last_seen': datetime.utcnow(),
            'session_id': session_id
        }


def cleanup_inactive_users():
    """
    Remove users who haven't been seen within ACTIVITY_TIMEOUT_SECONDS.

    Returns:
        int: Number of users removed
    """
    cutoff_time = datetime.utcnow() - timedelta(seconds=ACTIVITY_TIMEOUT_SECONDS)
    removed_count = 0

    with _active_users_lock:
        inactive_users = [
            username for username, data in _active_users.items()
            if data['last_seen'] < cutoff_time
        ]

        for username in inactive_users:
            del _active_users[username]
            removed_count += 1

    if removed_count > 0:
        logger.debug(f"Cleaned up {removed_count} inactive user(s)")

    return removed_count


def get_active_user_count() -> int:
    """
    Get the count of currently active users.

    Per T033: Returns count of users who have been active within
    ACTIVITY_TIMEOUT_SECONDS.

    Returns:
        int: Number of active users
    """
    # Clean up inactive users first
    cleanup_inactive_users()

    with _active_users_lock:
        count = len(_active_users)

    return count


def get_active_users() -> List[Dict[str, Any]]:
    """
    Get list of currently active users with details.

    Returns:
        List[Dict]: List of active user dictionaries
    """
    cleanup_inactive_users()

    with _active_users_lock:
        users = [
            {
                'username': username,
                'last_seen': data['last_seen'].isoformat(),
                'session_id': data['session_id']
            }
            for username, data in _active_users.items()
        ]

    return users


def should_display_performance_warning() -> bool:
    """
    Determine if performance warning should be displayed.

    Per T034: Display warning when at or near MAX_CONCURRENT_USERS capacity.

    Returns:
        bool: True if warning should be shown
    """
    max_users = current_app.config.get('MAX_CONCURRENT_USERS', 5)
    current_count = get_active_user_count()

    # Show warning when at or above max capacity
    return current_count >= max_users


# =========================================================================
# OpenAI Request Queue (T035-T037)
# =========================================================================

@dataclass
class OpenAIRequest:
    """
    Represents a queued OpenAI API request.

    Attributes:
        id: Unique request identifier
        func: The function to call (OpenAI API call)
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        callback: Optional callback function to call with result
        error_callback: Optional callback function to call on error
        created_at: Timestamp when request was created
        result: Result of the API call (set after processing)
        error: Error if the call failed (set after processing)
        completed: Whether the request has been processed
    """
    id: str
    func: Callable
    args: tuple
    kwargs: dict
    callback: Optional[Callable] = None
    error_callback: Optional[Callable] = None
    created_at: float = None
    result: Any = None
    error: Optional[Exception] = None
    completed: bool = False

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class OpenAIQueue:
    """
    FIFO queue for OpenAI API requests to avoid rate limit conflicts.

    Per clarifications: Queue OpenAI requests to ensure sequential processing
    and avoid hitting rate limits.

    Features:
    - FIFO processing of requests
    - Background worker thread
    - Callback support for async results
    - Request tracking and status
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize OpenAI request queue.

        Args:
            enabled: If False, requests execute immediately without queuing
        """
        self.enabled = enabled
        self._queue: Queue[OpenAIRequest] = Queue()
        self._requests: Dict[str, OpenAIRequest] = {}  # Track all requests by ID
        self._requests_lock = Lock()
        self._worker_thread: Optional[Thread] = None
        self._running = False

        if self.enabled:
            self.start_worker()

    def start_worker(self):
        """Start the background worker thread."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            logger.warning("OpenAI queue worker already running")
            return

        self._running = True
        self._worker_thread = Thread(target=self._worker, daemon=True, name="OpenAIQueueWorker")
        self._worker_thread.start()
        logger.info("OpenAI queue worker started")

    def stop_worker(self):
        """Stop the background worker thread."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        logger.info("OpenAI queue worker stopped")

    def _worker(self):
        """
        Background worker that processes queued requests.

        Runs continuously, processing requests from the queue in FIFO order.
        """
        logger.info("OpenAI queue worker thread started")

        while self._running:
            try:
                # Get next request (with timeout to allow checking _running flag)
                request = self._queue.get(timeout=1)

                logger.info(f"Processing OpenAI request {request.id}")

                try:
                    # Execute the OpenAI API call
                    result = request.func(*request.args, **request.kwargs)

                    # Store result
                    request.result = result
                    request.completed = True

                    # Call success callback if provided
                    if request.callback:
                        try:
                            request.callback(result)
                        except Exception as e:
                            logger.error(f"Error in request callback: {e}")

                    logger.info(f"OpenAI request {request.id} completed successfully")

                except Exception as e:
                    # Store error
                    request.error = e
                    request.completed = True

                    # Call error callback if provided
                    if request.error_callback:
                        try:
                            request.error_callback(e)
                        except Exception as callback_error:
                            logger.error(f"Error in error callback: {callback_error}")

                    logger.error(f"OpenAI request {request.id} failed: {e}")

                finally:
                    self._queue.task_done()

            except Empty:
                # No requests in queue, continue waiting
                continue
            except Exception as e:
                logger.error(f"Unexpected error in OpenAI queue worker: {e}")

        logger.info("OpenAI queue worker thread stopped")

    def enqueue(self,
                request_id: str,
                func: Callable,
                *args,
                callback: Optional[Callable] = None,
                error_callback: Optional[Callable] = None,
                **kwargs) -> OpenAIRequest:
        """
        Add an OpenAI API request to the queue.

        Args:
            request_id: Unique identifier for this request
            func: The OpenAI API function to call
            *args: Positional arguments for func
            callback: Optional callback to call with result on success
            error_callback: Optional callback to call with error on failure
            **kwargs: Keyword arguments for func

        Returns:
            OpenAIRequest: The created request object (can be used to check status)
        """
        request = OpenAIRequest(
            id=request_id,
            func=func,
            args=args,
            kwargs=kwargs,
            callback=callback,
            error_callback=error_callback
        )

        with self._requests_lock:
            self._requests[request_id] = request

        if self.enabled:
            # Add to queue for background processing
            self._queue.put(request)
            logger.info(f"Queued OpenAI request {request_id} (queue size: {self._queue.qsize()})")
        else:
            # Execute immediately if queuing is disabled
            logger.info(f"Executing OpenAI request {request_id} immediately (queue disabled)")
            try:
                result = func(*args, **kwargs)
                request.result = result
                request.completed = True
                if callback:
                    callback(result)
            except Exception as e:
                request.error = e
                request.completed = True
                if error_callback:
                    error_callback(e)
                else:
                    raise

        return request

    def get_request_status(self, request_id: str) -> Optional[OpenAIRequest]:
        """
        Get the status of a queued request.

        Args:
            request_id: The request ID to look up

        Returns:
            OpenAIRequest: The request object, or None if not found
        """
        with self._requests_lock:
            return self._requests.get(request_id)

    def wait_for_request(self, request_id: str, timeout: Optional[float] = None) -> OpenAIRequest:
        """
        Wait for a request to complete.

        Args:
            request_id: The request ID to wait for
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            OpenAIRequest: The completed request object

        Raises:
            TimeoutError: If timeout is exceeded
            KeyError: If request_id is not found
        """
        start_time = time.time()

        while True:
            request = self.get_request_status(request_id)

            if request is None:
                raise KeyError(f"Request {request_id} not found")

            if request.completed:
                return request

            # Check timeout
            if timeout is not None and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Request {request_id} did not complete within {timeout}s")

            # Sleep briefly before checking again
            time.sleep(0.1)

    def get_queue_size(self) -> int:
        """Get the current number of pending requests in the queue."""
        return self._queue.qsize()

    def cleanup_old_requests(self, max_age_seconds: int = 3600):
        """
        Remove completed requests older than max_age_seconds.

        Args:
            max_age_seconds: Maximum age in seconds for completed requests
        """
        cutoff_time = time.time() - max_age_seconds
        removed_count = 0

        with self._requests_lock:
            old_requests = [
                req_id for req_id, req in self._requests.items()
                if req.completed and req.created_at < cutoff_time
            ]

            for req_id in old_requests:
                del self._requests[req_id]
                removed_count += 1

        if removed_count > 0:
            logger.debug(f"Cleaned up {removed_count} old OpenAI request(s)")


# Global OpenAI queue instance
_openai_queue: Optional[OpenAIQueue] = None


def get_openai_queue() -> OpenAIQueue:
    """
    Get the global OpenAI queue instance.

    Returns:
        OpenAIQueue: The queue instance
    """
    global _openai_queue

    if _openai_queue is None:
        # Initialize queue based on config
        enabled = current_app.config.get('OPENAI_QUEUE_ENABLED', True)
        _openai_queue = OpenAIQueue(enabled=enabled)

    return _openai_queue


def init_concurrency_hooks(app):
    """
    Initialize concurrency management hooks for Flask app.

    Registers before_request handler to update active user tracking.
    Per T032-T037: Set up concurrency control and OpenAI queuing.

    Args:
        app: Flask application instance
    """

    @app.before_request
    def track_user_activity():
        """Update active user tracking on every authenticated request."""
        if current_user.is_authenticated:
            update_active_user()

    # Initialize OpenAI queue
    with app.app_context():
        queue = get_openai_queue()
        app.logger.info(
            f"Concurrency management initialized "
            f"(max_users={app.config.get('MAX_CONCURRENT_USERS', 5)}, "
            f"openai_queue={'enabled' if queue.enabled else 'disabled'})"
        )
