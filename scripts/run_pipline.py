#!/usr/bin/env python3
"""CLI entry point for the patent due-date ETL pipeline.

Usage
-----
    python scripts/run_pipeline.py --input data/raw/IndianPatentFilingDateNew.xlsx

    python scripts/run_pipeline.py \\
        --input data/raw/IndianPatentFilingDateNew.xlsx \\
        --output-dir output \\
        --due-soon-days 30 \\
        --due-later-days 90 \\
        --formats sqlite excel csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from patent_etl.config import PipelineConfig  # noqa: E402
from patent_etl.pipeline import run_pipeline  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="Path to the source .xlsx workbook")
    parser.add_argument("--output-dir", default="output", help="Directory to write outputs into")
    parser.add_argument("--sheet-name", default="IndianPatentFilingDateNew", help="Sheet holding case-level data")
    parser.add_argument("--as-of", default=None, help="ISO date (YYYY-MM-DD) to anchor due-date math to; default today")
    parser.add_argument("--due-soon-days", type=int, default=30, help="Cutoff (days) for the 'due soon' urgency band")
    parser.add_argument("--due-later-days", type=int, default=90, help="Cutoff (days) for the 'due later' urgency band")
    parser.add_argument(
        "--formats", nargs="+", default=["sqlite", "excel", "csv"],
        choices=["sqlite", "excel", "csv"], help="Which output format(s) to write",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    cfg = PipelineConfig(
        input_path=args.input,
        output_dir=args.output_dir,
        sheet_name=args.sheet_name,
        as_of=args.as_of,
        due_soon_days=args.due_soon_days,
        due_later_days=args.due_later_days,
        formats=tuple(args.formats),
    )

    tables = run_pipeline(cfg)

    print("\nSummary")
    print("-------")
    print(f"Total cases:          {len(tables['cases']):,}")
    print(f"Unique clients:       {tables['cases']['client_name'].nunique():,}")
    print(f"Pending RQ (active):  {int(tables['pending_rq']['action_required'].sum()):,}")
    overdue = tables["pending_rq"].query("urgency == 'OVERDUE' and action_required")
    print(f"Overdue RQ:           {len(overdue):,}")
    print(f"\nOutputs written to:   {Path(args.output_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
