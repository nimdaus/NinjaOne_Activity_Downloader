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

## Configuration Flags

- `--max-duration [SECONDS]`: Bounds execution time per account. Useful for periodic jobs or limited sync windows. The script checkpoints progress automatically.
- `--show-log`: Switches output from progress bars to standard diagnostic logs.

## Design Philosophy

- **Data Integrity**: Uses a deterministic `dedupe_key` to prevent duplicate activities, even with overlapping API response windows.
- **API Efficiency**: Respects the NinjaOne Activities API reverse-chronological structure, utilizing cursors to minimize data transfer.
- **Landing Zone Pattern**: The SQLite database acts as a raw landing zone, allowing downstream tools to transform JSON data into OCSF or other target formats.
