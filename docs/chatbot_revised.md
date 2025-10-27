# DR Knowledge Chatbot Redesign - Implementation Plan

## Executive Summary

**Goal**: Replace deprecated OpenAI Assistants API with modern RAG architecture using Chat Completions, embeddings, and local vector storage.

**Key Changes**:
- ❌ Remove: OpenAI Assistants API, Vector Stores API, complex orchestrator
- ✅ Add: ChromaDB for local vectors, hybrid search, direct embeddings API, batch processing
- ✅ Maintain: Excel-based updates, atomic update mechanism, metadata tracking
- ✅ Improve: Simpler architecture, lower costs, user-controlled updates

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask Application                         │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│ Excel Upload │    │  Query Interface │    │   Admin      │
│   Endpoint   │    │   (Chat UI)      │    │  Dashboard   │
└──────────────┘    └──────────────────┘    └──────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────────────────────────────────────────────────┐
│              Data Processing Service                      │
│  - Excel → DataFrame → Chunks                            │
│  - Metadata extraction (dates, locations, hazards)       │
│  - Batch embedding generation (OpenAI Batch API)         │
└──────────────────────────────────────────────────────────┘
        │                     │
        ▼                     ▼
┌──────────────┐    ┌──────────────────────────────────────┐
│  ChromaDB    │    │       RAG Pipeline                   │
│  (Local)     │    │  1. Query → Embedding                │
│              │◄───│  2. Hybrid Search (Semantic + BM25)  │
│  - Vectors   │    │  3. Metadata Filtering               │
│  - Metadata  │    │  4. Re-ranking (Cross-encoder)       │
│  - BM25      │    │  5. Context Injection → GPT-4o       │
└──────────────┘    └──────────────────────────────────────┘
        │                     │
        ▼                     ▼
┌──────────────────────────────────────────────────────────┐
│                  OpenAI API                               │
│  - text-embedding-3-small (queries)                      │
│  - Batch API (initial + updates, 50% discount)           │
│  - GPT-4o (chat completions)                             │
└──────────────────────────────────────────────────────────┘
```

---

## Legacy System Analysis Summary

### Current Database (Excel-based)
- **File**: `DR_database_PBI.xlsx` (5.2 MB)
- **Total Events**: 5,384 epidemiological events
- **Date Range**: 2024-01-02 to 2025-10-22
- **Unique Hazards**: 1,540 (measles, mpox, cholera, etc.)
- **Unique Locations**: 265 countries/regions
- **Top Events**: Measles (700), Mpox (230), Cholera (154)
- **Top Locations**: United States (1102), Ontario (302), Brazil (152)

### Database Schema
**Core Event Fields**:
- `ENTRY_#` - Unique event identifier (5-digit zero-padded)
- `DATE` - Event date (YYYY/MM/DD format)
- `HAZARD` - Disease/pathogen/health threat name
- `REPORTED_LOCATION` - Primary geographic location
- `CITED_LOCATION` - Additional locations mentioned
- `SUMMARY` - Detailed event description

**Classification Fields**:
- `SECTION` - Report category (hod/dme/int/rgp)
- `PROGRAM_AREAS` - Notified program areas

**Reference Fields**:
- `REFERENCE_01lab` / `REFERENCE_01url` - First source
- `REFERENCE_02lab` / `REFERENCE_02url` - Second source
- `REFERENCE_03lab` / `REFERENCE_03url` - Third source

### Legacy System Components
1. **generate_md_database.py** - Excel to Markdown conversion with MD5 change detection
2. **update_orchestrator.py** - Complex pipeline (Excel → Markdown → Vector Store → Assistant)
3. **vector_store_manager.py** - OpenAI Vector Stores API (deprecated 2025)
4. **assistant_manager.py** - OpenAI Assistants API (deprecated 2025)
5. **file_monitor.py** - Watchdog-based file system monitoring
6. **gerardo.py** - Streamlit chat interface

