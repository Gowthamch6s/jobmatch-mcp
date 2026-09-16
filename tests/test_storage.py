import pytest

from jobmatch_mcp import storage
from jobmatch_mcp.errors import ApplicationNotFoundError, InvalidQueryError


def test_create_and_list_application(isolated_db):
    row = storage.track_application(
        isolated_db, job_title="Agentic AI Engineer", company="Vertex Analytics", status="applied"
    )
    assert row["id"] is not None
    assert row["status"] == "applied"

    rows = storage.list_applications(isolated_db)
    assert len(rows) == 1
    assert rows[0]["company"] == "Vertex Analytics"


def test_update_existing_application_by_id(isolated_db):
    created = storage.track_application(
        isolated_db, job_title="ML Engineer", company="Cobalt Systems", status="saved"
    )
    updated = storage.track_application(
        isolated_db,
        job_title="ML Engineer",
        company="Cobalt Systems",
        status="interviewing",
        application_id=created["id"],
        notes="Phone screen scheduled",
    )
    assert updated["id"] == created["id"]
    assert updated["status"] == "interviewing"
    assert updated["notes"] == "Phone screen scheduled"

    rows = storage.list_applications(isolated_db)
    assert len(rows) == 1  # update, not a second insert


def test_update_unknown_id_raises_not_found(isolated_db):
    with pytest.raises(ApplicationNotFoundError):
        storage.track_application(
            isolated_db, job_title="X", company="Y", status="saved", application_id=999
        )


def test_invalid_status_raises_invalid_query(isolated_db):
    with pytest.raises(InvalidQueryError):
        storage.track_application(isolated_db, job_title="X", company="Y", status="ghosted")


def test_list_filtered_by_status(isolated_db):
    storage.track_application(isolated_db, job_title="A", company="Co1", status="applied")
    storage.track_application(isolated_db, job_title="B", company="Co2", status="rejected")

    applied_only = storage.list_applications(isolated_db, status="applied")
    assert len(applied_only) == 1
    assert applied_only[0]["job_title"] == "A"
