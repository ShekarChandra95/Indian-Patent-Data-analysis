"""Transform stage: clean raw rows and derive the analysis tables.

Produces four tidy DataFrames from the raw extract:

- ``cases``          one row per case, cleaned and typed
- ``pending_rq``      subset of cases with an outstanding RQ deadline,
                      annotated with days-remaining / urgency / whether
                      the case is still active
- ``client_summary``  one row per client, aggregated counts and the
                      client's nearest outstanding RQ deadline
- ``status_summary``  one row per case status, with counts and share of
                      the total portfolio

All date arithmetic is anchored to a single ``as_of`` timestamp so a run
is reproducible -- re-running the pipeline against the same input and
the same ``as_of`` date always yields identical output.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import pandas as pd

from .config import (
    COLUMN_MAP,
    DUE_LATER_DAYS,
    DUE_SOON_DAYS,
    INACTIVE_STATUSES,
    SOURCE_DATE_FORMAT,
    TRACKED_STATUSES,
)

logger = logging.getLogger(__name__)

_DATE_COLUMNS = ("case_received_on", "filing_date", "rq_due", "rq_filed")


def _split_client_name_ref(value: object) -> tuple[str | None, str | None]:
    """The source packs 'Client Name\\nRef Number' into a single cell."""
    if pd.isna(value):
        return None, None
    parts = str(value).split("\n")
    name = parts[0].strip() or None
    ref = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return name, ref


def clean_cases(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename, type-coerce, and enrich the raw extract into a tidy `cases` table."""
    df = raw.rename(columns=lambda c: c)  # keep original for the mapping lookup
    missing = set(COLUMN_MAP) - set(df.columns)
    if missing:
        raise KeyError(
            f"Source sheet is missing expected column(s): {sorted(missing)}. "
            "The workbook layout may have changed -- update config.COLUMN_MAP."
        )
    df = df[list(COLUMN_MAP)].rename(columns=COLUMN_MAP)

    for col in _DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col], format=SOURCE_DATE_FORMAT, errors="coerce")

    df["status"] = df["status"].fillna("UNKNOWN").str.strip().str.upper()

    client_split = df["client_name_ref"].apply(_split_client_name_ref)
    df["client_name"] = [c[0] for c in client_split]
    df["client_ref"] = [c[1] for c in client_split]
    df = df.drop(columns=["client_name_ref"])

    df["is_active"] = ~df["status"].isin(INACTIVE_STATUSES)

    logger.info("Cleaned %d cases across %d unique clients", len(df), df["client_name"].nunique())
    return df


def _resolve_as_of(as_of: str | date | datetime | None) -> pd.Timestamp:
    if as_of is None:
        return pd.Timestamp(date.today())
    return pd.Timestamp(as_of).normalize()


def build_pending_rq(
    cases: pd.DataFrame,
    as_of: str | date | datetime | None = None,
    due_soon_days: int = DUE_SOON_DAYS,
    due_later_days: int = DUE_LATER_DAYS,
) -> pd.DataFrame:
    """Cases with an RQ due date that has not yet been filed, with urgency flags."""
    as_of_ts = _resolve_as_of(as_of)

    pending = cases[cases["rq_due"].notna() & cases["rq_filed"].isna()].copy()
    pending["days_remaining"] = (pending["rq_due"] - as_of_ts).dt.days

    def _urgency(days: int) -> str:
        if days < 0:
            return "OVERDUE"
        if days <= due_soon_days:
            return f"DUE <={due_soon_days} DAYS"
        if days <= due_later_days:
            return f"DUE <={due_later_days} DAYS"
        return "UPCOMING"

    pending["urgency"] = pending["days_remaining"].apply(_urgency)
    pending["action_required"] = pending["is_active"]

    pending = pending.sort_values("rq_due").reset_index(drop=True)

    cols = [
        "file_no", "application_no", "client_name", "client_ref", "status",
        "filing_date", "rq_due", "days_remaining", "urgency", "action_required",
    ]
    logger.info(
        "Pending RQ: %d cases (%d active) as of %s",
        len(pending), int(pending["action_required"].sum()), as_of_ts.date(),
    )
    return pending[cols]


def build_client_summary(cases: pd.DataFrame, pending_rq: pd.DataFrame) -> pd.DataFrame:
    """One row per client: case counts by status bucket + nearest RQ deadline."""
    grouped = cases.groupby("client_name")

    summary = grouped.size().rename("total_cases").to_frame()

    for status in TRACKED_STATUSES:
        col = status.title().replace(" ", "_").lower()
        summary[col] = grouped.apply(lambda g, s=status: (g["status"] == s).sum())

    known = set(TRACKED_STATUSES)
    summary["other_status"] = grouped.apply(lambda g: (~g["status"].isin(known)).sum())

    active_pending = pending_rq[pending_rq["action_required"]]
    summary["pending_rq_active"] = active_pending.groupby("client_name").size()
    summary["overdue_rq"] = (
        active_pending[active_pending["urgency"] == "OVERDUE"].groupby("client_name").size()
    )
    due_soon_mask = active_pending["urgency"] != "UPCOMING"
    summary["due_within_window"] = active_pending[due_soon_mask].groupby("client_name").size()
    summary["next_rq_due"] = pending_rq.groupby("client_name")["rq_due"].min()

    fill_zero = [
        c for c in summary.columns
        if c not in ("next_rq_due",) and summary[c].dtype != "datetime64[ns]"
    ]
    summary[fill_zero] = summary[fill_zero].fillna(0).astype(int)

    summary = summary.reset_index().sort_values(
        ["overdue_rq", "due_within_window", "total_cases"], ascending=[False, False, False]
    ).reset_index(drop=True)

    return summary


def build_status_summary(cases: pd.DataFrame) -> pd.DataFrame:
    """Case count and % share per status value, sorted descending."""
    counts = cases["status"].value_counts().rename_axis("status").reset_index(name="case_count")
    counts["pct_of_total"] = (counts["case_count"] / len(cases) * 100).round(1)
    return counts


def transform(
    raw: pd.DataFrame,
    as_of: str | date | datetime | None = None,
    due_soon_days: int = DUE_SOON_DAYS,
    due_later_days: int = DUE_LATER_DAYS,
) -> dict[str, pd.DataFrame]:
    """Run the full transform stage and return all derived tables."""
    cases = clean_cases(raw)
    pending_rq = build_pending_rq(cases, as_of, due_soon_days, due_later_days)
    client_summary = build_client_summary(cases, pending_rq)
    status_summary = build_status_summary(cases)
    return {
        "cases": cases,
        "pending_rq": pending_rq,
        "client_summary": client_summary,
        "status_summary": status_summary,
    }
