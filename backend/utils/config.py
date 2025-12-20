import os
import yaml
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv()

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
    
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = cfg['db_host']
    DB_PORT = cfg['db_port']
    DB_NAME = cfg['db_name']

    # Construct the SQLAlchemy connection string
    SQLALCHEMY_DATABASE_URI = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-string'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    LLAMA_PORT = int(os.environ.get('LLAMA_PORT') or 8000)
    LLAMA_HOST = os.environ.get('LLAMA_HOST') or 'localhost'
