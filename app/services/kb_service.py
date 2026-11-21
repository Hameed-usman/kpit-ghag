"""Alias to app.services.kb for backward compatibility."""
from app.services.kb import (
    KBSection,
    KnowledgeBase,
    get_kb,
    init_kb,
)

# For backward compatibility
KBPassage = KBSection
