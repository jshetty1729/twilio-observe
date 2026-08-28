from pathlib import Path

from pydantic_settings import BaseSettings

# Look for .env in server/ first, then project root
_server_dir = Path(__file__).resolve().parent.parent.parent.parent
_project_root = _server_dir.parent
_env_file = _server_dir / ".env"
if not _env_file.exists():
    _env_file = _project_root / ".env"


class Settings(BaseSettings):
    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_api_key: str = ""
    twilio_api_secret: str = ""
    twilio_sync_service_sid: str = ""
    twilio_trunking_number: str = ""
    twilio_twiml_app_sid: str = ""
    twilio_ci_service_sid: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Server
    port: int = 8000
    ngrok_url: str = "http://localhost:8000"

    class Config:
        env_file = str(_env_file)
        env_file_encoding = "utf-8"


settings = Settings()
