from pydantic_settings import BaseSettings
from pathlib import Path
import yaml
from typing import Dict, Any


class Settings(BaseSettings):
    """Application settings loaded from config.yaml"""
    
    APP_NAME: str = "telecom-ai-platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    MODEL_PATH: str = "./data/anomaly_detector.pkl"
    CONTAMINATION: float = 0.05
    
    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "Settings":
        """Load settings from YAML file"""
        try:
            if Path(path).exists():
                with open(path, 'r') as f:
                    config = yaml.safe_load(f)

                return cls(
                    APP_NAME=config.get('app', {}).get('name', "telecom-ai-platform"),
                    APP_VERSION=config.get('app', {}).get('version', "1.0.0"),
                    DEBUG=config.get('app', {}).get('debug', False),
                    API_HOST=config.get('api', {}).get('host', "0.0.0.0"),
                    API_PORT=config.get('api', {}).get('port', 8000),
                    MODEL_PATH=config.get('ml', {}).get('model_path', "./data/anomaly_detector.pkl"),
                    CONTAMINATION=config.get('ml', {}).get('contamination', 0.05)
                )
        except Exception as e:
            # If loading fails (e.g., during testing with mocked objects), use defaults
            print(f"[CONFIG] Warning: Could not load YAML config: {e}. Using defaults.")
        return cls()


# Load settings, handling both production and test scenarios
try:
    settings = Settings.from_yaml()
except Exception:
    # Fallback for test environments with mocked imports
    settings = Settings()





