import asyncio
import logging
import json
import time
import argparse
from typing import List

import httpx
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.logging import RichHandler

from config import AppConfig
from auth import AuthManager
from client import NinjaClient
from database import Database
from models import AccountConfig, ActivityRow
from utils import extract_timestamp, generate_dedupe_key

# Configure minimal global logger before config handles it mostly
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_logging(level_str: str, show_log: bool):
    numeric_level = getattr(logging, level_str.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
        
    handlers = [logging.StreamHandler()] if show_log else [RichHandler(rich_tracebacks=True, show_time=True)]
    
    # If not showing log, suppress standard info level messages from spamming the progress bar
    if not show_log and numeric_level <= logging.INFO:
        numeric_level = logging.WARNING
        
    logging.basicConfig(
        format="%(message)s" if not show_log else "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=numeric_level,
        handlers=handlers,
        force=True
    )

async def process_account(
    account: AccountConfig,
    ninja_client: NinjaClient,
    database: Database,
    semaphore: asyncio.Semaphore,
    progress: Progress = None,
    max_duration_seconds: int = 0
):
    """
    Export process for a single account.
    Fetches activities and writes them to the database in batches.
    """
    task_id = None
    if progress:
        task_id = progress.add_task(f"[cyan]Starting sync for {account.name}...", total=None)
        
    async with semaphore:
        logger.info("Starting export for account: %s", account.name)
        
        batch: List[ActivityRow] = []
        batch_size = ninja_client.config.page_size
        total_inserted = 0
        total_fetched = 0
        start_time = time.time()
        
        try:
            max_id = database.get_last_activity_id(account.client_id)
            min_id = database.get_lowest_activity_id(account.client_id)
            
            async def combined_activity_generator():
                if max_id > 0:
                    logger.info("Syncing new records for account %s (newer than %d).", account.name, max_id)
                    # Pull backwards from present, stop when we hit max_id
                    async for act in ninja_client.fetch_activities(account, start_older_than_id=0, stop_at_id=max_id):
                        yield act
                        
                if min_id > 0 or max_id == 0:
                    if min_id > 0:
                        logger.info("Resuming historical sync for account %s (older than %d).", account.name, min_id)
                    else:
                        logger.info("Performing full initial historical sync for account %s.", account.name)
                        
                    # Pull backwards from min_id, don't stop until no more activities
                    async for act in ninja_client.fetch_activities(account, start_older_than_id=min_id, stop_at_id=0):
                        yield act

            async for activity in combined_activity_generator():
                if max_duration_seconds > 0 and (time.time() - start_time) > max_duration_seconds:
                    logger.warning("Max execution duration (%d seconds) reached for account %s. Stopping fetch.", max_duration_seconds, account.name)
                    if progress and task_id is not None:
                        progress.update(task_id, description=f"[yellow]Time limit reached for {account.name}[/yellow]")
                    break
                    
                total_fetched += 1
                
                downloaded_at = int(time.time())
                activity_timestamp = extract_timestamp(activity)
                activity_id = activity.get('id')
                dedupe_key = generate_dedupe_key(account.name, account.vertical, activity)
                activity_body = json.dumps(activity, separators=(',', ':'))
                
                row = ActivityRow(
                    account_name=account.name,
                    vertical=account.vertical,
                    client_id=account.client_id,
                    downloaded_at=downloaded_at,
                    activity_timestamp=activity_timestamp,
                    activity_id=activity_id,
                    dedupe_key=dedupe_key,
                    activity_body=activity_body
                )
                batch.append(row)
                
                if len(batch) >= batch_size:
                    # Offload the blocking SQLite write to a thread pool so it doesn't freeze the asyncio event loop
                    inserted = await asyncio.to_thread(database.insert_activities, batch)
                    total_inserted += inserted
                    if progress and task_id is not None:
                        # Advance by 1 for the indeterminate loading bar, but update description fully
                        progress.update(task_id, advance=1, description=f"[cyan]Syncing {account.name} - {total_fetched} activities fetched, {total_inserted} new inserts")
                        
                    logger.info("Inserted %d new records (%d fetched so far) for account %s", inserted, total_fetched, account.name)
                    # We must create a new list because passing the reference to the thread and clearing it could cause race conditions
                    batch = []
                    
            if batch:
                inserted = await asyncio.to_thread(database.insert_activities, batch)
                total_inserted += inserted
                
            if progress and task_id is not None:
                progress.update(task_id, description=f"[green]Completed {account.name} - {total_fetched} fetched, {total_inserted} new inserts[/green]", completed=100, total=100)
                
            logger.info("Completed export for account: %s. Total fetched: %d. Total new inserts: %d", account.name, total_fetched, total_inserted)
            
        except Exception as e:
            if progress and task_id is not None:
                progress.update(task_id, description=f"[red]Failed {account.name} - error: {str(e)}[/red]")
            logger.error("Unrecoverable failure for account %s: %s", account.name, e, exc_info=True)

async def main():
    parser = argparse.ArgumentParser(description="NinjaOne Activity Downloader")
    parser.add_argument("--show-log", action="store_true", help="Show detailed execution logs instead of progress bars")
    parser.add_argument("--max-duration", type=int, default=0, help="Maximum execution time in seconds per account. 0 means unlimited.")
    parser.add_argument("--page-size", type=int, default=1000, help="Number of records to fetch per API page (max 1000).")
    args = parser.parse_args()

    try:
        config = AppConfig()
        config.page_size = args.page_size
    except Exception as e:
        logger.error("Configuration failed: %s", e)
        return
        
    setup_logging(config.log_level, args.show_log)
    logger.info("Starting up. Discovered %d accounts to process.", len(config.accounts))
    
    database = Database(config.sqlite_db_path)
    
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
    timeout = httpx.Timeout(config.http_timeout_seconds)
    
    semaphore = asyncio.Semaphore(config.max_concurrent_accounts)
    
    # Use a single httpx AsyncClient for the entire application lifecycle
    async with httpx.AsyncClient(limits=limits, timeout=timeout) as http_client:
        auth_manager = AuthManager(config)
        ninja_client = NinjaClient(http_client, auth_manager, config)
        
        progress = None
        if not args.show_log:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=None),
                TimeElapsedColumn(),
                expand=True
            )
            
        tasks = [
            process_account(account, ninja_client, database, semaphore, progress, args.max_duration)
            for account in config.accounts
        ]
        
        if progress:
            with progress:
                await asyncio.gather(*tasks)
        else:
            await asyncio.gather(*tasks)
            
    logger.info("Shutdown complete.")

if __name__ == "__main__":
    asyncio.run(main())
