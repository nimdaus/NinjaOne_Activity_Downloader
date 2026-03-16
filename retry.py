import asyncio
import logging
import random
from typing import Callable, Awaitable
import httpx

logger = logging.getLogger(__name__)

# Exception types that indicate we should retry
RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.NetworkError,
)

async def with_retry(
    func: Callable[[], Awaitable[httpx.Response]],
    max_retries: int,
    base_backoff: int,
    max_backoff: int
) -> httpx.Response:
    """
    Wraps an async HTTP request in a retry loop using an exponential backoff strategy with jitter.
    Automatically handles transient network errors and rate limits (HTTP 429 & 500s).
    """
    attempt = 0
    while True:
        try:
            response = await func()
            
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = int(retry_after)
                else:
                    delay = min(base_backoff * (2 ** attempt), max_backoff)
            elif response.status_code in (500, 502, 503, 504):
                delay = min(base_backoff * (2 ** attempt), max_backoff)
            else:
                response.raise_for_status()
                return response
                
        except RETRYABLE_EXCEPTIONS as e:
            delay = min(base_backoff * (2 ** attempt), max_backoff)
            logger.warning("Transient error %s occurred, will retry.", type(e).__name__)
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in (429, 500, 502, 503, 504):
                raise
            # Valid retryable HTTP error, the delay is already set
        except Exception:
            raise
            
        attempt += 1
        if attempt > max_retries:
            logger.error("Max retries (%d) exceeded.", max_retries)
            if 'response' in locals() and isinstance(response, httpx.Response):
                response.raise_for_status()
            raise Exception("Max retries exceeded and no response available to raise.")

        # Add randomized jitter to prevent "thundering herd" issues
        jitter = random.uniform(0, 0.5 * delay)
        sleep_time = min(delay + jitter, max_backoff)
        
        logger.warning(
            "Request failed or rate limited. Retrying in %.2f seconds (attempt %d/%d).",
            sleep_time, attempt, max_retries
        )
        await asyncio.sleep(sleep_time)
