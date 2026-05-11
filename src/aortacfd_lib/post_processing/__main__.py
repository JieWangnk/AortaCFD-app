"""
Entry point for running post-processing as a module.

Usage:
    python -m aortacfd_lib.post_processing /path/to/case [options]
"""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
