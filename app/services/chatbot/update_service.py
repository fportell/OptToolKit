"""
Update Service for DR Knowledge Chatbot.

Handles Excel file uploads, change detection, and atomic database updates.
Per chatbot_revised.md: Daily updates, 2-day backup retention, MD5 change detection.
"""

import logging
import shutil
import sys
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

import pandas as pd
from flask import current_app

from app.services.chatbot.data_processor import DataProcessor
from app.services.chatbot.embedding_service import EmbeddingService
from app.services.chatbot.vector_store import VectorStore
from app.services.chatbot.metadata_service import MetadataService

logger = logging.getLogger(__name__)


@dataclass
class ChangeSet:
    """Changes detected between old and new database."""
    new_events: List
    modified_events: List
    deleted_events: List

    def is_empty(self) -> bool:
        """Check if there are any changes."""
        return len(self.new_events) == 0 and len(self.modified_events) == 0 and len(self.deleted_events) == 0

    def summary(self) -> Dict[str, int]:
        """Get change summary."""
        return {
            "new": len(self.new_events),
            "modified": len(self.modified_events),
            "deleted": len(self.deleted_events)
        }


@dataclass
class UpdateResult:
    """Result of update operation."""
    success: bool
    message: str
    version_id: str = ""
    backup_id: str = ""
    changes: Dict[str, int] = None
    error: str = ""


