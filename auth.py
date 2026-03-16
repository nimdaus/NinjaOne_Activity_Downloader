import time
import logging
import httpx
from typing import Dict
from models import AccountConfig, TokenInfo
from retry import with_retry

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self, config):
        self.config = config
        self._tokens: Dict[str, TokenInfo] = {}

    async def get_token(self, client: httpx.AsyncClient, account: AccountConfig) -> str:
        """
        Retrieves a valid OAuth2 token. 
        Returns a cached token if available, or fetches a new one if expired.
        """
        token_info = self._tokens.get(account.name)
        now = time.time()
        
        # Keep a 60-second buffer to prevent using a token that's about to expire
        if token_info and token_info.expires_at > now + 60:
            return token_info.access_token
            
        logger.info("Acquiring new token for account %s...", account.name)
        
        if account.auth_type != "client_credentials":
            raise ValueError(f"Unsupported auth_type '{account.auth_type}' for account {account.name}")

        token_url = f"{account.base_url.rstrip('/')}/ws/oauth/token"
        
        data = {
            "grant_type": "client_credentials",
            "scope": "monitoring"
        }
        
        # Client credentials grant requires Basic Auth using the ID and Secret
        auth = (account.client_id, account.client_secret)
        
        async def _fetch_token():
            return await client.post(
                token_url,
                data=data,
                auth=auth,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
        try:
            response = await with_retry(
                _fetch_token,
                max_retries=self.config.max_retries,
                base_backoff=self.config.base_backoff_seconds,
                max_backoff=self.config.max_backoff_seconds
            )
        except Exception as e:
            logger.error("Authentication failed for account %s: %s", account.name, e)
            raise
            
        resp_data = response.json()
        access_token = resp_data.get("access_token")
        expires_in = resp_data.get("expires_in", 3600)  # Default 1 hour if not provided
        
        if not access_token:
            logger.error("No access_token returned for account %s", account.name)
            raise ValueError("Authentication response did not contain an access_token")
            
        self._tokens[account.name] = TokenInfo(
            access_token=access_token,
            expires_at=now + int(expires_in)
        )
        logger.debug("Successfully acquired token for account %s (expires in %s sec)", account.name, expires_in)
        
        return access_token
