import sys
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Muhit o'zgaruvchisi topilmasa pydantic o'zi xato beradi,
        # lekin biz quyida yanada aniq xabar chiqaramiz.
    )

    telegram_bot_token: str
    telegram_chat_id: str
    db_url: str

    # Daily rejimi
    report_hour_utc: int = 9
    report_minute_utc: int = 0
    lookback_days: int = 1

    # Startup
    send_on_startup: bool = False


# Loading — if there's an error, point it out clearly and stop
REQUIRED_VARS = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "DB_URL"]

try:
    settings = Settings()
except ValidationError as exc:
    missing = []
    for err in exc.errors():
        field = err.get("loc", ("",))[0]
        if err.get("type") == "missing":
            missing.append(field.upper())

    print("\n" + "=" * 60, flush=True)
    print("❌  ALERTING SERVICE FAILED TO START", flush=True)
    print("=" * 60, flush=True)

    if missing:
        print(f"\n🔴 The following REQUIRED variables were not found in the .env file:\n", flush=True)
        for var in missing:
            print(f"     ➜  {var}", flush=True)
    else:
        print("\n🔴 Configuration error:", flush=True)
        print(exc, flush=True)

    print(f"""
📄 What to do:
  1. Create a .env file at the project root (or fill out the existing one).
  2. Add the following REQUIRED lines:

       TELEGRAM_BOT_TOKEN=<token from @BotFather>
       TELEGRAM_CHAT_ID=<group chat ID, e.g.: -1001234567890>
       DB_URL=<database connection url>

  3. See .env.example for an example.

{'=' * 60}
""", flush=True)
    sys.exit(1)
