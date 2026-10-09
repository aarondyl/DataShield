from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class IdentitySettings:
    database_url: str
    database_url_file: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password_file: str
    email_from: str
    smtp_starttls: bool
    access_minutes: int
    refresh_days: int
    email_code_minutes: int
    login_window_minutes: int
    login_max_attempts: int
    email_verify_required: bool
    llm_api_key_file: str
    llm_model: str

    @classmethod
    def load(cls) -> "IdentitySettings":
        database_url_file = os.getenv("IDENTITY_DATABASE_URL_FILE", "")
        database_url = Path(database_url_file).read_text(encoding="utf-8").strip() if database_url_file else os.getenv("IDENTITY_DATABASE_URL", "")
        return cls(
            database_url=database_url,
            database_url_file=database_url_file,
            smtp_host=os.getenv("IDENTITY_SMTP_HOST", ""),
            smtp_port=int(os.getenv("IDENTITY_SMTP_PORT", "587")),
            smtp_user=os.getenv("IDENTITY_SMTP_USER", ""),
            smtp_password_file=os.getenv("IDENTITY_SMTP_PASSWORD_FILE", ""),
            email_from=os.getenv("IDENTITY_EMAIL_FROM", ""),
            smtp_starttls=os.getenv("IDENTITY_SMTP_STARTTLS", "true").lower() == "true",
            access_minutes=max(5, min(60, int(os.getenv("IDENTITY_ACCESS_MINUTES", "15")))),
            refresh_days=max(1, min(90, int(os.getenv("IDENTITY_REFRESH_DAYS", "30")))),
            email_code_minutes=max(5, min(30, int(os.getenv("IDENTITY_EMAIL_CODE_MINUTES", "10")))),
            login_window_minutes=max(1, min(60, int(os.getenv("IDENTITY_LOGIN_WINDOW_MINUTES", "15")))),
            login_max_attempts=max(3, min(20, int(os.getenv("IDENTITY_LOGIN_MAX_ATTEMPTS", "8")))),
            email_verify_required=os.getenv("IDENTITY_EMAIL_VERIFY_REQUIRED", "true").lower() == "true",
            llm_api_key_file=os.getenv("IDENTITY_LLM_API_KEY_FILE", ""),
            llm_model=os.getenv("IDENTITY_LLM_MODEL", "deepseek-flash"),
        )

    @property
    def email_ready(self) -> bool:
        password_file_ok = bool(self.smtp_password_file and Path(self.smtp_password_file).is_file())
        return bool(self.smtp_host and self.email_from and self.smtp_user and password_file_ok)

    @property
    def llm_api_key(self) -> str:
        return Path(self.llm_api_key_file).read_text(encoding="utf-8").strip() if self.llm_api_key_file and Path(self.llm_api_key_file).is_file() else ""
