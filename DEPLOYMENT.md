# OpsToolKit Deployment Guide

## Overview

This guide explains how to deploy OpsToolKit from GitHub to a new server. After cloning, you only need to update the `.env` file - all required databases and configuration are included in the repository.

## What's Included in the Repository

### ✅ Application Files (Committed)

- **Source Code**: All Python modules, templates, static files
- **Configuration Templates**: `.env.example`, `requirements.txt`
- **Static Databases**:
  - `app/data/chatbot/DR_database_PBI.xlsx` (5.2MB) - Epidemiological events database
  - `app/data/rss_subscriptions.db` (2MB) - RSS subscriptions
- **Configuration Data**:
  - `app/data/dr_tracker/idc_hazards.json` - Hazard classifications
  - `app/data/dr_tracker/idc_hazards_hierarchical.json` - Hierarchical hazards
  - `app/data/dr_tracker/program_areas.json` - Program area mappings
  - `app/data/dr_tracker/gpt4_dr2tracker_preprompt.txt` - GPT-4 prompts
  - `app/data/dr_tracker/vbaProject.bin` - Excel VBA macros

### ❌ Auto-Generated (NOT in Repository)

These are generated automatically on first run and should NOT be committed:

- **Vector Store**: `app/data/chatbot/chroma_db/` (234MB)
  - Regenerated from `DR_database_PBI.xlsx` on first run
  - Takes ~2-3 minutes to initialize
- **Caches**:
  - `app/data/chatbot/embedding_cache/` - OpenAI embedding cache
- **Runtime Metadata**:
  - `app/data/chatbot/metadata.json` - Database statistics
  - `app/data/chatbot/DR_database_PBI_metadata.json` - File hashes
- **Temporary Data**:
  - `app/data/chatbot/uploads/` - User uploads
  - `app/data/chatbot/backups/` - Database backups
- **Session Data**: `flask_session/` - User sessions
- **Logs**: `logs/` - Application logs
- **Environment**:
  - `venv/` - Python virtual environment
  - `.env` - Environment configuration (contains secrets)

## Deployment Steps

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/OpsToolKit.git
cd OpsToolKit
```

### 2. Set Up Environment Configuration

```bash
# Copy the template
cp .env.example .env

# Generate a secure session secret
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Edit .env File

Open `.env` in your editor and update these **required** values:

```bash
# Authentication (REQUIRED)
APP_USERNAME=your_admin_username
APP_PASSWORD=your_secure_password

# Session Secret (REQUIRED - use output from step 2)
SESSION_SECRET=paste_the_generated_secret_here

# OpenAI API Key (REQUIRED)
OPENAI_API_KEY=sk-your-openai-api-key-here
```

### 4. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 5. Create Required Directories

```bash
mkdir -p logs
```

### 6. Run the Application

#### Development Mode

```bash
source venv/bin/activate  # If not already activated
python app.py
```

Access at: `http://localhost:5000`

#### Production Mode

Update `.env` for production:

```bash
FLASK_ENV=production
FLASK_DEBUG=false
HTTPS_ENABLED=true
SECURE_COOKIES=true
```

Install and run with Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

## First Run Initialization

On first startup, the application will:

1. **Load the Excel database** (`DR_database_PBI.xlsx`)
2. **Generate embeddings** for all events (using OpenAI API)
3. **Build ChromaDB vector store** (~2-3 minutes)
4. **Create metadata files** for tracking updates

You'll see log messages like:

```
[INFO] Loading knowledge base from: app/data/chatbot/DR_database_PBI.xlsx
[INFO] Extracted 5000 events, 12000 chunks
[INFO] Generating embeddings for 12000 chunks...
[INFO] Collection ready: epidemiological_events (12000 documents)
```

## Environment Configuration

### Minimal Configuration (Development)

```bash
APP_USERNAME=admin
APP_PASSWORD=SecurePassword123!
SESSION_SECRET=<generated-secret>
OPENAI_API_KEY=sk-...
```

### Recommended Production Configuration

```bash
# Authentication
APP_USERNAME=your_username
APP_PASSWORD=your_strong_password

# Security
SESSION_SECRET=<generated-secret-64-chars>
FLASK_ENV=production
FLASK_DEBUG=false
HTTPS_ENABLED=true
SECURE_COOKIES=true

# OpenAI
OPENAI_API_KEY=sk-...

# Session Management
SESSION_ACTIVITY_TIMEOUT=14400  # 4 hours
SESSION_INACTIVITY_TIMEOUT=1800  # 30 minutes
SESSION_TYPE=filesystem          # or 'redis' for production

# Concurrency
MAX_CONCURRENT_USERS=5
OPENAI_QUEUE_ENABLED=true

# Rate Limiting
RATE_LIMIT_LOGIN=5
RATE_LIMIT_AI_OPERATIONS=20
```

