"""
Ghag – Knowledge Base Service.

Loads kb/domicile.md at startup, parses into sections {id, title, source_url, content}.
Enforces Constitution P-1: ignores unverified sections marked with TODO(verified-source).
Provides render_for_prompt() for system prompt injection and reload() for dynamic updates.

FR-3, FR-4
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^---\s*$", re.MULTILINE)
_META_RE = re.compile(r"^(\w[\w_-]*):\s*(.+)$", re.MULTILINE)


@dataclass
class KBSection:
    """Represents a single verified section from the knowledge base."""
    id: str
    title: str
    source_url: str
    content: str
    last_verified: str = ""


@dataclass
class KnowledgeBase:
    """In-memory verified knowledge base loaded from kb markdown files."""
    sections: Dict[str, KBSection] = field(default_factory=dict)
    kb_path: Path = field(default_factory=lambda: Path("kb/domicile.md"))

    @classmethod
    def load(cls, path_or_dir: str | Path = "kb/domicile.md") -> KnowledgeBase:
        """Parse the given KB file or directory of markdown files."""
        target = Path(path_or_dir)
        kb = cls(kb_path=target)
        kb.reload(target)
        return kb

    def reload(self, path_or_dir: Optional[str | Path] = None) -> None:
        """Parse or reload markdown files from disk."""
        target = Path(path_or_dir) if path_or_dir else self.kb_path
        self.kb_path = target
        new_sections: Dict[str, KBSection] = {}

        files_to_read: List[Path] = []
        if target.is_dir():
            files_to_read = sorted(target.glob("*.md"))
        elif target.is_file():
            files_to_read = [target]
        else:
            log.warning("KB target does not exist: %s", target)
            return

        for f in files_to_read:
            count = self._parse_file(f, new_sections)
            log.info("KB: Loaded %d verified section(s) from %s", count, f.name)

        self.sections = new_sections
        log.info("KB: Total verified sections active: %d", len(self.sections))

    def _parse_file(self, file_path: Path, store: Dict[str, KBSection]) -> int:
        """Parse a markdown file into sections delimited by --- blocks."""
        raw_text = file_path.read_text(encoding="utf-8")
        # Strip comments
        cleaned_text = re.sub(r"<!--.*?-->", "", raw_text, flags=re.DOTALL)
        parts = _FENCE_RE.split(cleaned_text)

        loaded = 0
        i = 1
        while i < len(parts) - 1:
            meta_block = parts[i].strip()
            content_block = parts[i + 1].strip() if i + 1 < len(parts) else ""
            i += 2

            if not meta_block:
                continue

            metadata = dict(_META_RE.findall(meta_block))
            sec_id = metadata.get("id", "").strip()
            if not sec_id:
                continue

            # Skip unverified sections containing TODO(verified-source)
            if "TODO(verified-source)" in content_block:
                log.debug("KB: Skipping unverified section '%s'", sec_id)
                continue

            sec = KBSection(
                id=sec_id,
                title=metadata.get("title", sec_id).strip(),
                source_url=metadata.get("source_url", "").strip(),
                content=content_block,
                last_verified=metadata.get("last_verified", "").strip(),
            )
            store[sec_id] = sec
            loaded += 1

        return loaded

    def render_for_prompt(self) -> str:
        """Render all verified sections as plain text for LLM system prompt."""
        if not self.sections:
            return "(No verified government knowledge base entries found.)"

        blocks: List[str] = []
        for sec in self.sections.values():
            blocks.append(
                f"[Source ID: {sec.id}]\n"
                f"Title: {sec.title}\n"
                f"Official URL: {sec.source_url}\n"
                f"Content:\n{sec.content}"
            )
        return "\n\n---\n\n".join(blocks)

    def source_id_valid(self, source_id: Optional[str]) -> bool:
        """Check if source_id exists in the loaded KB."""
        if not source_id:
            return False
        return source_id.strip() in self.sections

    def get_source_url(self, source_id: Optional[str]) -> Optional[str]:
        """Retrieve canonical source_url for a verified section."""
        if not source_id:
            return None
        sec = self.sections.get(source_id.strip())
        return sec.source_url if sec else None

    def __len__(self) -> int:
        return len(self.sections)


_ACTIVE_KB: Optional[KnowledgeBase] = None


def get_kb() -> KnowledgeBase:
    """Retrieve global singleton KB. Initializes default if none exists."""
    global _ACTIVE_KB
    if _ACTIVE_KB is None:
        _ACTIVE_KB = KnowledgeBase.load()
    return _ACTIVE_KB


def init_kb(path_or_dir: str | Path = "kb/domicile.md") -> KnowledgeBase:
    """Initialize or reset the global KB singleton."""
    global _ACTIVE_KB
    _ACTIVE_KB = KnowledgeBase.load(path_or_dir)
    return _ACTIVE_KB
