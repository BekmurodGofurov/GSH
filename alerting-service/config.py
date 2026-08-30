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


# Yüklash — xato bo'lsa aniq ko'rsatib to'xtatadi
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
    print("❌  ALERTING SERVICE ISHGA TUSHMADI", flush=True)
    print("=" * 60, flush=True)

    if missing:
        print(f"\n🔴 Quyidagi MAJBURIY o'zgaruvchilar .env faylda topilmadi:\n", flush=True)
        for var in missing:
            print(f"     ➜  {var}", flush=True)
    else:
        print("\n🔴 Konfiguratsiya xatosi:", flush=True)
        print(exc, flush=True)

    print(f"""
📄 Nima qilish kerak:
  1. Loyiha ildizida .env fayl yarating (yoki mavjudini to'ldiring).
  2. Quyidagi MAJBURIY qatorlarni qo'shing:

       TELEGRAM_BOT_TOKEN=<@BotFather dan olingan token>
       TELEGRAM_CHAT_ID=<guruh chat ID, masalan: -1001234567890>
       DB_URL=postgresql://postgres:postgrespassword@timescaledb:5432/game_monitor

  3. Namuna uchun: .env.example faylini ko'ring.

{'=' * 60}
""", flush=True)
    sys.exit(1)
