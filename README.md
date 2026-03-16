# NinjaOne Activity Downloader

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![HTTPX](https://img.shields.io/badge/httpx-async-blue)](https://www.python-httpx.org/)
[![SQLite](https://img.shields.io/badge/sqlite-3-003b57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Gemini 3.1](https://img.shields.io/badge/Developed%20with-Gemini%203.1-8E75B2?logo=google-gemini&logoColor=white)](https://deepmind.google/technologies/gemini/)

A high-performance, asynchronous Python tool for exporting raw activity data from multiple NinjaOne accounts into a local SQLite database. This serves as a robust local mirror for auditing, analysis, or as a source for an OCSF translation layer.

## Key Features

- **Concurrent Performance**: Built on `asyncio` and `httpx` to process multiple accounts simultaneously.
- **Resumable Sync**: Logic that fetches new events forward and resumes interrupted historical downloads backward.
- **Optimized Storage**: Uses SQLite Write-Ahead Logging (WAL) and background thread offloading for non-blocking I/O.
- **CLI Interface**: Real-time progress tracking via `rich` for high-level monitoring across accounts.
- **Reliability**: Jittered exponential backoff to handle rate limits and transient network issues.

## Getting Started

### 1. Prerequisites
- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (recommended for dependency management)

### 2. Setup
```bash
# Clone and enter the project
cd NinjaOne_Activity_Downloader

# Sync dependencies
uv sync

# Configure credentials
cp .env.example .env
```
Edit the `.env` file to include your NinjaOne API credentials in the `NINJAONE_ACCOUNTS_JSON` array.

### 3. Execution
```bash
# Standard sync
uv run main.py

# Time-bounded sync (e.g., 60 seconds)
uv run main.py --max-duration 60

# Diagnostic log mode
uv run main.py --show-log
```

## Expanding the Project

### Scheduled Ingestion (Cron)
Because the downloader internally tracks the cursor state for every account and prevents duplicates, it is safe and highly efficient to run it repeatedly.
For a simple daily or hourly sync on a Linux/macOS server, use cron:

```bash
# Example: Run the sync every hour at minute 0
0 * * * * cd /path/to/NinjaOne_Activity_Downloader && /path/to/uv run main.py --max-duration 300
```
*Note: Using `--max-duration` in a cron job ensures that if the API is exceptionally slow, the job won't hang and overlap with the next hour's run.*

### Browsing the Data (Datasette + Cloudflare Tunnel)
You can easily turn the raw SQLite database into a beautiful, searchable, and shareable web interface using Datasette and secure it with Cloudflare.

1. **Install Datasette:**
   ```bash
   uv pip install datasette
   ```
2. **Launch the Interface:**
   ```bash
   uv run datasette activities.sqlite3 -p 8001
   ```
   *You can now browse your data locally at `http://localhost:8001`.*

3. **Secure Remote Access (Optional):**
   To share this securely with your team without exposing ports, use Cloudflare Tunnels:
   ```bash
   cloudflared tunnel --url http://localhost:8001
   ```
   *You can attach a Cloudflare Access Policy to this tunnel to require Google or Entra SSO before viewing the data.*

## Configuration Flags

- `--max-duration [SECONDS]`: Bounds execution time per account. Useful for periodic jobs or limited sync windows. The script checkpoints progress automatically.
- `--show-log`: Switches output from progress bars to standard diagnostic logs.
- `--page-size [NUMBER]`: Overrides the default number of items fetched per API request (default/max is 1000).

## Design Philosophy

- **Data Integrity**: Uses a deterministic `dedupe_key` to prevent duplicate activities, even with overlapping API response windows.
- **API Efficiency**: Respects the NinjaOne Activities API reverse-chronological structure, utilizing cursors to minimize data transfer.
- **Landing Zone Pattern**: The SQLite database acts as a raw landing zone, allowing downstream tools to transform JSON data into OCSF or other target formats.