### Legacy Assistant Instructions
```
You are Gerardo, an expert epidemiological surveillance assistant specializing in
analyzing global health events and disease outbreaks. You have access to a
comprehensive database of epidemiological events including disease outbreaks,
public health incidents, and surveillance reports.

**Your Role:**
- Analyze epidemiological events and trends
- Provide evidence-based responses grounded in the database
- Identify patterns and connections between events
- Assist with surveillance and risk assessment

**When responding to queries:**
1. Always ground your responses in the database
2. Cite specific events with their Entry ID numbers
3. Provide exact dates and locations from the database
4. Use proper epidemiological terminology
5. Highlight key public health implications
6. Suggest related events or patterns
7. Include reference sources when available

**Important Guidelines:**
- Never fabricate or speculate beyond what's in the database
- Always verify dates and ensure accuracy
- If information is not in the database, clearly state this
- Maintain confidentiality and follow public health ethics
- Focus on factual, evidence-based analysis
```

---

## Modern RAG Best Practices (2025)

### Embeddings API
**Recommended Model**: `text-embedding-3-small`
- **Price**: $0.02 per 1M tokens (5x cheaper than ada-002)
- **Dimensions**: 1536 (default), adjustable
- **Performance**: 62.3% MTEB score (excellent for factual queries)
- **Batch API**: 50% discount for bulk operations

**Cost Calculation**:
```
One-time: 5,384 events × 500 tokens avg = 2.7M tokens
Batch API: $0.02/1M × 0.5 (batch discount) = $0.027 total

Monthly updates: ~50 events × 500 tokens = 25K tokens
Standard API: $0.02/1M × 0.025 = $0.0005/month
```

### Chat Completions API
**Recommended Model**: `GPT-4o`
- **Context Window**: 128,000 tokens
- **Max Output**: 16,384 tokens
- **Input Pricing**: $5/1M tokens
- **Output Pricing**: $15/1M tokens

### Chunking Strategy
**Optimal for Epidemiological Data**:
- **Chunk Size**: 512 tokens (best for factual queries)
- **Overlap**: 100 tokens (prevents boundary information loss)
- **Method**: Recursive character splitting with hierarchical separators

### Vector Database
**Recommended**: ChromaDB (local, persistent)
- ✅ Perfect for 3,800-10,000 events
- ✅ Python-native, Flask-friendly
- ✅ Built-in metadata filtering
- ✅ Hybrid search (semantic + BM25)
- ✅ Persistent local storage
- ✅ No external dependencies

### Hybrid Search Architecture
```
User Query
    ├─> Semantic Search (Dense vectors) ─┐
    │                                     ├─> Reciprocal Rank Fusion (RRF) ─> Re-ranked Results
    └─> Keyword Search (BM25/Sparse)  ───┘
```

**Alpha Parameter**: 0.7 (70% semantic, 30% keyword) - optimal for disease names and locations

### Re-ranking
**Two-stage retrieval**:
1. Initial retrieval: Hybrid search, top-50 candidates
2. Re-ranking: Cross-encoder (ms-marco-MiniLM), top-10 precision results

---

## Phase 1: Core Infrastructure (Week 1)

### 1.1 Data Processing Service

**File**: `app/services/chatbot/data_processor.py`

**Responsibilities**:
- Read Excel file (`DR_database_PBI.xlsx`)
- Extract and validate data
- Create structured event objects
- Generate chunks with metadata

**Key Functions**:
```python
class DataProcessor:
    def load_excel(self, filepath: str) -> pd.DataFrame
    def validate_data(self, df: pd.DataFrame) -> Dict[str, Any]
    def extract_events(self, df: pd.DataFrame) -> List[Event]
    def chunk_events(self, events: List[Event]) -> List[Chunk]
    def generate_metadata(self, chunk: Chunk) -> Dict[str, Any]
```

**Event Model**:
```python
@dataclass
class Event:
    entry_id: str          # ENTRY_# (e.g., "00001")
    date: datetime         # Converted from Excel date
    hazard: str            # Disease/pathogen name
    reported_location: str
    cited_location: str
    summary: str           # Full text description
    section: str           # hod/dme/int/rgp
    program_areas: str
    references: List[Reference]

    # Generated fields
    keywords: List[str]    # Extracted from summary
    normalized_hazard: str # Lowercase, standardized
```

