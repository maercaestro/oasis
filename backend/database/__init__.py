"""
OASIS Database Module
SQLite database implementation for the OASIS system.
Replaces vulnerable JSON file operations with ACID-compliant database transactions.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from .db_manager import DatabaseManager
from .extended_ops import DatabaseManagerExtended
# from .migration import DatabaseMigration  # Migration doesn't export a class

__all__ = [
    'DatabaseManager',
    'DatabaseManagerExtended'
]
