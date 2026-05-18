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

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
