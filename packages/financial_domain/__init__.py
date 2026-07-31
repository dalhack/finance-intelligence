"""
Finance Intelligence — Pure Python Financial Calculation Domain Package
=============================================================================
IMPORTANT ARCHITECTURAL SCOPE RULE:
- This package is strictly for Python backend and worker domain modules.
- Flutter mobile app cannot import or execute Python code directly.
- Wire sharing with mobile clients is handled strictly via versioned contracts.
"""

from decimal import Decimal, getcontext

# Enforce working context precision of 38 significant digits
getcontext().prec = 38

__all__ = ["Decimal", "getcontext"]
__version__ = "0.1.0"
