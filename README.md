# OpsToolKit - Integrated Tools Platform

**Version 0.1.0**

A unified web application integrating 5 operational tools with AI-powered features, session management, and a professional Bootstrap 5 interface.

## 🚀 Features

### 🔐 Authentication & Security
- Single-user authentication with Flask-Login
- Session timeouts: 4 hours activity OR 30 minutes inactivity
- Automatic session recovery (unsaved work preserved in browser)
- Secure password handling with timing-attack resistance

### 🛠️ Integrated Tools

1. **Geolocation Tool** - GPS coordinate extraction from images
   - Extract GPS data from JPEG/PNG EXIF metadata
   - Interactive maps with Folium (OpenStreetMap, Satellite, Terrain)
   - Marker clustering, path mode, fullscreen controls
   - Export coordinates as JSON

2. **Summary Revision** - AI-powered text improvement
   - OpenAI GPT-4 integration
   - 5 revision types: General, Professional, Concise, Detailed, Grammar
   - Side-by-side comparison view
   - Custom instructions support

3. **DR-Tracker Builder** - Structured report generation
   - Natural language to structured DR entries
   - AI-powered parsing with OpenAI GPT-4
   - Export to CSV, JSON, XLSX with color formatting
   - Entry validation and error reporting

4. **DR Knowledge Chatbot** - Semantic search and conversational AI
   - Sentence-transformers for semantic search (all-MiniLM-L6-v2)
   - Real-time chat interface with AJAX
   - Context-aware responses via OpenAI GPT-4
   - Chat history management (20 messages)

5. **RSS Manager** - Feed subscription management
   - Integration with Node.js Express service
   - Add, view, update, delete RSS feeds
   - View feed entries in modal dialog
   - Service health monitoring

### ⚡ Performance & Scalability
- OpenAI request queuing for rate limit management
- Active user tracking (max 5 concurrent users)
- Performance warning system
- Configurable timeouts and limits

## 📋 Requirements

### System Requirements
- Python 3.12+
- Node.js 22+ (for RSS Manager)
- 4GB RAM minimum
- OpenAI API key

### Python Dependencies
See `requirements.txt` for full list. Key dependencies:
- Flask 3.0.0
- Flask-Login 0.6.3
- Flask-Session 0.5.0
- OpenAI 1.12.0
- Pillow (for image processing)
- Folium (for maps)
- sentence-transformers 2.5.0
- pandas, xlsxwriter
- pytest (testing)

## 🔧 Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd OpsToolKit
```

### 2. Set Up Python Environment
```bash
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create `.env` file (use `.env.example` as template):

```bash
# Authentication
APP_USERNAME=admin
APP_PASSWORD=your-secure-password
SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Session Management
SESSION_ACTIVITY_TIMEOUT=14400  # 4 hours
SESSION_INACTIVITY_TIMEOUT=1800  # 30 minutes

# Concurrency
MAX_CONCURRENT_USERS=5
OPENAI_QUEUE_ENABLED=true

# File Uploads
MAX_UPLOAD_SIZE_MB=10
DR_TRACKER_TIMEOUT_SECONDS=120

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/opstoolkit.log
```

### 4. Initialize Directories
```bash
mkdir -p logs
mkdir -p instance/uploads
```

## 🚀 Running the Application

### Development Mode
```bash
export FLASK_APP=wsgi.py
export FLASK_ENV=development
flask run
```

Or use the WSGI entry point:
```bash
python wsgi.py
```

Access at: http://localhost:5000

### Production Mode
```bash
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

#### Gunicorn Worker Configuration

The `-w` (workers) parameter should be tuned based on your hardware:

**General formula:** `(2 × num_cores) + 1`

**OpsToolKit-specific recommendations** (I/O-bound application):
- **2 CPUs:** `gunicorn -w 3` or `-w 4` (3-4 workers, ~3-4GB RAM needed)
- **4 CPUs:** `gunicorn -w 4` to `-w 6` (4-6 workers, ~6-8GB RAM needed)
- **8 CPUs:** `gunicorn -w 8` to `-w 12` (8-12 workers, ~8-12GB RAM needed)

**Key considerations:**
- Each worker loads the full app + ML models (~1GB per worker)
- More workers help with I/O-bound tasks (OpenAI API calls, file uploads)
- Start with `workers = num_cores` and tune based on CPU/memory monitoring
- For low-traffic deployments (2-3 users), 2-3 workers is sufficient

**Example configurations:**
```bash
# Small deployment (2 CPUs, 4GB RAM, 2-3 users)
gunicorn -w 3 -b 0.0.0.0:5000 wsgi:app

# Standard deployment (4 CPUs, 6-8GB RAM, 3-5 users)
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app

# High-traffic deployment (8 CPUs, 12GB RAM, 10+ users)
gunicorn -w 10 -b 0.0.0.0:5000 wsgi:app
```

## 🧪 Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
pytest tests/test_services.py

# Integration tests
pytest tests/test_routes.py

# Performance tests
pytest tests/test_performance.py -m performance

# Skip slow tests
pytest -m "not slow"
```

### Coverage Report
```bash
pytest --cov=app --cov-report=html --cov-report=term-missing
```

View HTML report: `htmlcov/index.html`

## 📊 Success Criteria Validation

The application meets all success criteria:

- **SC-001**: Login page load time p95 < 500ms ✅
- **SC-002**: Tools landing page load time p95 < 1000ms ✅
- **SC-003**: Geolocation processing time p95 < 3000ms ✅
- **SC-004**: Supports 5 concurrent active users ✅

