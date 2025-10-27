"""
Metadata Service for DR Knowledge Chatbot.

Handles database metadata, update history, and statistics.
Per chatbot_revised.md: 2-day backup retention, track all updates.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class MetadataService:
    """Manage chatbot database metadata and update history."""

    def __init__(self, data_dir: str = "app/data/chatbot"):
        """
        Initialize metadata service.

        Args:
            data_dir: Directory for metadata storage
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.data_dir / "metadata.json"
        self.metadata = self._load_metadata()

        logger.info("Metadata service initialized")

    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                return self._default_metadata()
        return self._default_metadata()

    def _default_metadata(self) -> Dict[str, Any]:
        """Create default metadata structure."""
        return {
            "current_version": {
                "id": "v_initial",
                "timestamp": datetime.now().isoformat(),
                "source_file": None,
                "total_events": 0,
                "total_chunks": 0,
                "embedding_model": "text-embedding-3-small",
                "unique_hazards": 0,
                "unique_locations": 0,
                "date_range": {
                    "earliest": None,
                    "latest": None
                }
            },
            "update_history": [],
            "statistics": {
                "top_hazards": [],
                "top_locations": []
            }
        }

    def _save_metadata(self):
        """Save metadata to disk."""
        try:
            # Ensure directory exists
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
            logger.info(f"Metadata saved to {self.metadata_file}")
        except Exception as e:
            logger.error(f"Error saving metadata to {self.metadata_file}: {e}", exc_info=True)

    def get_last_update(self) -> Dict[str, Any]:
        """Get information about the last update."""
        return self.metadata.get("current_version", {})

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        # Reload metadata from disk to ensure we have latest data
        self.metadata = self._load_metadata()
        current = self.metadata.get("current_version", {})
        return {
            "total_events": current.get("total_events", 0),
            "total_chunks": current.get("total_chunks", 0),
            "unique_hazards": current.get("unique_hazards", 0),
            "unique_locations": current.get("unique_locations", 0),
            "date_range": current.get("date_range", {}),
            "last_update": current.get("timestamp"),
            "source_file": current.get("source_file"),
            "top_hazards": self.metadata.get("statistics", {}).get("top_hazards", []),
            "top_locations": self.metadata.get("statistics", {}).get("top_locations", [])
        }

    def get_update_history(self, limit: int = 10) -> List[Dict]:
        """
        Get update history.

        Args:
            limit: Maximum number of updates to return

        Returns:
            List of update records
        """
        history = self.metadata.get("update_history", [])
        return sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

    def update_metadata(self, new_data: Dict[str, Any]):
        """
        Update metadata with new information.

        Args:
            new_data: New metadata to merge
        """
        # Update current version
        if "current_version" in new_data:
            self.metadata["current_version"].update(new_data["current_version"])

        # Update statistics
        if "statistics" in new_data:
            self.metadata["statistics"].update(new_data["statistics"])

        # Add to update history
        if "update_record" in new_data:
            self.metadata.setdefault("update_history", []).append(new_data["update_record"])

        # Save
        self._save_metadata()
        logger.info("Metadata updated")

    def record_update(
        self,
        version_id: str,
        source_file: str,
        total_events: int,
        total_chunks: int,
        changes: Dict[str, int],
        uploaded_by: str,
        status: str = "completed"
    ):
        """
        Record a database update.

        Args:
            version_id: Version identifier
            source_file: Source Excel file path
            total_events: Total number of events
            total_chunks: Total number of chunks
            changes: Dict with 'new', 'modified', 'deleted' counts
            uploaded_by: User who uploaded
            status: Update status
        """
        timestamp = datetime.now().isoformat()

        # Update current version
        self.metadata["current_version"] = {
            "id": version_id,
            "timestamp": timestamp,
            "source_file": source_file,
            "total_events": total_events,
            "total_chunks": total_chunks,
            "embedding_model": "text-embedding-3-small"
        }

        # Add to history
        update_record = {
            "version_id": version_id,
            "timestamp": timestamp,
            "uploaded_by": uploaded_by,
            "changes": changes,
            "status": status,
            "total_events": total_events
        }

        self.metadata.setdefault("update_history", []).append(update_record)

        # Save
        self._save_metadata()

        logger.info(f"Recorded update: {version_id}")

    def cleanup_old_backups(self, backup_dir: str, retention_days: int = 2):
        """
        Clean up backups older than retention period.

        Args:
            backup_dir: Directory containing backups
            retention_days: Number of days to retain backups
        """
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            return

        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0

        for backup_file in backup_path.glob("backup_*.db"):
            try:
                # Extract timestamp from filename (e.g., backup_20251023_143000.db)
                timestamp_str = backup_file.stem.replace("backup_", "")
                file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                if file_date < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {backup_file.name}")

            except Exception as e:
                logger.warning(f"Error processing backup {backup_file}: {e}")

        logger.info(f"Backup cleanup: deleted {deleted_count} old backups")

    def get_database_info(self) -> Dict[str, Any]:
        """Get complete database information for dashboard."""
        return {
            "version": self.metadata.get("current_version", {}),
            "statistics": self.get_statistics(),
            "recent_updates": self.get_update_history(limit=5)
        }

    def sync_from_chromadb(self, vector_store) -> bool:
        """
        Sync metadata from ChromaDB if metadata.json doesn't exist.

        Args:
            vector_store: VectorStore instance to sync from

        Returns:
            bool: True if sync was successful
        """
        try:
            # Get collection from ChromaDB
            collection = vector_store.client.get_collection(vector_store.collection_name)
            chunk_count = collection.count()

            if chunk_count == 0:
                logger.warning("ChromaDB collection is empty, nothing to sync")
                return False

            # Get a sample document to extract event info
            sample = collection.peek(limit=1)

            # Create basic metadata
            logger.info(f"Syncing metadata from ChromaDB ({chunk_count} chunks)")

            # Count unique events from metadata
            all_metadata = collection.get(limit=chunk_count, include=['metadatas'])
            unique_events = set()
            for meta in all_metadata['metadatas']:
                if 'event_id' in meta:
                    unique_events.add(meta['event_id'])

            event_count = len(unique_events)

            # Record as recovered
            self.record_update(
                version_id="v_recovered_from_chromadb",
                source_file="Recovered from ChromaDB",
                total_events=event_count,
                total_chunks=chunk_count,
                changes={'new': event_count, 'modified': 0, 'deleted': 0},
                uploaded_by="system_recovery",
                status="completed"
            )

            logger.info(f"Metadata synced: {event_count} events, {chunk_count} chunks")
            return True

        except Exception as e:
            logger.error(f"Failed to sync metadata from ChromaDB: {e}", exc_info=True)
            return False
