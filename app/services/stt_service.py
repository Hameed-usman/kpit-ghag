"""Alias to app.services.stt for backward compatibility."""
from app.services.stt import (
    STTError,
    STTApiError,
    STTConnectionError,
    STTText,
    transcribe,
)

# For backward compatibility with earlier stubs
TranscriptResult = STTText
