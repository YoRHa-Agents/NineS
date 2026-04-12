"""``nines collect`` — search and collect information from configured sources."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from nines.collector.arxiv import ArxivCollector, ArxivConfig
from nines.collector.github import GitHubCollector, GitHubConfig
from nines.collector.store import DataStore

logger = logging.getLogger(__name__)

_VALID_SOURCES = ("github", "arxiv")


@click.command("collect")
@click.option(
    "--source",
    required=True,
    type=click.Choice(_VALID_SOURCES, case_sensitive=False),
    help="Data source to collect from.",
)
@click.option(
    "--query",
    required=True,
    type=str,
    help="Search query string.",
)
@click.option(
    "--max-results",
    type=int,
    default=30,
    show_default=True,
    help="Maximum number of results to return.",
)
@click.option(
    "--store-path",
    type=click.Path(),
    default=None,
    help="Path to a SQLite database for persisting results.",
)
@click.pass_context
def collect_cmd(
    ctx: click.Context,
    source: str,
    query: str,
    max_results: int,
    store_path: str | None,
) -> None:
    """Search and collect information from configured sources."""
    verbose = ctx.obj.get("verbose", False)

    if source == "github":
        collector = GitHubCollector(GitHubConfig(per_page=min(max_results, 100)))
        if verbose:
            click.echo(f"Searching GitHub for: {query}")
        results = collector.search_repos(query, per_page=max_results)
        click.echo(f"Collected {len(results)} repositories.")

        if store_path:
            store = DataStore(db_path=store_path)
            store.save_repos(results)
            store.close()
            click.echo(f"Saved to {store_path}")

        for repo in results:
            click.echo(f"  - {repo.owner}/{repo.name} ({repo.stars} stars)")

    elif source == "arxiv":
        collector_arxiv = ArxivCollector(ArxivConfig(max_results=max_results))
        if verbose:
            click.echo(f"Searching arXiv for: {query}")
        results_papers = collector_arxiv.search_papers(query, max_results=max_results)
        click.echo(f"Collected {len(results_papers)} papers.")

        if store_path:
            store = DataStore(db_path=store_path)
            store.save_papers(results_papers)
            store.close()
            click.echo(f"Saved to {store_path}")

        for paper in results_papers:
            click.echo(f"  - [{paper.id}] {paper.title}")

    else:
        click.echo(f"Unknown source: {source}", err=True)
        sys.exit(1)
