import os
import json
from typing import List
from dotenv import load_dotenv
from models import AccountConfig

class AppConfig:
    def __init__(self):
        load_dotenv()
        self.sqlite_db_path = os.getenv('SQLITE_DB_PATH', './activities.sqlite3')
        self.http_timeout_seconds = int(os.getenv('HTTP_TIMEOUT_SECONDS', '60'))
        self.max_concurrent_accounts = int(os.getenv('MAX_CONCURRENT_ACCOUNTS', '5'))
        self.page_size = int(os.getenv('PAGE_SIZE', '1000'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '6'))
        self.base_backoff_seconds = int(os.getenv('BASE_BACKOFF_SECONDS', '1'))
        self.max_backoff_seconds = int(os.getenv('MAX_BACKOFF_SECONDS', '30'))
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        
        accounts_json_str = os.getenv('NINJAONE_ACCOUNTS_JSON')
        if not accounts_json_str:
            raise ValueError("NINJAONE_ACCOUNTS_JSON environment variable is required")
            
        try:
            accounts_data = json.loads(accounts_json_str)
            self.accounts: List[AccountConfig] = [
                AccountConfig(**acc) for acc in accounts_data
            ]
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Failed to parse NINJAONE_ACCOUNTS_JSON: {e}")
