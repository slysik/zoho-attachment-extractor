from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_refresh_token: str = ""

    zoho_sheet_id: str = ""
    zoho_sheet_name: str = "Sheet1"

    workdrive_incoming_folder_id: str = ""
    workdrive_processed_folder_id: str = ""
    workdrive_failed_folder_id: str = ""

    webhook_secret: str = ""

    # Zoho OAuth token endpoint — .com for US datacenter
    zoho_accounts_url: str = "https://accounts.zoho.com"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
