import logging
import httpx
from typing import AsyncGenerator, Dict, Any
from models import AccountConfig
from auth import AuthManager
from retry import with_retry

logger = logging.getLogger(__name__)

class NinjaClient:
    """
    Handles API requests to NinjaOne.
    Manages URLs, pagination state, and handles the raw API responses.
    """
    def __init__(self, http_client: httpx.AsyncClient, auth_manager: AuthManager, config):
        self.http_client = http_client
        self.auth_manager = auth_manager
        self.config = config

    async def fetch_activities(self, account: AccountConfig, start_older_than_id: int = 0, stop_at_id: int = 0) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yields activities for a specific account.
        Used for both historical backfills (`start_older_than_id`) and incremental updates (`stop_at_id`).
        """
        # The NinjaOne API uses reverse-chronological cursor pagination (olderThan)
        
        endpoint = f"{account.base_url.rstrip('/')}/v2/activities"
        limit = self.config.page_size
        current_older_than = start_older_than_id if start_older_than_id > 0 else None
        
        while True:
            token = await self.auth_manager.get_token(self.http_client, account)
            headers = {"Authorization": f"Bearer {token}"}
            params = {"pageSize": limit}
            if current_older_than is not None:
                params["olderThan"] = current_older_than
            
            async def _do_fetch():
                return await self.http_client.get(endpoint, headers=headers, params=params)

            logger.debug("Fetching activities from %s with params %s", endpoint, params)
            response = await with_retry(
                _do_fetch,
                max_retries=self.config.max_retries,
                base_backoff=self.config.base_backoff_seconds,
                max_backoff=self.config.max_backoff_seconds
            )
            
            data = response.json()
            
            # Extract the actual list of activities from the response wrapper
            activities = data.get('activities', [])
            
            if not isinstance(activities, list):
                logger.error("Unexpected response shape from activities API: %s. keys: %s", type(activities), data.keys())
                break
                
            if not activities:
                logger.info("No more activities found for account %s.", account.name)
                break
                
            logger.info("Fetched page of %d activities for account %s (first id: %s, last id: %s)", len(activities), account.name, activities[0].get('id'), activities[-1].get('id'))
            
            for activity in activities:
                # Stop yielding if we reach our high-water mark from a previous run
                if stop_at_id > 0 and activity.get('id', 0) <= stop_at_id:
                    logger.debug("Hit integration bound (activity_id %s <= %s). Halting yield.", activity.get('id'), stop_at_id)
                    return
                yield activity
                
            # Update the cursor to point to the oldest item in this page for the next request
            last_activity = activities[-1]
            next_older_than_id = last_activity.get('id')
            if not next_older_than_id:
                logger.warning("Activity is missing 'id', cannot paginate further in account %s", account.name)
                break
                
            if current_older_than == next_older_than_id:
                logger.debug("Cursor 'olderThan' did not change (%s), end of history reached.", current_older_than)
                break
                
            current_older_than = next_older_than_id
