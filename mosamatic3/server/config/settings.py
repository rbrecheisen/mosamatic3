import os
import logging
import logging.config
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / '.env')

def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {'1', 'true', 'yes', 'on'}

SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
DEBUG = env_bool('DEBUG', True)
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

USE_X_FORWARDED_HOST = env_bool('USE_X_FORWARDED_HOST', False)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if env_bool('SECURE_PROXY_SSL_HEADER', False) else None

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'data' / 'app.db'}")

if DATABASE_URL.startswith('sqlite:///'):
    db_name = DATABASE_URL.replace('sqlite:///', '', 1)
    if not db_name.startswith('/'):
        db_name = str(BASE_DIR / db_name)
    Path(db_name).parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': db_name,
        }
    }
else:
    raise RuntimeError('Only sqlite DATABASE_URL is configured in this generated migration.')

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = Path(os.getenv('STATIC_ROOT', BASE_DIR / 'data' / 'staticfiles'))
if not STATIC_ROOT.is_absolute():
    STATIC_ROOT = BASE_DIR / STATIC_ROOT
STATIC_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

UPLOAD_ROOT = Path(os.getenv('UPLOAD_ROOT', BASE_DIR / 'data' / 'uploads'))
if not UPLOAD_ROOT.is_absolute():
    UPLOAD_ROOT = BASE_DIR / UPLOAD_ROOT
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

BUILTIN_MODEL_FILES_DATASET_NAME = os.getenv(
    'BUILTIN_MODEL_FILES_DATASET_NAME',
    'AI model files'
)
BUILTIN_MODEL_FILES_DIR = Path(
    os.getenv(
        'BUILTIN_MODEL_FILES_DIR',
        BASE_DIR / 'core' / 'systemdatasets' / 'modelfiles',
    )
)

if not BUILTIN_MODEL_FILES_DIR.is_absolute():
    BUILTIN_MODEL_FILES_DIR = BASE_DIR / BUILTIN_MODEL_FILES_DIR

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
ADMIN_PASSWORD_FILE_VALUE = os.getenv('ADMIN_PASSWORD_FILE', '').strip()
ADMIN_PASSWORD_FILE = Path(ADMIN_PASSWORD_FILE_VALUE) if ADMIN_PASSWORD_FILE_VALUE else None
if ADMIN_PASSWORD_FILE is not None and not ADMIN_PASSWORD_FILE.is_absolute():
    ADMIN_PASSWORD_FILE = BASE_DIR / ADMIN_PASSWORD_FILE

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '1440'))
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication', 'core.accounts.auth.BearerJWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
}

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# DATA_UPLOAD_MAX_NUMBER_FILES = 5000
# FILE_UPLOAD_MAX_MEMORY_SIZE = 2_500_000  # 2.5 MB
# DATA_UPLOAD_MAX_MEMORY_SIZE = 25_000_000  # 25 MB

DATA_UPLOAD_MAX_NUMBER_FILES = int(os.getenv('DATA_UPLOAD_MAX_NUMBER_FILES', '10000'))
DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.getenv('DATA_UPLOAD_MAX_NUMBER_FIELDS', '20000'))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('FILE_UPLOAD_MAX_MEMORY_SIZE', '2500000'))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv('DATA_UPLOAD_MAX_MEMORY_SIZE', '25000000'))

# ---------------------------------------------------------------------
# DICOM Storage SCP / PACS import
# ---------------------------------------------------------------------

DICOM_INBOX_ROOT = Path(os.getenv("DICOM_INBOX_ROOT", BASE_DIR / "data" / "dicom_inbox"))
if not DICOM_INBOX_ROOT.is_absolute():
    DICOM_INBOX_ROOT = BASE_DIR / DICOM_INBOX_ROOT
DICOM_INBOX_ROOT.mkdir(parents=True, exist_ok=True)

DICOM_SCP_AE_TITLE = os.getenv("DICOM_SCP_AE_TITLE", "MOSAMATIC3")
DICOM_SCP_HOST = os.getenv("DICOM_SCP_HOST", "0.0.0.0")
DICOM_SCP_PORT = int(os.getenv("DICOM_SCP_PORT", "11112"))

DICOM_IMPORT_STABLE_SECONDS = int(os.getenv("DICOM_IMPORT_STABLE_SECONDS", "60"))

# The user who owns automatically created DICOM import sessions/datasets.
DICOM_IMPORT_OWNER_USERNAME = os.getenv("DICOM_IMPORT_OWNER_USERNAME", ADMIN_USERNAME)

# Manual-review mode by default. Later you can turn this on.
DICOM_IMPORT_AUTO_RUN = env_bool("DICOM_IMPORT_AUTO_RUN", False)

DICOM_IMPORT_PIPELINE_KEY = os.getenv(
    "DICOM_IMPORT_PIPELINE_KEY",
    "default_l3_from_pacs",
)

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

LOG_DIR = Path(os.getenv("LOG_DIR", "/data/logs"))
if not LOG_DIR.is_absolute():
    LOG_DIR = BASE_DIR / LOG_DIR
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10 MB
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": (
                "%(asctime)s %(levelname)s "
                "[%(process)d:%(threadName)s] "
                "%(name)s: %(message)s"
            )
        },
        "simple": {
            "format": "%(asctime)s %(levelname)s %(name)s: %(message)s"
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "mosamatic3.log"),
            "maxBytes": LOG_MAX_BYTES,
            "backupCount": LOG_BACKUP_COUNT,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "mosamatic3-errors.log"),
            "maxBytes": LOG_MAX_BYTES,
            "backupCount": LOG_BACKUP_COUNT,
            "formatter": "verbose",
            "encoding": "utf-8",
            "level": "ERROR",
        },
    },

    "root": {
        "handlers": ["console", "app_file", "error_file"],
        "level": LOG_LEVEL,
    },

    "loggers": {
        "django": {
            "handlers": ["console", "app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "core": {
            "handlers": ["console", "app_file", "error_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}