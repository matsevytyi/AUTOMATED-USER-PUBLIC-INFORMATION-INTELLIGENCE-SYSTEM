import os
import yaml
from datetime import timedelta

# Load YAML config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'cfg.yaml')
with open(CONFIG_PATH, 'r') as f:
    cfg = yaml.safe_load(f)

class Config:
    # --- Loaded from cfg.yaml ---
    SEMANTIC_MODEL = cfg['semantic_model']
    NER_MODEL = cfg['NER_model']
    AVAILABLE_ASSISTANT_MODELS = cfg['available_assistant_models']
    
    BM_25_PRIMARY_THRESHOLD = cfg['BM_25_primary_threshold']
    BM_25_SECONDARY_THRESHOLD = cfg['BM_25_secondary_threshold']
    USE_PRUNING_FILTER_BACKUP = cfg['use_pruning_filter_backup']

    APPLIED_REPORT_QUERY_MATCHING_MODE = cfg['applied_report_query_matching_mode']
    FUZZY_THRESHOLD = cfg['fuzzy_threshold']
    SEMANTIC_THRESHOLD = cfg['semantic_threshold']

    NAME_COEFFICIENT = cfg['name_coefficient']
    CONTEXT_COEFFICIENT = cfg['context_coefficient']
    CATEGORY_WEIGHTS = cfg['category_weights']
    
    # --- loaded from .env ---
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///profolio.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-string'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    LLAMA_PORT = int(os.environ.get('LLAMA_PORT') or 8000)
    LLAMA_HOST = os.environ.get('LLAMA_HOST') or 'localhost'
