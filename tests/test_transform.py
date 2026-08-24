""" Unit test for patent_etl.transform
These use a small synthetic DataFrame shaped like the raw extract, so they run in milliseconds and don't depend on the real (large, private) source workbook
"""

from __future__ import annotations
import pandas as pd
import pytest

from patent_etl.transform import (
    build_client_summary,
    build_pending_rq,
    build_status_summary,
    clean_cases
)

def _raw_row(**overrides) -> dict:
    row = {
        "Sr. No.": 1,
        "File No ": "IP00001",
        "Application No": "202511000001",
        "Client Name / Ref.": "ACME CORP\nREF-001",
        "Client Country": "United States Of America",
        "Applicant": "ACME CORP",
        "  Title": "A WIDGET",
        "Provisional/\nComplete": None,
        "Branch": "GURGAON",
        "Case Recv. On": "01-01-2025",
        "Filing Date": "05-01-2025",
        "RQ Due": "05-01-2029",
        "RQ Filed": None,
        "Attorney": "Jane Doe",
        "Paralegal": "John Roe",
        "Status": "PROVISIONAL FILED",
    }
    row.update(overrides)
    return row

@pytest.fixture
def raw_df() -> pd.DataFrame:
  return pd.DataFrame(
    [
      _raw_row(),
      _raw_row(
        **{
            "Sr. No.":2,
            "File No":"IP00002",
            "Client Name / Ref.": "ACME CORP\nREF-002",
            "RQ Due": "01-01-2020",  # overdue relative to as_of below
            "Status": "COMPLETE FILED",
        }
      )
      _raw_row(
          **{
            "Sr. No.": 3,
            "File No ": "IP00003",
            "Client Name / Ref.": "BETA LTD\nREF-100",
            "RQ Due": "01-06-2025",
            "RQ Filed": "01-05-2025",  # already filed -> not pending
            "Status": "RFE FILED",
        }
    ),
    _raw_row(
        **{
            "Sr. No.": 4,
            "File No ": "IP00004",
            "Client Name / Ref.": "BETA LTD\nREF-101",
            "RQ Due": "01-01-2026",
            "Status": "ABANDONED",  # inactive -> excluded from action_required
        }
    ),
        ]
    )

def test_clean_cases_splits_client_name_and_ref(raw_df):
    cases = clean_cases(raw_df)
    assert list(cases["client_name"]) == ["ACME CORP", "ACME CORP", "BETA LTD", "BETA LTD"]
    assert list(cases["client_ref"]) == ["REF-001", "REF-002", "REF-100", "REF-101"]


def test_clean_cases_parses_dates(raw_df):
    cases = clean_cases(raw_df)
    assert cases.loc[0, "filing_date"] == pd.Timestamp("2025-01-05")
    assert pd.isna(cases.loc[0, "rq_filed"])


def test_clean_cases_flags_inactive_status(raw_df):
    cases = clean_cases(raw_df)
    assert cases.loc[3, "is_active"] is False or cases.loc[3, "is_active"] == False  # noqa: E712
    assert bool(cases.loc[0, "is_active"]) is True


def test_pending_rq_excludes_already_filed(raw_df):
    cases = clean_cases(raw_df)
    pending = build_pending_rq(cases, as_of="2025-06-01")
    # Row index 2 (BETA LTD REF-100) had RQ Filed set -> must not appear
    assert "IP00003" not in set(pending["file_no"])
    assert len(pending) == 3


def test_pending_rq_urgency_buckets(raw_df):
    cases = clean_cases(raw_df)
    pending = build_pending_rq(cases, as_of="2025-06-01", due_soon_days=30, due_later_days=90)
    by_file = pending.set_index("file_no")
    assert by_file.loc["IP00002", "urgency"] == "OVERDUE"
    assert by_file.loc["IP00001", "urgency"] == "UPCOMING"


def test_pending_rq_action_required_respects_active_flag(raw_df):
    cases = clean_cases(raw_df)
    pending = build_pending_rq(cases, as_of="2025-06-01")
    by_file = pending.set_index("file_no")
    assert bool(by_file.loc["IP00004", "action_required"]) is False  # ABANDONED
    assert bool(by_file.loc["IP00001", "action_required"]) is True


def test_client_summary_counts_per_client(raw_df):
    cases = clean_cases(raw_df)
    pending = build_pending_rq(cases, as_of="2025-06-01")
    summary = build_client_summary(cases, pending).set_index("client_name")
    assert summary.loc["ACME CORP", "total_cases"] == 2
    assert summary.loc["BETA LTD", "total_cases"] == 2
    # Only IP00001 is active + pending for ACME CORP after IP00002 counted too
    assert summary.loc["ACME CORP", "pending_rq_active"] == 2
    assert summary.loc["ACME CORP", "overdue_rq"] == 1


def test_status_summary_sums_to_total(raw_df):
    cases = clean_cases(raw_df)
    status_summary = build_status_summary(cases)
    assert status_summary["case_count"].sum() == len(cases)
    assert pytest.approx(status_summary["pct_of_total"].sum(), abs=0.2) == 100.0


def test_clean_cases_raises_on_missing_column():
    bad_df = pd.DataFrame([{"Sr. No.": 1}])
    with pytest.raises(KeyError):
        clean_cases(bad_df)
