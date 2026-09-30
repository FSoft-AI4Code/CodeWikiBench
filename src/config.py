import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Load .env from the current working directory upwards (works for installed packages too)
load_dotenv(find_dotenv(usecwd=True))

# Package directory (the repo's src/ dir in a source checkout / editable install)
PACKAGE_DIR = Path(__file__).parent.absolute()
SRC_DIR = PACKAGE_DIR


def _is_source_checkout() -> bool:
    """True when running from the repo tree (src/ mapped as the codewikibench package)."""
    root = PACKAGE_DIR.parent
    return PACKAGE_DIR.name == "src" and (root / "pyproject.toml").is_file()


def _resolve_data_dir() -> Path:
    env = os.getenv("CWB_DATA_DIR")
    if env:
        return Path(env).expanduser().absolute()
    if _is_source_checkout():
        return PACKAGE_DIR.parent / "data"
    return Path.cwd().absolute() / "data"


# Project root: the repo root in a source checkout, else the current working directory
PROJECT_ROOT = PACKAGE_DIR.parent if _is_source_checkout() else Path.cwd().absolute()

# In a source checkout, also pick up the repo's .env (does not override values already set)
if _is_source_checkout() and (PACKAGE_DIR.parent / ".env").is_file():
    load_dotenv(PACKAGE_DIR.parent / ".env")

# Data directory used by the legacy --repo-name scripts:
#   $CWB_DATA_DIR  >  <repo root>/data (source checkout)  >  ./data
DATA_DIR = _resolve_data_dir()

API_KEY = os.getenv("API_KEY", "sk-1234")
MODEL = os.getenv("MODEL", "claude-sonnet-4")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
BASE_URL = os.getenv("BASE_URL", "http://localhost:4000/")

def get_project_path(*paths):
    """Get a path relative to the project root"""
    return str(PROJECT_ROOT.joinpath(*paths))

def get_data_path(*paths):
    """Get a path relative to the data directory"""
    return str(DATA_DIR.joinpath(*paths))

# max tokens per tool response
MAX_TOKENS_PER_TOOL_RESPONSE = 36_000



