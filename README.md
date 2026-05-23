# OrbitAI

OrbitAI is a personal AI information radar.

It is designed to automatically collect, organize, and display AI-related information from sources such as RSS feeds, webpages, and APIs.

The early goal of OrbitAI is not to build a large online platform immediately, but to first create a local, runnable information system.

## Project Goal

The basic workflow is:

```text
RSS / Webpage / API
        ↓
Python script
        ↓
Save as data.json
        ↓
Generate local index.html
        ↓
Open in browser
```

## Current Version

### V1.0 - RSS Fetching and Terminal Output

Current status: completed.

In V1.0, OrbitAI can:

- Fetch AI-related information from RSS sources
- Print article titles in the terminal
- Print source names
- Print article links
- Print publication times

Run:

```bash
python main.py
```

Example output:

```text
========== OpenAI News ==========

Title: ...
Time: ...
Link: ...
```

## Current Project Structure

```text
OrbitAI/
├─ main.py              # Main Python script for RSS fetching
├─ requirements.txt     # Python dependencies
├─ README.md            # Project documentation
└─ OrbitAI路线图.docx    # Project roadmap
```

## Installation

Install dependencies:

```bash
pip install -r requirements.txt
```

If the network has trouble connecting to PyPI, configure the terminal proxy first.

Example for PowerShell:

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7897"
$env:HTTPS_PROXY="http://127.0.0.1:7897"
```

Then run:

```bash
pip install -r requirements.txt
```

## Roadmap

### V1.x - Local Basic Version

- V1.0: Fetch RSS feeds and print results in the terminal
- V1.1: Save fetched data to `data.json`
- V1.2: Generate local `index.html`
- V1.3: Add search and basic classification
- V1.4: Improve local user experience

### V2.x - AI Enhanced Version

Future versions will add:

- AI summaries
- Chinese translation
- AI classification
- Keyword extraction
- Importance scoring
- Daily AI briefings

### V3.x - Website Version

Future website versions may include:

- FastAPI backend
- SQLite database
- Frontend pages
- Server deployment
- Automatic scheduled updates

## Development Principle

OrbitAI follows these principles:

1. Build the basic workflow first.
2. Do not add AI features too early.
3. Start with RSS before webpage scraping and APIs.
4. Use code for deterministic tasks such as deduplication, sorting, filtering, and storage.
5. After each version, test, summarize, and push to GitHub.

## About

OrbitAI is currently a learning-oriented personal project.

Its long-term direction is to become a personal AI information radar that helps users track important AI updates without being overwhelmed by information noise.