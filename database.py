import sqlite3
import logging
from typing import List
from models import ActivityRow

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self):
        """Creates the necessary SQLite tables and performance indexes."""
        logger.info("Initializing database schema at %s", self.db_path)
        with sqlite3.connect(self.db_path) as conn:
            # Enable WAL mode so readers aren't blocked by writers
            conn.execute('PRAGMA journal_mode=WAL;')
            # NORMAL sync is faster and perfectly safe in WAL mode
            conn.execute('PRAGMA synchronous=NORMAL;')
            
            cursor = conn.cursor()
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS raw_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_name TEXT NOT NULL,
                vertical TEXT NOT NULL,
                client_id TEXT NOT NULL,
                downloaded_at INTEGER NOT NULL,
                activity_timestamp INTEGER,
                activity_id INTEGER,
                dedupe_key TEXT NOT NULL,
                activity_body JSON NOT NULL
            );
            ''')
            
            cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_activities_dedupe_key
            ON raw_activities(dedupe_key);
            ''')
            
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_raw_activities_account_timestamp
            ON raw_activities(account_name, activity_timestamp);
            ''')
            
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_raw_activities_account_activity_id
            ON raw_activities(account_name, activity_id);
            ''')
            
            conn.commit()

    def get_last_activity_id(self, client_id: str) -> int:
        """
        Finds the newest activity_id we have fully saved for this client.
        Used as the stopping boundary during forward-syncs.
        """
        stmt = "SELECT MAX(activity_id) FROM raw_activities WHERE client_id = ?"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(stmt, (client_id,))
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0

    def get_lowest_activity_id(self, client_id: str) -> int:
        """
        Finds the oldest activity_id we have fully saved for this client.
        Used as the starting cursor when backfilling history.
        """
        stmt = "SELECT MIN(activity_id) FROM raw_activities WHERE client_id = ?"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(stmt, (client_id,))
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0

    def insert_activities(self, rows: List[ActivityRow]) -> int:
        """
        Persists a batch of activities to the database.
        Returns the number of genuinely new records saved.
        """
        if not rows:
            return 0
            
        data = [
            (
                row.account_name,
                row.vertical,
                row.client_id,
                row.downloaded_at,
                row.activity_timestamp,
                row.activity_id,
                row.dedupe_key,
                row.activity_body
            )
            for row in rows
        ]
        
        stmt = '''
        INSERT OR IGNORE INTO raw_activities (
            account_name,
            vertical,
            client_id,
            downloaded_at,
            activity_timestamp,
            activity_id,
            dedupe_key,
            activity_body
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        
        with sqlite3.connect(self.db_path) as conn:
            # Wrap inserts in a single transaction for maximum batch performance
            conn.execute("BEGIN TRANSACTION;")
            cursor = conn.cursor()
            cursor.executemany(stmt, data)
            inserted_count = cursor.rowcount
            conn.commit()
            
        return inserted_count
