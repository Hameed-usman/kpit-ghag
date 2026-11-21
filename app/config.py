"""
Ghag – Application configuration.

All secrets and tunable parameters are read from environment variables.
Never hardcode API keys or paths here (see constitution P-6).

Usage:
    from app.config import settings
    settings.groq_api_key
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Pydantic-settings model — reads from .env and environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Groq
    groq_api_key: str = ""
    groq_stt_model: str = "whisper-large-v3"
    groq_llm_model: str = "openai/gpt-oss-120b"

    # App behaviour
    demo_mode: bool = False          # True → serve eval/demo_fixture.json offline
    confidence_threshold: float = 0.75
    max_audio_bytes: int = 10 * 1024 * 1024  # 10 MB

    # DB
    db_path: str = "ghag.db"

    # Dashboard
    admin_token: str = ""

    # TTS voices — verified against edge-tts voice list
    tts_voice_ur: str = "ur-PK-AsadNeural"
    tts_voice_en: str = "en-US-AriaNeural"
    tts_voice_ps: str = "ps-AF-GulNawazNeural"


settings = Config()