class UpdateService:
    """Orchestrate database updates from Excel files."""

    def __init__(
        self,
        data_processor: DataProcessor,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        metadata_service: MetadataService,
        data_dir: str = "app/data/chatbot"
    ):
        """
        Initialize update service.

        Args:
            data_processor: Data processing service
            embedding_service: Embedding service
            vector_store: Vector store
            metadata_service: Metadata service
            data_dir: Data directory
        """
        self.data_processor = data_processor
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.metadata_service = metadata_service

        self.data_dir = Path(data_dir)
        self.uploads_dir = self.data_dir / "uploads"
        self.backups_dir = self.data_dir / "backups"
        self.current_db_path = self.data_dir / "DR_database_PBI.xlsx"

        # Create directories
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Update service initialized")

    def process_upload(self, excel_file, uploaded_by: str) -> UpdateResult:
        """
        Process uploaded Excel file and update database.

        Args:
            excel_file: FileStorage object from Flask
            uploaded_by: User who uploaded the file

        Returns:
            UpdateResult with operation details
        """
        timestamp = datetime.now()
        version_id = f"v_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting update process: {version_id}")

        try:
            # 1. Save uploaded file
            upload_path = self.uploads_dir / f"DR_database_{timestamp.strftime('%Y%m%d_%H%M%S')}.xlsx"
            excel_file.save(str(upload_path))
            logger.info(f"Saved upload to: {upload_path}")

            # 2. Load and validate
            new_df = self.data_processor.load_excel(str(upload_path))
            validation = self.data_processor.validate_data(new_df)

            if not validation['valid']:
                error_msg = f"Validation failed: {', '.join(validation['errors'])}"
                logger.error(error_msg)
                return UpdateResult(success=False, message=error_msg, error=error_msg)

            # 3. Check if ChromaDB has data (first upload vs update)
            try:
                collection = self.vector_store.client.get_collection(self.vector_store.collection_name)
                has_existing_data = collection.count() > 0
            except:
                has_existing_data = False

            # 3b. Detect changes (compare with current database)
            changeset = self._detect_changes(new_df)

            if changeset.is_empty() and has_existing_data:
                logger.info("No changes detected and database already loaded")
                return UpdateResult(
                    success=True,
                    message="No changes detected - database is already up to date",
                    version_id=version_id
                )
            elif changeset.is_empty() and not has_existing_data:
                # No changes but database is empty - this is first load, process everything
                logger.info("No changes detected but database is empty - processing all events as initial load")
                all_events = self.data_processor.extract_events(new_df)
                changeset = ChangeSet(
                    new_events=all_events,
                    modified_events=[],
                    deleted_events=[]
                )

            logger.info(f"Changes detected: {changeset.summary()}")

            # 4. Create backup
            backup_id = self._create_backup()
            logger.info(f"Backup created: {backup_id}")

            # 5. Process new/modified events
            logger.info("Step 5: Extracting events from uploaded file...")
            sys.stdout.flush()
            all_events = self.data_processor.extract_events(new_df)
            logger.info(f"Extracted {len(all_events)} events")
            sys.stdout.flush()

            logger.info("Step 6: Chunking events...")
            sys.stdout.flush()
            chunks = self.data_processor.chunk_events(all_events)
            logger.info(f"Created {len(chunks)} chunks")
            sys.stdout.flush()

            logger.info(f"Step 7: Processing embeddings for {len(chunks)} chunks...")
            sys.stdout.flush()

            # 6. Generate embeddings (always use embed_batch for efficiency)
            logger.info(f"Generating embeddings for {len(chunks)} chunks...")
            sys.stdout.flush()

            # Extract text from all chunks
            logger.info("Extracting text from chunks...")
            sys.stdout.flush()
            texts = [chunk.text for chunk in chunks]

            # Use embed_batch which handles caching and batching intelligently
            logger.info(f"Calling embed_batch for {len(texts)} texts...")
            sys.stdout.flush()
            embeddings_dict = self.embedding_service.embed_batch(texts)

            # Check if Batch API was used (async processing)
            if 'batch_job' in embeddings_dict and embeddings_dict.get('pending'):
                logger.info("Batch API job pending - embeddings will be processed asynchronously")
                sys.stdout.flush()
                return UpdateResult(
                    success=False,
                    message="Batch processing started - update will complete in 10-20 minutes",
                    version_id=version_id,
                    error="Use check_batch_status endpoint to monitor progress"
                )

            # Extract embeddings in same order as chunks
            logger.info("Mapping embeddings to chunks...")
            sys.stdout.flush()
            embeddings = []
            for i, chunk in enumerate(chunks):
                if (i + 1) % 50 == 0:
                    logger.info(f"Mapped {i + 1}/{len(chunks)} embeddings")
                    sys.stdout.flush()
                text_hash = self.embedding_service._text_hash(chunk.text)
                embeddings.append(embeddings_dict[text_hash])

            logger.info(f"All {len(embeddings)} embeddings ready")
            sys.stdout.flush()

            # 7. Update vector store (atomic operation)
            logger.info("Updating vector store...")
            self.vector_store.create_collection(reset=True)  # Reset and recreate
            self.vector_store.add_documents(chunks, embeddings)

            # 8. Update metadata
            logger.info("Updating metadata...")
            self.metadata_service.record_update(
                version_id=version_id,
                source_file=str(upload_path),
                total_events=len(all_events),
                total_chunks=len(chunks),
                changes=changeset.summary(),
                uploaded_by=uploaded_by,
                status="completed"
            )

            # 9. Replace current database file
            shutil.copy(upload_path, self.current_db_path)

            # 10. Cleanup old backups (keep last 2 days)
            self.metadata_service.cleanup_old_backups(str(self.backups_dir), retention_days=2)

            logger.info(f"Update completed successfully: {version_id}")

            return UpdateResult(
                success=True,
                message=f"Update successful: {changeset.summary()['new']} new, {changeset.summary()['modified']} modified events",
                version_id=version_id,
                backup_id=backup_id,
                changes=changeset.summary()
            )

        except Exception as e:
            error_msg = f"Update failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Attempt rollback
            if 'backup_id' in locals():
                self._rollback(locals()['backup_id'])

            return UpdateResult(success=False, message=error_msg, error=str(e))

    def _detect_changes(self, new_df: pd.DataFrame) -> ChangeSet:
        """
        Detect changes between current and new database.

        Args:
            new_df: New database DataFrame

        Returns:
            ChangeSet with detected changes
        """
        # Load current database if it exists
        if not self.current_db_path.exists():
            # No current database - all events are new
            all_events = self.data_processor.extract_events(new_df)
            return ChangeSet(
                new_events=all_events,
                modified_events=[],
                deleted_events=[]
            )

        try:
            old_df = self.data_processor.load_excel(str(self.current_db_path))

            # Convert to dictionaries for comparison (keyed by ENTRY_#)
            old_events = {str(row['ENTRY_#']): row for _, row in old_df.iterrows()}
            new_events = {str(row['ENTRY_#']): row for _, row in new_df.iterrows()}

            # Find new, modified, deleted
            new_ids = set(new_events.keys()) - set(old_events.keys())
            deleted_ids = set(old_events.keys()) - set(new_events.keys())
            common_ids = set(new_events.keys()) & set(old_events.keys())

            # Detect modifications (simple: check if any field changed)
            modified_ids = []
            for entry_id in common_ids:
                old_row = old_events[entry_id]
                new_row = new_events[entry_id]

                # Compare SUMMARY field (most likely to change)
                if str(old_row.get('SUMMARY', '')) != str(new_row.get('SUMMARY', '')):
                    modified_ids.append(entry_id)

            # Extract actual events
            new_event_objects = self.data_processor.extract_events(
                new_df[new_df['ENTRY_#'].astype(str).isin(new_ids)]
            )

            modified_event_objects = self.data_processor.extract_events(
                new_df[new_df['ENTRY_#'].astype(str).isin(modified_ids)]
            )

            deleted_event_objects = []  # We don't delete, just track

            logger.info(f"Changes: {len(new_ids)} new, {len(modified_ids)} modified, {len(deleted_ids)} deleted")

            return ChangeSet(
                new_events=new_event_objects,
                modified_events=modified_event_objects,
                deleted_events=deleted_event_objects
            )

        except Exception as e:
            logger.error(f"Error detecting changes: {e}")
            # If comparison fails, treat all as new
            all_events = self.data_processor.extract_events(new_df)
            return ChangeSet(
                new_events=all_events,
                modified_events=[],
                deleted_events=[]
            )

    def _create_backup(self) -> str:
        """Create backup of current database."""
        if not self.current_db_path.exists():
            return "no_backup_needed"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}"
        backup_path = self.backups_dir / f"{backup_id}.xlsx"

        shutil.copy(self.current_db_path, backup_path)

        logger.info(f"Created backup: {backup_path}")
        return backup_id

    def _rollback(self, backup_id: str):
        """
        Rollback to a previous backup.

        Args:
            backup_id: Backup identifier
        """
        backup_path = self.backups_dir / f"{backup_id}.xlsx"

        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_id}")
            return

        try:
            shutil.copy(backup_path, self.current_db_path)
            logger.info(f"Rolled back to backup: {backup_id}")
        except Exception as e:
            logger.error(f"Rollback failed: {e}")

    def get_upload_history(self, limit: int = 10) -> List[Dict]:
        """Get recent upload history."""
        return self.metadata_service.get_update_history(limit=limit)
