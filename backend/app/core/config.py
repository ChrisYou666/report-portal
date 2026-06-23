from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "数据中台门户 API"
    database_url: str = "postgresql+psycopg://portal:portal@127.0.0.1:5432/report_portal"
    storage_dir: str = "storage"
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173,https://julongtongchuan.icu"

    teams_webhook_url: str = ""
    teams_portal_url: str = "https://julongtongchuan.icu/report-portal/indicator"
    teams_bot_app_id: str = ""
    teams_bot_app_password: str = ""
    teams_bot_tenant_id: str = "botframework.com"
    teams_bot_validate_incoming: bool = True
    teams_bot_name: str = "Report Portal Bot"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_to: str = ""

    onedrive_enabled: bool = False
    onedrive_tenant_id: str = ""
    onedrive_client_id: str = ""
    onedrive_client_secret: str = ""
    onedrive_site_id: str = ""
    onedrive_drive_id: str = ""
    onedrive_root_folder: str = "报表原始文件"
    onedrive_path_template: str = "{year}/{month}/{day}/{site}/{batch_no}"
    onedrive_report_root_folder: str = "报表生成结果"
    onedrive_report_path_template: str = "{year}/{month}/{day}/{report_name}/{batch_no}"
    keep_local_copy: bool = True

    paddle_ocr_cache_dir: str = "storage/.ocr_cache"
    paddle_ocr_det_model_dir: str = ""
    paddle_ocr_rec_model_dir: str = ""
    paddle_ocr_textline_model_dir: str = ""

    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 480  # 8 hours

    sqlserver_host: str = ""
    sqlserver_port: str = "1433"
    sqlserver_database: str = ""
    sqlserver_user: str = ""
    sqlserver_password: str = ""
    sqlserver_odbc_driver: str = "ODBC Driver 17 for SQL Server"
    sqlserver_encrypt: str = "yes"
    sqlserver_trust_server_certificate: str = "yes"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


settings = Settings()
