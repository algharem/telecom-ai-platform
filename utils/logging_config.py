
# utils/logging_config.py - FINAL FIXED VERSION

import logging
import sys
from pythonjsonlogger import jsonlogger
from typing import Any, Dict
from datetime import datetime


class TelecomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that properly sets all fields"""
    
    def __init__(self, fmt: str = "%(message)s", *args, **kwargs):
        # Don't use rename_fields - handle manually
        super().__init__(fmt, *args, **kwargs)
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        # Don't call parent - it sets fields to None
        # super().add_fields(log_record, record, message_dict)
        
        # Set timestamp explicitly
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Set level from record
        log_record['level'] = record.levelname
        
        # Set logger name
        log_record['name'] = record.name
        
        # Set message (getMessage() renders the format string)
        log_record['message'] = record.getMessage()
        
        # Add service context
        log_record['service'] = 'telecom-ai-platform'
        log_record['environment'] = 'production'
        
        # Add source location
        log_record['source'] = {
            'file': record.filename,
            'line': record.lineno,
            'function': record.funcName
        }
        
        # Copy any extra fields from message_dict
        for key, value in message_dict.items():
            if key not in log_record:
                log_record[key] = value


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> logging.Logger:
    """
    Configure structured logging - SINGLETON pattern to prevent duplicates.
    """
    logger = logging.getLogger("telecom_ai")
    
    # CRITICAL: Check if already configured
    if logger.handlers:
        # Already configured, just return
        return logger
    
    # Set level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if log_format == "json":
        formatter = TelecomJsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger
