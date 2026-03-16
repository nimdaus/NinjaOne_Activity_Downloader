import hashlib
import json
from typing import Any, Dict, Optional

def generate_dedupe_key(account_name: str, vertical: str, activity_body: Dict[str, Any]) -> str:
    """
    Creates a unique hash for an activity to prevent duplicate database entries.
    Prioritizes an explicit 'id' field. If missing, it hashes the JSON payload.
    """
    activity_id = activity_body.get('id')
    if activity_id is not None:
        raw_key = f"{account_name}:{vertical}:{activity_id}"
    else:
        # Canonical JSON string: sorted keys, no whitespace
        canonical_json = json.dumps(activity_body, sort_keys=True, separators=(',', ':'))
        raw_key = f"{account_name}:{vertical}:{canonical_json}"
    
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

def extract_timestamp(activity_body: Dict[str, Any]) -> Optional[int]:
    """
    Finds and standardizes the timestamp from an activity payload into Unix epoch seconds.
    Returns None if a timestamp is missing or cannot be safely parsed.
    """
    ts = activity_body.get('activityTime') or activity_body.get('timestamp')
    if isinstance(ts, (int, float)):
        # If it looks like milliseconds, convert to seconds
        if ts > 1e11:
            return int(ts / 1000)
        return int(ts)
    if isinstance(ts, str):
        # Additional standard string parsers could be added here later if needed
        pass
        
    return None
