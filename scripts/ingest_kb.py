"""
scripts/ingest_kb.py – Parse kb/*.md and populate SQLite FTS5 table.

Usage:
    python scripts/ingest_kb.py [--kb-dir kb] [--db-path ghag.db]

Skips any entry whose content contains 'TODO(verified-source)'.
Prints a summary of ingested vs. skipped entries.

TODO(chunk-2): implement parsing and DB insertion logic.
"""
import argparse


def parse_kb_file(filepath: str) -> list[dict]:
    """
    Parse a kb/*.md file and extract section blocks.

    Each block starts with a YAML-like header enclosed in '---' lines
    containing: id, title, source_url, last_verified.
    Content follows the closing '---' until the next block or EOF.

    Returns list of dicts with keys: id, title, source_url, last_verified, content.
    TODO(chunk-2): implement
    """
    raise NotImplementedError


def ingest(kb_dir: str = "kb", db_path: str = "ghag.db") -> None:
    """
    Main ingestion entry point.

    TODO(chunk-2): implement
    """
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest KB markdown files into SQLite.")
    parser.add_argument("--kb-dir", default="kb")
    parser.add_argument("--db-path", default="ghag.db")
    args = parser.parse_args()
    ingest(args.kb_dir, args.db_path)
