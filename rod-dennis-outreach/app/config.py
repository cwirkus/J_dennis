from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    hunter_api_key: str = ""
    artsy_client_id: str = ""
    artsy_client_secret: str = ""
    perplexity_api_key: str = ""
    data_path: str = "data/prospects.csv"
    drafts_path: str = "data/outreach_drafts.csv"
    inbox_path: str = "data/inbound_messages.csv"
    rod_email: str = "info@jrodneydennis.com"
    gmail_credentials_json: str = ""
    environment: str = "development"
    discovery_log_path: str = "data/discovery_log.csv"
    social_drafts_path: str = "data/social_drafts.csv"
    dashboard_url: str = "http://localhost:3000"
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
