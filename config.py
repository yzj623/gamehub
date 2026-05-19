import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_DIR = os.environ.get(
        "UPLOAD_DIR", os.path.join(BASE_DIR, "static", "uploads")
    )
    
    # Flask file upload configuration
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size

    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "123456")
    DB_NAME = os.environ.get("DB_NAME", "steam_platform")



    POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "5"))
