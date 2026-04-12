"""Information collection pipeline (V2 vertex).

Re-exports the public surface so consumers can write::

    from nines.collector import Repository, GitHubCollector, DataStore
"""

from nines.collector.arxiv import ArxivCollector, ArxivConfig
from nines.collector.github import GitHubCollector, GitHubConfig
from nines.collector.models import (
    ChangeEvent,
    CollectionSnapshot,
    Paper,
    Repository,
)
from nines.collector.store import DataStore

__all__ = [
    "ArxivCollector",
    "ArxivConfig",
    "ChangeEvent",
    "CollectionSnapshot",
    "DataStore",
    "GitHubCollector",
    "GitHubConfig",
    "Paper",
    "Repository",
]
