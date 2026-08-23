"""Extract stage: read the raw case list out of the source workbook.

This stage does the minimum possible: open the correct sheet, drop rows
that are structurally blank, and return a DataFrame with the *original*
column names untouched. Renaming, type coercion, and business logic all
live in transform.py, so extract.py stays a thin, easily-testable I/O
boundary.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from .config import SOURCE_SHEET_NAME

logger = logging.getLogger(__name__)


def extract(input_path: str | Path, sheet_name: str = SOURCE_SHEET_NAME) -> pd.DataFrame:
    """Read the case-level sheet from the source workbook.

    Parameters
    ----------
    input_path:
        Path to the source .xlsx workbook.
    sheet_name:
        Name of the sheet holding row-level case data. The workbook also
        contains other sheets (e.g. a stale duplicate, a linked-table
        placeholder) that must NOT be read.

    Returns
    -------
    A DataFrame with raw column headers, one row per case, with fully
    blank trailing rows removed.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Source workbook not found: {input_path}")

    logger.info("Reading sheet %r from %s", sheet_name, input_path)
    df = pd.read_excel(input_path, sheet_name=sheet_name, engine="openpyxl")

    before = len(df)
    df = df[df["Sr. No."].notna()].reset_index(drop=True)
    dropped = before - len(df)
    if dropped:
        logger.info("Dropped %d fully blank trailing row(s)", dropped)

    logger.info("Extracted %d raw case rows, %d columns", len(df), df.shape[1])
    return df


def list_sheet_names(input_path: str | Path) -> list[str]:
    """Utility used by tests / CLI diagnostics to sanity-check a workbook."""
    return pd.ExcelFile(Path(input_path), engine="openpyxl").sheet_names
