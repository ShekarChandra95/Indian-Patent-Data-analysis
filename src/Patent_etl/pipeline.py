"""Pipeline orchestration: wires extract -> transform -> load together."""

from __future__ import annotations

import logging

from .config import PipelineConfig
from .extract import extract
from .load import load_all
from .transform import transform

logger = logging.getLogger(__name__)


def run_pipeline(cfg: PipelineConfig) -> dict:
    """Run the full ETL pipeline and return the in-memory result tables.

    Returning the tables (not just writing files) makes this callable
    from a notebook or another script without shelling out.
    """
    logger.info("Starting pipeline run: input=%s output_dir=%s", cfg.input_path, cfg.output_dir)

    raw = extract(cfg.input_path, sheet_name=cfg.sheet_name)
    tables = transform(
        raw,
        as_of=cfg.as_of,
        due_soon_days=cfg.due_soon_days,
        due_later_days=cfg.due_later_days,
    )
    load_all(tables, cfg.output_dir, cfg.formats)

    logger.info("Pipeline run complete.")
    return tables
