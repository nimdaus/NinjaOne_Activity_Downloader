import logging
import httpx
from typing import AsyncGenerator, Dict, Any
from models import AccountConfig
from auth import AuthManager
from retry import with_retry

logger = logging.getLogger(__name__)

class NinjaClient:
    """
    Wraps NinjaOne API interactions.
    Isolates endpoint URL construction, pagination logic, and response parsing.
    """
    def __init__(self, http_client: httpx.AsyncClient, auth_manager: AuthManager, config):
        self.http_client = http_client
        self.auth_manager = auth_manager
        self.config = config

    async def fetch_activities(self, account: AccountConfig, start_older_than_id: int = 0, stop_at_id: int = 0) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Fetches all activities for the given account.
        Yields individual activity dictionaries.
        If start_older_than_id is provided, begins pulling activities older than that ID.
        If stop_at_id is provided, halts fetching entirely once an activity ID <= stop_at_id is encountered.
        """
        # Assumptions isolated here:
        # 1. Activities API endpoint is `/v2/activities`
        # 2. Uses `pageSize` and cursor-based `olderThan` & `newerThan` pagination.
        
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
            
            # The API returns {'activities': [...], 'lastActivityId': ...}
            activities = data.get('activities', [])
            
            if not isinstance(activities, list):
                logger.error("Unexpected response shape from activities API: %s. keys: %s", type(activities), data.keys())
                break
                
            if not activities:
                logger.info("No more activities found for account %s.", account.name)
                break
                
            logger.info("Fetched page of %d activities for account %s (first id: %s, last id: %s)", len(activities), account.name, activities[0].get('id'), activities[-1].get('id'))
            
            for activity in activities:
                # Application layer bound limit
                if stop_at_id > 0 and activity.get('id', 0) <= stop_at_id:
                    logger.debug("Hit integration bound (activity_id %s <= %s). Halting yield.", activity.get('id'), stop_at_id)
                    return
                yield activity
                
            # If we didn't use `pageSize` to limit the response, we might get fewer items.
            # But the safest break condition for backward pagination is when the API
            # returns an empty array, which we already handle above.
            # We explicitly remove the `if len(activities) < limit: break` check, as
            # queries using `newerThan` might return a partial final page that still has older data.
                
            # Update older_than_id cursor with the last (oldest) activity ID from this batch
            last_activity = activities[-1]
            next_older_than_id = last_activity.get('id')
            if not next_older_than_id:
                logger.warning("Activity is missing 'id', cannot paginate further in account %s", account.name)
                break
                
            if current_older_than == next_older_than_id:
                logger.debug("Cursor 'olderThan' did not change (%s), end of history reached.", current_older_than)
                break
                
            current_older_than = next_older_than_id