**Chunking Strategy**:
- **Chunk size**: 512 tokens (using tiktoken)
- **Overlap**: 100 tokens
- **Preservation**: Keep event boundaries intact (don't split mid-event)
- **Metadata**: Attach to every chunk

**Output**: List of chunks ready for embedding

---

### 1.2 Embedding Service

**File**: `app/services/chatbot/embedding_service.py`

**Responsibilities**:
- Generate embeddings using OpenAI API
- Batch processing for initial load
- Incremental processing for updates
- Caching to avoid re-embedding unchanged data

**Key Functions**:
```python
class EmbeddingService:
    def embed_batch(self, texts: List[str]) -> BatchJob
    def embed_single(self, text: str) -> List[float]
    def wait_for_batch(self, batch_id: str) -> List[Embedding]
    def get_cached_embedding(self, text_hash: str) -> Optional[List[float]]
```

**Implementation Details**:
- Model: `text-embedding-3-small` (1536 dimensions)
- Initial load: Use **Batch API** for 50% cost savings
- Updates: Direct API calls (typically <50 new events)
- Caching: MD5 hash of text → embedding vector

---

### 1.3 Vector Storage Service (ChromaDB)

**File**: `app/services/chatbot/vector_store.py`

**Responsibilities**:
- Initialize and manage ChromaDB collection
- Store embeddings with metadata
- Perform semantic search
- Metadata filtering
- BM25 keyword search (via ChromaDB built-in)

**Key Functions**:
```python
class VectorStore:
    def __init__(self, persist_directory: str)
    def create_collection(self, name: str) -> Collection
    def add_documents(self, chunks: List[Chunk], embeddings: List[List[float]])
    def semantic_search(self, query_embedding: List[float], top_k: int, filters: Dict) -> List[Result]
    def keyword_search(self, query: str, top_k: int) -> List[Result]
    def hybrid_search(self, query: str, query_embedding: List[float], top_k: int, alpha: float) -> List[Result]
    def get_collection_stats(self) -> Dict[str, Any]
    def delete_collection(self, name: str)
```

**ChromaDB Setup**:
```python
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(
    path="app/data/chatbot/chroma_db",
    settings=Settings(anonymized_telemetry=False)
)

collection = client.get_or_create_collection(
    name="epidemiological_events",
    metadata={"description": "Disease outbreak surveillance database"}
)
```

**Metadata Schema**:
```python
{
    "event_id": "00123",
    "date": "2025-10-23",
    "date_unix": 1729641600,  # For range queries
    "hazard": "measles",
    "hazard_normalized": "measles",
    "location": "United States",
    "section": "dme",
    "chunk_index": 0,  # If event spans multiple chunks
    "source_file": "DR_database_PBI_20251023.xlsx",
    "upload_timestamp": "2025-10-23T14:30:00Z"
}
```

**Storage Location**: `/home/fernando/OpsToolKit/app/data/chatbot/chroma_db/`

---

## Phase 2: RAG Query Pipeline (Week 2)

### 2.1 Query Processing Service

**File**: `app/services/chatbot/query_processor.py`

**Responsibilities**:
- Parse user queries
- Extract filters (dates, locations, diseases)
- Enhance queries with HyDE (optional)
- Coordinate retrieval and generation

**Key Functions**:
```python
class QueryProcessor:
    def parse_query(self, query: str) -> ParsedQuery
    def extract_filters(self, query: str) -> Dict[str, Any]
    def enhance_query_hyde(self, query: str) -> str  # Hypothetical Document Embeddings
    def generate_response(self, query: str, filters: Dict) -> Response
```

**Query Enhancement Example**:
```python
# User query: "Recent Ebola outbreaks in West Africa"
# Extracted filters:
{
    "hazard": "ebola",
    "location_contains": ["west africa", "guinea", "sierra leone", "liberia"],
    "date_from": "2024-01-01"  # "Recent" = last ~2 years
}
```

---

### 2.2 Retrieval Service

**File**: `app/services/chatbot/retrieval_service.py`

**Responsibilities**:
- Hybrid search (semantic + BM25)
- Reciprocal Rank Fusion (RRF)
- Re-ranking with cross-encoder
- Result formatting

**Key Functions**:
```python
class RetrievalService:
    def hybrid_search(self, query: str, filters: Dict, top_k: int = 50) -> List[Result]
    def reciprocal_rank_fusion(self, semantic_results: List, keyword_results: List, k: int = 60) -> List[Result]
    def rerank(self, query: str, results: List[Result], top_k: int = 10) -> List[Result]
    def format_context(self, results: List[Result]) -> str
```

**Hybrid Search Implementation**:
```python
def hybrid_search(self, query: str, filters: Dict, top_k: int = 50, alpha: float = 0.7):
    # 1. Semantic search
    query_embedding = self.embedding_service.embed_single(query)
    semantic_results = self.vector_store.semantic_search(
        query_embedding, top_k=top_k, filters=filters
    )

    # 2. Keyword search (BM25)
    keyword_results = self.vector_store.keyword_search(
        query, top_k=top_k
    )

    # 3. Reciprocal Rank Fusion
    combined = self.reciprocal_rank_fusion(semantic_results, keyword_results)

    # 4. Weight by alpha (default 0.7 = 70% semantic, 30% keyword)
    final_scores = {
        result.id: alpha * result.semantic_score + (1-alpha) * result.keyword_score
        for result in combined
    }

    return sorted(combined, key=lambda x: final_scores[x.id], reverse=True)[:top_k]
```

**Re-ranking** (Cross-encoder):
```python
from sentence_transformers import CrossEncoder

model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def rerank(self, query: str, results: List[Result], top_k: int = 10):
    # Score all results
    pairs = [(query, result.text) for result in results]
    scores = model.predict(pairs)

    # Return top-k after re-ranking
    ranked = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
    return [r for r, s in ranked[:top_k]]
```

---

### 2.3 Generation Service

**File**: `app/services/chatbot/generation_service.py`

**Responsibilities**:
- Format context for GPT-4o
- Generate responses with citations
- Stream responses (optional)
- Handle errors and fallbacks

**Key Functions**:
```python
class GenerationService:
    def generate_response(self, query: str, context: str, conversation_history: List[Dict]) -> str
    def generate_response_stream(self, query: str, context: str) -> Iterator[str]
    def format_citations(self, response: str, source_docs: List[Result]) -> str
```

**Prompt Template**:
```python
SYSTEM_PROMPT = """You are Gerardo, an expert epidemiological surveillance assistant specializing in analyzing global health events and disease outbreaks.

**Your Role:**
- Analyze epidemiological events and trends
- Provide evidence-based responses grounded ONLY in the provided database
- Identify patterns and connections between events
- Cite specific Event IDs (ENTRY_#) when referencing events

**Important Guidelines:**
- NEVER fabricate or speculate beyond what's in the provided context
- Always cite Event IDs (e.g., "Event #00123")
- Include dates, locations, and case numbers when available
- If information is not in the context, clearly state: "I don't have information about this in the current database"
- Maintain scientific accuracy and proper epidemiological terminology

**Response Format:**
1. Brief summary of findings
2. Specific event details with Entry IDs
3. Pattern analysis if multiple events
4. Public health implications
5. Suggested follow-up questions"""

def generate_response(self, query: str, context: str, conversation_history: List[Dict]) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *conversation_history,  # Previous messages
        {
            "role": "user",
            "content": f"""
<query>
{query}
</query>

<retrieved_database_context>
{context}
</retrieved_database_context>

Based ONLY on the above database context, please answer the query. Remember to cite Event IDs (ENTRY_#) for all mentioned events.
"""
        }
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.1,  # Very deterministic for factual queries
        max_tokens=2000
    )

    return response.choices[0].message.content
```

---

## Phase 3: Update Mechanism (Week 2-3)

### 3.1 Update Service

**File**: `app/services/chatbot/update_service.py`

**Responsibilities**:
- Process uploaded Excel files
- Detect changes (new/modified events)
- Generate embeddings for new data
- Atomic database updates
- Track update history

**Key Functions**:
```python
class UpdateService:
    def process_upload(self, excel_file: FileStorage) -> UpdateResult
    def detect_changes(self, new_df: pd.DataFrame, old_df: pd.DataFrame) -> ChangeSet
    def create_backup(self) -> str
    def apply_update(self, changeset: ChangeSet) -> UpdateResult
    def rollback(self, backup_id: str)
    def get_update_history(self) -> List[UpdateRecord]
```

**Update Flow**:
```python
def process_upload(self, excel_file: FileStorage) -> UpdateResult:
    # 1. Save uploaded file
    timestamp = datetime.now().isoformat()
    filepath = f"app/data/chatbot/uploads/DR_database_{timestamp}.xlsx"
    excel_file.save(filepath)

    # 2. Load and validate
    new_df = self.data_processor.load_excel(filepath)
    validation = self.data_processor.validate_data(new_df)
    if not validation['valid']:
        return UpdateResult(success=False, errors=validation['errors'])

    # 3. Detect changes
    old_df = self.load_current_database()
    changeset = self.detect_changes(new_df, old_df)

    if changeset.is_empty():
        return UpdateResult(success=True, message="No changes detected")

    # 4. Create backup
    backup_id = self.create_backup()

    try:
        # 5. Process new/modified events
        new_chunks = self.data_processor.chunk_events(changeset.new_events)

        # 6. Generate embeddings (use Batch API if >100 chunks)
        if len(new_chunks) > 100:
            batch_job = self.embedding_service.embed_batch(new_chunks)
            embeddings = self.embedding_service.wait_for_batch(batch_job.id)
        else:
            embeddings = [self.embedding_service.embed_single(c.text) for c in new_chunks]

        # 7. Update ChromaDB (atomic operation)
        self.vector_store.add_documents(new_chunks, embeddings)

        # 8. Update metadata
        self.update_metadata({
            "last_update": timestamp,
            "total_events": len(new_df),
            "source_file": filepath,
            "changes": {
                "new": len(changeset.new_events),
                "modified": len(changeset.modified_events),
                "deleted": len(changeset.deleted_events)
            }
        })

        return UpdateResult(
            success=True,
            message=f"Update successful: {len(changeset.new_events)} new, {len(changeset.modified_events)} modified events",
            backup_id=backup_id
        )

    except Exception as e:
        # Rollback on failure
        self.rollback(backup_id)
        return UpdateResult(success=False, error=str(e))
```

---

### 3.2 Metadata Service

**File**: `app/services/chatbot/metadata_service.py`

**Responsibilities**:
- Track database version
- Store update history
- Provide system statistics
- Last update timestamp

**Metadata Schema** (`app/data/chatbot/metadata.json`):
```json
{
  "current_version": {
    "id": "v_20251023_143000",
    "timestamp": "2025-10-23T14:30:00Z",
    "source_file": "DR_database_PBI_20251023.xlsx",
    "total_events": 5384,
    "total_chunks": 8756,
    "embedding_model": "text-embedding-3-small",
    "unique_hazards": 1540,
    "unique_locations": 265,
    "date_range": {
      "earliest": "2024-01-02",
      "latest": "2025-10-23"
    }
  },
  "update_history": [
    {
      "version_id": "v_20251023_143000",
      "timestamp": "2025-10-23T14:30:00Z",
      "uploaded_by": "user@example.com",
      "changes": {
        "new_events": 45,
        "modified_events": 3,
        "deleted_events": 0
      },
      "status": "completed",
      "backup_id": "backup_20251023_143000"
    }
  ],
  "statistics": {
    "top_hazards": [
      {"name": "measles", "count": 700},
      {"name": "mpox", "count": 230}
    ],
    "top_locations": [
      {"name": "United States", "count": 1102},
      {"name": "Ontario", "count": 302}
    ]
  }
}
```

**Key Functions**:
```python
class MetadataService:
    def get_last_update(self) -> Dict[str, Any]
    def get_statistics(self) -> Dict[str, Any]
    def get_update_history(self, limit: int = 10) -> List[Dict]
    def update_metadata(self, new_data: Dict)
```

---

## Phase 4: Flask Integration (Week 3)

### 4.1 Routes

**File**: `app/routes/tools/chatbot.py`

**Endpoints**:
```python
# Chat interface
GET  /tools/chatbot                    # Main chat UI
POST /tools/chatbot/query              # Submit query, get response
POST /tools/chatbot/clear              # Clear conversation history

# Upload & updates
GET  /tools/chatbot/upload             # Upload form
POST /tools/chatbot/upload             # Process upload
GET  /tools/chatbot/update-status      # Check update job status

# Admin & metadata
GET  /tools/chatbot/stats              # Database statistics
GET  /tools/chatbot/history            # Update history
```

**Query Endpoint**:
```python
@chatbot_bp.route('/query', methods=['POST'])
@login_required
def query():
    data = request.json
    user_query = data.get('query')
    filters = data.get('filters', {})
    conversation_history = session.get('chatbot_history', [])

    # Process query through RAG pipeline
    service = get_chatbot_service()
    result = service.process_query(
        query=user_query,
        filters=filters,
        conversation_history=conversation_history
    )

    # Update session history
    conversation_history.append({"role": "user", "content": user_query})
    conversation_history.append({"role": "assistant", "content": result['response']})
    session['chatbot_history'] = conversation_history[-10:]  # Keep last 10 messages

    return jsonify({
        'response': result['response'],
        'sources': result['sources'],  # Event IDs cited
        'retrieved_count': result['retrieved_count']
    })
```

**Upload Endpoint**:
```python
@chatbot_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': 'Only .xlsx files allowed'}), 400

    # Start background job for processing
    service = get_chatbot_service()
    job_id = service.start_update(file, current_user.id)

    return jsonify({
        'message': 'Upload started',
        'job_id': job_id,
        'status_url': url_for('chatbot.update_status', job_id=job_id)
    })
```

---

### 4.2 Templates

**Main Chat Interface** (`app/templates/tools/chatbot/index.html`):

**Features**:
- Chat UI with message history
- Typing indicators
- Citation display (Event IDs as badges)
- Filters panel (date range, location, disease)
- Last update timestamp display
- Upload button

**Layout**:
```
┌────────────────────────────────────────────────────┐
│  DR Knowledge Chatbot - Gerardo                    │
│  Last updated: 2025-10-23 14:30:00                 │
│  5,384 events | 1,540 hazards | 265 locations      │
└────────────────────────────────────────────────────┘
┌────────────────┬───────────────────────────────────┐
│  Filters       │  Chat Messages                    │
│  ────────      │  ─────────────                    │
│  Date Range    │  👤 User: Recent Ebola outbreaks  │
│  [2024-01-01]  │                                    │
│  to [Today]    │  🤖 Gerardo:                       │
│                │  Based on the database, I found 3  │
│  Location      │  events:                           │
│  [ USA    ▼]   │                                    │
│                │  Event #00123: Ebola in DRC       │
│  Disease       │  - Date: 2025-09-15               │
│  [ Ebola   ]   │  - Cases: 45 confirmed            │
│                │  [View Details]                    │
│  [Apply]       │                                    │
│                │  ───────────────────────────────  │
│  [Upload New   │                                    │
│   Database]    │  Type your question...            │
│                │  [Send]                            │
└────────────────┴───────────────────────────────────┘
```

**Upload Interface** (`app/templates/tools/chatbot/upload.html`):

**Features**:
- Drag-and-drop file upload
- Validation (file size, format)
- Progress indicator
- Change preview (before confirming)
- Backup management

---

## Phase 5: Testing & Optimization (Week 4)

### 5.1 Testing Strategy

**Unit Tests**:
- Data processing (Excel parsing, chunking)
- Embedding generation (mocking OpenAI API)
- Vector storage (ChromaDB operations)
- RAG pipeline (retrieval, re-ranking)
- Update mechanism (change detection, rollback)

**Integration Tests**:
- End-to-end query flow
- Upload and update flow
- Error handling and rollback
- Conversation context management

**Performance Tests**:
- Query latency (<2 seconds target)
- Concurrent queries (5 users)
- Large update processing (1000+ events)
- Embedding cache hit rate

---

### 5.2 Monitoring

**Metrics to Track**:
```python
{
    "query_metrics": {
        "total_queries": 1250,
        "avg_latency_ms": 1450,
        "cache_hit_rate": 0.73,
        "avg_retrieved_docs": 8.5
    },
    "cost_metrics": {
        "embedding_tokens_month": 125000,
        "embedding_cost_month": 2.50,
        "llm_tokens_month": 2500000,
        "llm_cost_month": 37.50,
        "total_monthly_cost": 40.00
    },
    "database_metrics": {
        "total_events": 5384,
        "total_chunks": 8756,
        "storage_mb": 145,
        "last_update": "2025-10-23T14:30:00Z"
    }
}
```

**Logging**:
```python
import logging

logger = logging.getLogger('chatbot')
logger.setLevel(logging.INFO)

# Log all queries
logger.info(f"Query: {query} | Retrieved: {len(results)} | Latency: {latency_ms}ms")

# Log updates
logger.info(f"Update started: {len(new_events)} new events")
logger.info(f"Update completed: {duration_sec}s | Cost: ${cost}")

# Log errors
logger.error(f"Query failed: {error}", exc_info=True)
```

---

## Implementation Timeline

### Week 1: Core Infrastructure
- **Day 1-2**: Data processing service (Excel → Events → Chunks)
- **Day 3-4**: Embedding service (Batch API integration)
- **Day 5-7**: Vector storage (ChromaDB setup and operations)

### Week 2: RAG Pipeline
- **Day 8-9**: Query processing and enhancement
- **Day 10-11**: Retrieval service (hybrid search + re-ranking)
- **Day 12-14**: Generation service (GPT-4o integration)

### Week 3: Updates & UI
- **Day 15-16**: Update service (upload, detect changes, apply)
- **Day 17-18**: Flask routes and API
- **Day 19-21**: Templates (chat UI, upload UI)

### Week 4: Polish & Deploy
- **Day 22-23**: Testing (unit, integration, performance)
- **Day 24-25**: Monitoring and logging
- **Day 26-28**: Documentation and deployment

---

## File Structure

```
app/
├── services/
│   └── chatbot/
│       ├── __init__.py
│       ├── data_processor.py       # Excel → Events → Chunks
│       ├── embedding_service.py    # OpenAI embeddings + batch
│       ├── vector_store.py         # ChromaDB operations
│       ├── query_processor.py      # Query parsing + enhancement
│       ├── retrieval_service.py    # Hybrid search + re-ranking
│       ├── generation_service.py   # GPT-4o responses
│       ├── update_service.py       # Upload + update mechanism
│       └── metadata_service.py     # Stats + history
│
├── routes/
│   └── tools/
│       └── chatbot.py              # Flask blueprint
│
├── templates/
│   └── tools/
│       └── chatbot/
│           ├── index.html          # Main chat UI
│           ├── upload.html         # Upload interface
│           ├── stats.html          # Statistics dashboard
│           └── history.html        # Update history
│
└── data/
    └── chatbot/
        ├── chroma_db/              # ChromaDB persistent storage
        ├── uploads/                # Uploaded Excel files
        ├── backups/                # Database backups
        ├── metadata.json           # Version + statistics
        └── update_history.json     # Update log
```

---

## Cost Analysis

### One-Time Setup (Initial 5,384 Events)

| Component | Volume | Price | Cost |
|-----------|--------|-------|------|
| Embeddings (Batch) | 2.7M tokens | $0.01/1M | **$0.027** |
| ChromaDB Storage | 145 MB | Free (local) | **$0** |
| **Total** | | | **$0.027** |

### Monthly Operating Costs (1,000 Queries)

| Component | Volume | Price | Monthly Cost |
|-----------|--------|-------|--------------|
| Query Embeddings | 50K tokens | $0.02/1M | $0.001 |
| GPT-4o Input | 2.05M tokens | $5/1M | $10.25 |
| GPT-4o Output | 300K tokens | $15/1M | $4.50 |
| Update Embeddings | 25K tokens | $0.02/1M | $0.001 |
| **Total** | | | **~$15/month** |

### Comparison with Legacy System

| Metric | Legacy (Assistants) | New (RAG) | Savings |
|--------|---------------------|-----------|---------|
| Monthly cost (1K queries) | ~$50 | ~$15 | **70%** |
| Query latency | 3-8 seconds | 1-2 seconds | **50-75%** |
| Control | Limited (black box) | Full | ✅ |
| Deprecation risk | High (2025) | None | ✅ |

---

## Key Success Factors

1. ✅ **Start Simple**: Basic semantic search first, add hybrid later if needed
2. ✅ **Batch Everything**: Use Batch API for all bulk operations (50% savings)
3. ✅ **Cache Aggressively**: Embed query caching, semantic caching, prompt caching
4. ✅ **Monitor Everything**: Track costs, latency, relevance metrics
5. ✅ **Test with Real Queries**: Use actual epidemiologist questions to validate
6. ✅ **Metadata is King**: Dates and locations enable powerful filtering
7. ✅ **Atomic Updates**: Never leave database in inconsistent state
8. ✅ **Keep Backups**: Always allow rollback to previous version

---

## Migration Strategy

### Phase 1: Parallel Operation (Week 1-2)
- Keep legacy system running
- Deploy new system alongside
- Compare responses for same queries
- Validate accuracy and performance

### Phase 2: Gradual Cutover (Week 3)
- Direct 25% of traffic to new system
- Monitor errors and user feedback
- Increase to 50%, then 75%
- Keep legacy as fallback

### Phase 3: Full Migration (Week 4)
- 100% traffic to new system
- Deprecate legacy Assistant API
- Clean up old vector stores
- Delete orchestrator code

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Embedding API failures | Retry logic, exponential backoff, caching |
| ChromaDB corruption | Automated backups every 24h, rollback capability |
| Upload errors | Validation before processing, atomic updates |
| Query latency spikes | Caching, connection pooling, timeout handling |
| Cost overruns | Monthly budget alerts, rate limiting, query optimization |
| Inaccurate responses | Strict system prompts, citation enforcement, user feedback loop |

---

## Future Enhancements (Post-MVP)

1. **Advanced Re-ranking**: Implement query-specific re-rankers
2. **Multi-lingual Support**: Handle non-English disease outbreak reports
3. **Trend Analysis**: Time-series analysis of disease patterns
4. **Geographic Visualization**: Map-based outbreak display
5. **Alert System**: Notify users of new outbreaks matching criteria
6. **API Access**: External API for programmatic queries
7. **Fine-tuned Embeddings**: Custom domain-specific embedding model

---

## Project Requirements (Confirmed)

1. **User Access**: ✅ All authenticated users can upload
2. **Update Frequency**: ✅ Daily updates expected
3. **Backup Retention**: ✅ 2 days (automatic cleanup)
4. **Query Limits**: ✅ 20 queries/minute per user
5. **Response Format**: ✅ Conversational (natural language)
6. **Citation Style**: ✅ Full event details (date, location, summary, references)
7. **Deployment**: ✅ Single instance (local ChromaDB)

### Implementation Adjustments Based on Requirements

**Daily Updates**:
- Optimized for frequent, incremental updates
- Change detection via MD5 hashing to skip unchanged events
- Batch API for large updates (>100 events), direct API for small daily changes
- Quick update processing (<2 minutes for typical daily additions)

**All-User Upload Access**:
- Upload endpoint accessible to all authenticated users
- Track uploader user ID in metadata
- Display upload history with user attribution
- No admin approval required

**2-Day Backup Retention**:
- Automatic cleanup job runs daily
- Keeps only last 2 backups
- Minimal storage footprint (~300 MB max)
- Simple rollback to yesterday's version

**20 Queries/Minute Rate Limiting**:
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=lambda: current_user.id,  # Per-user limiting
    default_limits=["20 per minute"]
)

@chatbot_bp.route('/query', methods=['POST'])
@login_required
@limiter.limit("20/minute")
def query():
    # ... query handling
```

**Full Event Details in Citations**:
```python
# Citation format in conversational responses:
"""
Based on the database, I found 3 recent Ebola outbreaks in West Africa:

**Event #00123 - Ebola in Democratic Republic of Congo**
- Date: 2025-09-15
- Location: North Kivu Province, DRC
- Summary: Health authorities confirmed 45 cases (32 confirmed, 13 probable)
  of Ebola virus disease in North Kivu Province. Contact tracing is ongoing.
- Cases: 45 total (32 confirmed, 13 probable)
- Deaths: 28 (case fatality rate: 62%)
- Source: WHO Disease Outbreak News
  https://www.who.int/emergencies/disease-outbreak-news/item/2025-DON-123

[Additional events with full details...]
"""
```

---

This plan provides a comprehensive roadmap for replacing the deprecated Assistants API with a modern, cost-effective, and maintainable RAG system. The implementation is straightforward, leverages industry best practices, and positions the chatbot for long-term success.

**Requirements confirmed - Ready to begin implementation!** 🚀
