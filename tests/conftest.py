"""
Pytest configuration file for telecom-ai-platform tests.
Sets up the Python path to allow imports from the project root.
"""

import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
