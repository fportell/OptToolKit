**RSS Subscription Manager** is a Node.js web application for managing a large collection of RSS feed subscriptions. It is designed for local use, providing a clean, Bootstrap 5-based interface for browsing, searching, filtering, importing, exporting, and backing up RSS feeds with rich metadata.

---

## Entry point code

```bash
/home/fernando/OpsToolKit/legacy_code/rss-manager/app.js
```


## Database Structure

The application uses **SQLite** as its database, leveraging its FTS5 (Full-Text Search) capabilities for fast searching. The schema is designed for robust metadata management and easy backup/restore.

### Main Tables

#### 1. `rss_subscriptions`

- **Purpose:** Stores all active RSS feed subscriptions.
- **Columns:**
    - `rss_id` (TEXT, PK): Unique SHA-256 hash (first 16 chars) of the feed’s `xml_url`.
    - `xml_url` (TEXT, UNIQUE): The RSS/Atom feed URL.
    - `html_url` (TEXT): The website’s homepage URL.
    - `language` (TEXT): ISO 639-1 code (e.g., `en`, `fr`).
    - `title` (TEXT): Feed or organization name.
    - `type` (TEXT): Organization type (one of 7 allowed types).
    - `scope` (TEXT): Geographic scope (`International`, `National`, `Local`).
    - `country` (TEXT): ISO 3166-1 alpha-3 code (e.g., `USA`, `CAN`, or `INT`).
    - `subdivision` (TEXT): ISO 3166-2 code, `NAT`, or `N/A`.
    - `created_at` (TIMESTAMP): Record creation time.
    - `updated_at` (TIMESTAMP): Last update time.

#### 2. `rss_search`

- **Purpose:** FTS5 virtual table for fast full-text search.
- **Columns:** `rss_id`, `title`, `xml_url`, `html_url`.
- **Sync:** Maintained via triggers on `rss_subscriptions` for insert/update/delete.

#### 3. `deleted_subscriptions`

- **Purpose:** Stores deleted subscriptions for undo/restore.
- **Columns:** All fields from `rss_subscriptions` plus:
    - `id` (INTEGER, PK, AUTOINCREMENT)
    - `deleted_at` (TIMESTAMP): When the record was deleted.

### Indexes & Triggers

- **Indexes:** Composite and single-field indexes for fast filtering (by language, type, country, scope).
- **Triggers:**
    - Keep `rss_search` in sync with `rss_subscriptions`.
    - Move deleted records to `deleted_subscriptions` (soft delete).

---

## How the Frontend Manages the Database

The frontend is built with **EJS templates** and **Bootstrap 5**, providing a responsive, accessible UI. All data operations are performed via Express routes, which interact with the database through model/controller logic.

### Data Management Flows

- **Listing & Filtering:**  
    The main subscriptions page displays feeds in a paginated table. Users can filter by language, type, country, and scope using dropdowns. All filters are reflected in the URL as query parameters, and results are fetched from the database using optimized queries.
    
- **Full-Text Search:**  
    Users can search across titles and URLs using a search box. The search is powered by the FTS5 table, allowing for instant, case-insensitive, and field-specific queries (e.g., `lan:en type:MED`).
    
- **Add/Edit/Delete:**  
    Forms are provided for adding and editing subscriptions. All inputs are validated (ISO codes, URLs, required fields). Deleting a subscription moves it to the `deleted_subscriptions` table, allowing for easy restoration.
    
- **Bulk Operations:**  
    Users can select multiple subscriptions and perform bulk delete or export actions.
    
- **Import/Export:**
    
    - **Import:** Users can upload a JSON file of subscriptions. The system validates all records, detects duplicates, and previews changes before importing.
    - **Export:** Subscriptions can be exported in OPML 2.0 format, grouped by language and with structured prefixes.
- **Backup & Restore:**
    
    - **Manual Backup:** Users can create and download JSON backups of all subscriptions.
    - **Restore:** Deleted subscriptions can be restored from the UI. Full database backups can also be restored via file replacement.

---

## Features Implemented

### Core Features

- **Subscription Management:**  
    Add, edit, delete, and restore RSS feed subscriptions with rich metadata.
    
- **Advanced Filtering:**  
    Filter feeds by language, country, organization type, and scope.
    
- **Full-Text Search:**  
    Fast, field-specific search using SQLite FTS5, with support for advanced query syntax.
    
- **Bulk Operations:**  
    Select multiple feeds for bulk deletion or export.
    
- **OPML Export:**  
    Export all, selected, or filtered subscriptions to OPML 2.0, with custom collection names and structured prefixes.
    
- **JSON Import:**  
    Import subscriptions from JSON files, with validation, duplicate detection, and preview.
    
- **Backup & Restore:**
    
    - Web-based interface for creating and downloading JSON backups.
    - Restore deleted subscriptions from the UI.
    - Command-line backup and restore options.

### User Interface

- **Responsive Design:**  
    Bootstrap 5-based, works on all devices.
    
- **Pagination Controls:**  
    Flexible per-page limits (25/50/100/250/500/All).
    
- **Interactive Dashboard:**  
    Overview statistics, recent activity, and quick actions.
    
- **Flash Messages:**  
    User-friendly notifications for success and errors.
    
- **Tooltips & Help:**  
    Contextual help and advanced search syntax documentation.
    

### Data Organization

- **Multi-dimensional Classification:**  
    Feeds are classified by language, country, subdivision, organization type, and scope.
    
- **Automatic Prefix Generation:**  
    Structured naming for OPML export (e.g., `en-USA-CA-MED`).
    
- **Soft Deletes:**  
    Deleted subscriptions are backed up for recovery.
    

### Technical Features

- **SQLite Database:**  
    Embedded, lightweight, with FTS5 for search.
    
- **MVC Architecture:**  
    Clean separation of models, views, and controllers.
    
- **Security:**  
    Helmet.js for security headers, session management, input validation, parameterized queries.
    
- **Performance:**  
    Compression, indexed queries, efficient pagination.
    
- **Logging:**  
    Winston-based logging with daily rotation and error logs.
    

---

## Summary Table of Features

|Feature|Description|
|---|---|
|Add/Edit/Delete Feeds|Manage subscriptions with full metadata|
|Filtering|By language, country, type, scope|
|Full-Text Search|Fast, advanced, field-specific search|
|Bulk Operations|Bulk delete and export|
|OPML Export|Export all/selected/filtered feeds with structured prefixes|
|JSON Import|Import with validation, duplicate detection, preview|
|Backup & Restore|Manual and automatic backups, restore deleted feeds|
|Pagination|Flexible per-page limits|
|Dashboard|Stats, recent activity, quick actions|
|Flash Messages|Success/error notifications|
|Security|Helmet, input validation, parameterized queries|
|Logging|Winston logs, daily rotation, error separation|
|Responsive UI|Bootstrap 5, accessible, works on all devices|

---

**In summary:**  
The RSS Subscription Manager is a robust, local-first web app for managing large RSS feed collections, with a well-structured SQLite database, a modern Bootstrap 5 UI, and a full suite of features for filtering, searching, importing, exporting, backup, and restore. All data operations are managed through a clean MVC architecture, ensuring maintainability and extensibility.
