"""Alias to app.services.tts for backward compatibility."""
from app.services.tts import (
    get_voice_for_lang,
    synthesize,
    to_base64_data_uri,
    verify_voices,
)

# For backward compatibility
synthesise = synthesize
to_base64 = to_base64_data_uri
check_voices = verify_voices
