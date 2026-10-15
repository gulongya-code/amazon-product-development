"""Run the local market/PDS workflow without installing or editing PYTHONPATH."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from amazon_product_intelligence.market_pds_workflow import main

if __name__ == '__main__':
    raise SystemExit(main())