Run performance tests to validate:
```bash
pytest tests/test_performance.py -v
```

## 📁 Project Structure

```
OpsToolKit/
├── app/
│   ├── __init__.py           # Flask application factory
│   ├── auth.py               # Authentication module
│   ├── config.py             # Configuration management
│   ├── session_manager.py    # Session timeout handling
│   ├── concurrency_manager.py # User tracking & OpenAI queue
│   ├── routes/
│   │   ├── landing.py        # Login, logout, tools page
│   │   └── tools/            # Tool-specific routes
│   │       ├── geolocation.py
│   │       ├── summary_revision.py
│   │       ├── dr_tracker.py
│   │       ├── chatbot.py
│   │       └── rss_manager.py
│   ├── services/             # Business logic
│   │   ├── geolocation/
│   │   ├── summary_revision/
│   │   ├── dr_tracker/
│   │   └── chatbot/
│   ├── templates/            # Jinja2 templates
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── landing.html
│   │   └── tools/
│   └── static/               # CSS, JavaScript
│       ├── css/styles.css
│       └── js/
│           ├── main.js
│           └── session_recovery.js
├── tests/                    # Test suite
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_routes.py
│   ├── test_services.py
│   └── test_performance.py
├── legacy_code/
│   └── rss-manager/          # Node.js RSS Manager
├── .env.example              # Environment template
├── requirements.txt          # Python dependencies
├── pytest.ini                # Test configuration
├── wsgi.py                   # WSGI entry point
└── README.md                 # This file
```

## 🔒 Security Considerations

### Implemented Security Measures
- Session-based authentication with Flask-Login
- CSRF protection (Flask-WTF)
- Secure password comparison (secrets.compare_digest)
- HTML escaping in templates
- Input validation and sanitization
- Configurable HTTPS and secure cookies
- Rate limiting via OpenAI queue
- Session timeout enforcement

### Production Deployment Checklist
- [ ] Set strong SESSION_SECRET (32+ bytes)
- [ ] Enable HTTPS (HTTPS_ENABLED=true)
- [ ] Enable secure cookies (SECURE_COOKIES=true)
- [ ] Use environment variables for secrets
- [ ] Configure proper file permissions
- [ ] Set up log rotation
- [ ] Enable firewall rules
- [ ] Use reverse proxy (nginx)
- [ ] Set up SSL/TLS certificates
- [ ] Regular dependency updates

## 🛠️ Configuration

### Session Management
- `SESSION_ACTIVITY_TIMEOUT`: Maximum session duration (default: 14400s / 4h)
- `SESSION_INACTIVITY_TIMEOUT`: Inactivity timeout (default: 1800s / 30min)
- `SESSION_TYPE`: Storage type ('filesystem' or 'redis')

### File Uploads
- `MAX_UPLOAD_SIZE_MB`: Maximum file size (default: 10 MB)
- `DR_TRACKER_TIMEOUT_SECONDS`: DR generation timeout (default: 120s)

### AI Configuration
- `SUMMARY_REVISION_MODEL`: Model for text revision (default: 'gpt-4.1')
- `DR_TRACKER_MODEL`: Model for DR generation (default: 'gpt-4.1')
- `CHATBOT_MODEL`: Model for chatbot responses (default: 'gpt-4.1')

### Concurrency
- `MAX_CONCURRENT_USERS`: Maximum concurrent users (default: 5)
- `OPENAI_QUEUE_ENABLED`: Enable request queuing (default: true)

## 📚 API Documentation

### Authentication Endpoints
- `GET /auth/login` - Display login form
- `POST /auth/login` - Process login (username, password)
- `POST /auth/logout` - Logout current user
- `GET /health` - Health check endpoint

### Tool Endpoints
Each tool has its own route namespace:
- `/tools/geolocation/*` - Geolocation tool
- `/tools/summary-revision/*` - Summary revision tool
- `/tools/dr-tracker/*` - DR-Tracker builder
- `/tools/chatbot/*` - DR Knowledge chatbot
- `/tools/rss-manager/*` - RSS Manager

See individual route files for detailed API specifications.

## 🐛 Troubleshooting

### Common Issues

**Issue**: "OPENAI_API_KEY not configured"
- **Solution**: Set `OPENAI_API_KEY` in `.env` file

**Issue**: "RSS Manager service not available"
- **Solution**: Start Node.js service: `cd legacy_code/rss-manager && npm start`

**Issue**: "No module named 'app'"
- **Solution**: Ensure virtual environment is activated and dependencies installed

**Issue**: "Session expired too quickly"
- **Solution**: Adjust `SESSION_ACTIVITY_TIMEOUT` and `SESSION_INACTIVITY_TIMEOUT` in `.env`

**Issue**: Performance degradation with multiple users
- **Solution**: Enable `OPENAI_QUEUE_ENABLED=true` to queue API requests

## 📝 License

See LICENSE file for details.

## 🤝 Contributing

This is a prototype/single-user application. For production use, consider:
- Migrating to multi-user authentication (Auth0, Okta)
- Implementing role-based access control
- Adding database backend (PostgreSQL)
- Scaling with Redis for session storage
- Implementing WebSockets for real-time updates
- Adding comprehensive logging and monitoring

## 📧 Support

For issues and questions, please refer to the project documentation or create an issue in the repository.

---

**Built with Flask, Bootstrap 5, and OpenAI GPT-4**

🤖 Generated with [Claude Code](https://claude.com/claude-code)