## Updating the Database

The chatbot uses `app/data/chatbot/DR_database_PBI.xlsx` as the source of truth. To update:

### Option 1: Upload via Web Interface

1. Log in to OpsToolKit
2. Navigate to **DR Knowledge Chatbot**
3. Click **Upload Database**
4. Select new Excel file
5. The system will:
   - Detect changes
   - Update ChromaDB
   - Regenerate embeddings
   - Create backup

### Option 2: Replace File Directly

1. Replace `app/data/chatbot/DR_database_PBI.xlsx`
2. Delete the vector store: `rm -rf app/data/chatbot/chroma_db/`
3. Restart the application
4. Vector store will regenerate on startup

## Server Requirements

### Minimum

- **Python**: 3.12 or higher
- **Memory**: 2GB RAM
- **Storage**: 500MB (1GB recommended with embeddings cache)
- **Network**: Outbound HTTPS for OpenAI API

### Recommended (Production)

- **Python**: 3.12
- **Memory**: 4GB RAM
- **Storage**: 2GB SSD
- **CPU**: 2+ cores
- **OS**: Ubuntu 22.04 LTS or similar
- **Reverse Proxy**: Nginx or Apache with SSL

## Monitoring & Maintenance

### Health Checks

Monitor these endpoints:

- `/` - Should return 200 with login page
- `/api/health` - Application health status (if implemented)

### Log Files

```bash
# View application logs
tail -f logs/opstoolkit.log

# Check for errors
grep ERROR logs/opstoolkit.log
```

### Database Backups

Automated backups are created in `app/data/chatbot/backups/` when updating the database via the web interface. Keep these backed up separately.

### Disk Space

Monitor these directories:

```bash
# Check vector store size
du -sh app/data/chatbot/chroma_db/

# Check embedding cache
du -sh app/data/chatbot/embedding_cache/

# Check logs
du -sh logs/
```

## Troubleshooting

### Vector Store Won't Initialize

**Symptom**: "Knowledge base not loaded" message

**Solution**:
```bash
# Delete and regenerate
rm -rf app/data/chatbot/chroma_db/
rm -rf app/data/chatbot/metadata.json
# Restart application
```

### OpenAI API Errors

**Symptom**: 401 Unauthorized errors

**Solution**:
- Verify `OPENAI_API_KEY` in `.env`
- Check API key at https://platform.openai.com/api-keys
- Ensure sufficient credits in OpenAI account

### Chatbot Timeout Errors

**Symptom**: "Request did not complete within 30s"

**Fix**: Already implemented! Timeout increased to 90s with user feedback.

### Session Expired Too Quickly

**Solution**: Adjust timeouts in `.env`:
```bash
SESSION_ACTIVITY_TIMEOUT=28800  # 8 hours
SESSION_INACTIVITY_TIMEOUT=3600  # 1 hour
```

## Migration from Development to Production

1. **Backup your database**:
   ```bash
   cp app/data/chatbot/DR_database_PBI.xlsx ~/backup/
   cp app/data/rss_subscriptions.db ~/backup/
   ```

2. **Update .env for production** (see configuration above)

3. **Set up reverse proxy** (Nginx example):
   ```nginx
   server {
       listen 443 ssl;
       server_name opstoolkit.example.com;

       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

4. **Set up systemd service** (optional):
   ```ini
   [Unit]
   Description=OpsToolKit Flask Application
   After=network.target

   [Service]
   Type=simple
   User=opstoolkit
   WorkingDirectory=/home/opstoolkit/OpsToolKit
   Environment="PATH=/home/opstoolkit/OpsToolKit/venv/bin"
   ExecStart=/home/opstoolkit/OpsToolKit/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app()"
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

## Security Considerations

### Production Checklist

- [ ] Use strong, unique `APP_PASSWORD`
- [ ] Generate secure `SESSION_SECRET` (64+ characters)
- [ ] Set `HTTPS_ENABLED=true`
- [ ] Set `SECURE_COOKIES=true`
- [ ] Use HTTPS/SSL certificate
- [ ] Enable firewall (allow only 443, 22)
- [ ] Keep OpenAI API key secure
- [ ] Regularly update dependencies
- [ ] Monitor logs for suspicious activity
- [ ] Set up regular database backups

### Secrets Management

Never commit these to Git:
- `.env` file
- OpenAI API keys
- Session secrets
- Passwords

Always use environment variables or secret management services.

## Support

For issues or questions:
1. Check logs: `logs/opstoolkit.log`
2. Review this guide
3. Consult README.md for feature documentation
4. Create an issue in the GitHub repository

---

**Last Updated**: 2025-10-27
**Version**: 1.0
