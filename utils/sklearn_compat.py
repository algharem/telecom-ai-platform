"""
Sklearn compatibility utilities.

Handles version mismatches and deprecation warnings.
"""

import warnings
import os

# Suppress sklearn version warnings
os.environ['SCIKIT_LEARN_ASSUME_FINITE'] = 'True'

def suppress_sklearn_warnings():
    """Suppress sklearn-related warnings and deprecations"""
    warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')
    warnings.filterwarnings('ignore', message='.*sklearn.*')
    warnings.filterwarnings('ignore', category=FutureWarning)
