"""
Central configuration for the patent ETL pipeline.

Keeping these as named constants (instead of scattering magic values through extract/transform/load) means a policy change -- 
e.g. the "due soon" window moving from 90 to 60 days -- only touches one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# The sheet in the source workbook that holds the row-level case data.
# The workbook also ships a couple of near-duplicate / pivot sheets that
# are NOT the source of truth and must be ignored.
SOURCE_SHEET_NAME = "IndianPatentFilingDateNew"

# Source date columns are stored as dd-mm-yyyy text in the workbook.
SOURCE_DATE_FORMAT = "%d-%m-%Y"

# Urgency windows (in days) used to bucket outstanding RQ deadlines.
DUE_SOON_DAYS = 30
DUE_LATER_DAYS = 90

# Case statuses where no further RQ action is required, even if an RQ due
# date is technically still present in the source data.
INACTIVE_STATUSES = frozenset({"ABANDONED", "CLOSED", "MERGED", "WITHDRAWN"})

# Statuses broken out individually in the client-level summary; anything
# else falls into "Other" so the summary table doesn't grow unbounded if
# a new status value shows up in a future export.
TRACKED_STATUSES = (
    "RFE FILED",
    "PROVISIONAL FILED",
    "COMPLETE FILED",
    "APPLICATION FILED",
    "UNDER EXAMINATION",
    "GRANTED",
)

# Raw source column name -> clean output column name.
# Source headers include stray newlines / trailing spaces that need
# stripping before they're usable as dict keys or DataFrame columns.
COLUMN_MAP = {
    "Sr. No.": "sr_no",
    "File No ": "file_no",
    "Application No": "application_no",
    "Client Name / Ref.": "client_name_ref",
    "Client Country": "client_country",
    "Applicant": "applicant",
    "  Title": "title",
    "Provisional/\nComplete": "provisional_complete",
    "Branch": "branch",
    "Case Recv. On": "case_received_on",
    "Filing Date": "filing_date",
    "RQ Due": "rq_due",
    "RQ Filed": "rq_filed",
    "Attorney": "attorney",
    "Paralegal": "paralegal",
    "Status": "status",
}


@dataclass(frozen=True)
class PipelineConfig:
    """Runtime-overridable settings, exposed via the CLI in scripts/run_pipeline.py."""

    input_path: str
    output_dir: str = "output"
    sheet_name: str = SOURCE_SHEET_NAME
    due_soon_days: int = DUE_SOON_DAYS
    due_later_days: int = DUE_LATER_DAYS
    as_of: str | None = None  # ISO date string; defaults to today if None
    formats: tuple[str, ...] = field(default_factory=lambda: ("sqlite", "excel", "csv"))
