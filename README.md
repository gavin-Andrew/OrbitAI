```markdown
# OrbitAI

OrbitAI is a personal AI information radar.

It collects AI-related information from RSS feeds, processes the information with AI, saves structured data locally, and generates local HTML pages for reading and review.

The current goal of OrbitAI is not to become a large online platform immediately, but to first build a stable local information system that can run reliably on a personal computer.

---

## Current Version

### V2.7 - AI Enhanced Local Stable Version

Current status: completed.

OrbitAI V2.7 can:

- Fetch AI-related information from RSS sources
- Save structured information to `data.json`
- Avoid duplicated articles by checking existing links
- Use DeepSeek API to generate:
  - Chinese title
  - Chinese summary
  - AI category
  - Tags
  - Multi-dimensional scores
  - `final_score`
- Generate three local HTML pages:
  - `index.html`: all information
  - `featured.html`: selected high-value information
  - `daily.html`: today's newly fetched information
- Retry unstable RSS requests
- Use `certifi` to improve Python HTTPS certificate verification
- Record AI processing errors with:
  - `error`
  - `error_type`
  - `failed_at`
  - `retry_count`

---

## Basic Workflow

```text
sources.json
    ↓
Load RSS sources
    ↓
Fetch RSS feeds
    ↓
Deduplicate by link
    ↓
Create new structured items
    ↓
AI processing
    ↓
Save to data.json
    ↓
Generate local HTML pages
    ↓
Open in browser
```

---

## Project Structure

```text
OrbitAI/
├─ main.py
├─ requirements.txt
├─ README.md
├─ sources.json
├─ .env
├─ .gitignore
│
├─ orbitai/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ data_utils.py
│  ├─ text_utils.py
│  ├─ scoring.py
│  ├─ rss_fetcher.py
│  ├─ ai_client.py
│  ├─ ai_processor.py
│  └─ html_generator.py
│
├─ data.json          # generated, ignored by Git
├─ index.html         # generated, ignored by Git
├─ featured.html      # generated, ignored by Git
└─ daily.html         # generated, ignored by Git
```

---

## Main Modules

### `main.py`

Main workflow controller.

It coordinates the whole process:

1. Load existing data
2. Load RSS sources
3. Fetch new RSS items
4. Process items with AI
5. Save data
6. Generate HTML pages

---

### `orbitai/config.py`

Central configuration file.

It manages:

- File paths
- AI provider settings
- AI model settings
- RSS retry settings
- AI categories
- Score keys
- Final score weights
- Featured page thresholds

---

### `orbitai/data_utils.py`

Data loading, saving, migration, and item creation.

It handles:

- Reading `data.json`
- Saving `data.json`
- Migrating old data into V2.x structure
- Creating new article items
- Creating empty AI fields
- Deduplicating links

---

### `orbitai/rss_fetcher.py`

RSS source loading and RSS fetching.

It handles:

- Reading `sources.json`
- Loading enabled RSS sources
- Fetching RSS content
- Retrying failed RSS requests
- Adding User-Agent
- Using `certifi` for SSL certificate verification
- Parsing RSS entries
- Creating new article items

---

### `orbitai/ai_client.py`

DeepSeek REST API client.

It handles:

- Creating the AI client configuration
- Sending chat completion requests
- Handling HTTP errors
- Handling connection errors
- Parsing API responses

---

### `orbitai/ai_processor.py`

AI information processing.

It handles:

- Prompt construction
- AI JSON extraction
- Chinese title generation
- Chinese summary generation
- AI category normalization
- Tag normalization
- Multi-dimensional scoring
- Error recording
- Retry count recording

---

### `orbitai/scoring.py`

Scoring logic.

It handles:

- Score normalization
- `final_score` calculation
- Sorting by score
- Selecting featured items

---

### `orbitai/html_generator.py`

HTML page generation.

It generates:

- `index.html`
- `featured.html`
- `daily.html`

---

### `orbitai/text_utils.py`

Text utility functions.

It handles:

- Cleaning HTML from RSS summaries
- Truncating long text

---

## Generated Files

The following files are generated automatically and should not be committed to GitHub:

```text
data.json
index.html
featured.html
daily.html
```

They are ignored by `.gitignore`.

---

## Environment Variables

Create a local `.env` file in the project root.

Example:

```env
AI_PROVIDER=deepseek
AI_API_KEY=your_deepseek_api_key
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-v4-flash
AI_BATCH_LIMIT=5
AI_INPUT_SUMMARY_MAX_CHARS=1800
AI_MAX_TOKENS=1200

RSS_MAX_ITEMS_PER_SOURCE=5
RSS_RETRY_TIMES=3
RSS_RETRY_DELAY_SECONDS=2
RSS_TIMEOUT_SECONDS=20
```

Do not commit `.env` to GitHub.

---

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

---

## Usage

Run:

```bash
python main.py
```

After running, OrbitAI will generate:

```text
index.html
featured.html
daily.html
```

Open them in your browser to read the collected AI information.

---

## Version History

### V1.x - Local Basic Version

- V1.0: Fetch RSS feeds and print results in the terminal
- V1.1: Save fetched data to `data.json`
- V1.2: Generate local `index.html`
- V1.3: Add search and basic classification
- V1.4: Improve local user experience

### V2.x - AI Enhanced Version

- V2.0: Prepare AI data structure
- V2.1: Add DeepSeek API integration
- V2.2: Add AI classification and tag extraction
- V2.3: Add AI multi-dimensional scoring and `final_score`
- V2.4: Add `featured.html` selected information page
- V2.5: Refactor code into modules
- V2.6: Add `daily.html` daily briefing page
- V2.7: Improve local stability, RSS retry logic, configuration management, and AI error recording

---

## Known Issues

### DeepSeek connection instability

DeepSeek API requests may occasionally fail due to network or service instability.

Current behavior:

- Failed AI processing is recorded in the item
- The failed item may be retried in later runs
- Error type, error message, failed time, and retry count are stored

Possible future improvement:

- Add a retry threshold
- If `retry_count >= 3`, temporarily skip AI processing for that item
- Keep the article in the dataset but avoid repeated API consumption

---

## Development Principle

OrbitAI follows these principles:

1. Build a runnable local workflow first.
2. Keep deterministic logic in code.
3. Use AI for language understanding, summarization, classification, tagging, and scoring.
4. Keep generated data and generated pages out of Git.
5. After each version, test, summarize, and push to GitHub.
6. Prefer stable small improvements over large risky rewrites.

---

## About

OrbitAI is a learning-oriented personal project.

Its long-term direction is to become a personal AI information radar that helps users track important AI updates without being overwhelmed by information noise.
```