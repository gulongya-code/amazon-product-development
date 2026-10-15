"""File-only new research completion/return entry; no package installation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from amazon_product_intelligence.native_research_completion import main

if __name__ == '__main__':
    raise SystemExit(main())
