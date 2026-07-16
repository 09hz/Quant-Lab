"""Optional database backend for AlgoTrader research data.

Research/simulation only. No broker integration or order execution.
"""
from .config import DatabaseConfig, load_database_config, masked_database_config
from .backend import DatabaseConnection, connect_database
from .migrations import migrate_database

__all__ = [
    "DatabaseConfig",
    "DatabaseConnection",
    "connect_database",
    "load_database_config",
    "masked_database_config",
    "migrate_database",
]
