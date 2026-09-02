import time
from pathlib import Path

from acceptance_ext.jobs import JobManager


def wait_for_terminal(manager: JobManager, job_id: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = manager.get_job(job_id)
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_demo_job_persists_result_and_events(tmp_path: Path) -> None:
    manager = JobManager(workspace=tmp_path, max_workers=1)
    try:
        created = manager.create_demo_job()
        job = wait_for_terminal(manager, created["job_id"])
        assert job["status"] == "succeeded", job.get("error_detail")
        assert job["progress"] == 1.0
        result = manager.get_result(job["job_id"])
        assert result.metrics["acceptance_item_count"] == 4
        events = manager.get_events(job["job_id"])["events"]
        assert any(event["stage"] == "parse" for event in events)
        assert any(event["kind"] == "summary" for event in events)
        assert (tmp_path / "jobs" / job["job_id"] / "events.jsonl").exists()
    finally:
        manager.shutdown(wait=True)


def test_result_edit_creates_revision(tmp_path: Path) -> None:
    manager = JobManager(workspace=tmp_path, max_workers=1)
    try:
        job = wait_for_terminal(manager, manager.create_demo_job()["job_id"])
        result = manager.get_result(job["job_id"])
        result.tree[0].name = "模板工程（人工修订）"
        manager.save_result(job["job_id"], result.model_dump(mode="json"))
        updated = manager.get_job(job["job_id"])
        assert updated["result_revision"] == 1
        assert manager.get_result(job["job_id"]).tree[0].name.endswith("人工修订）")
    finally:
        manager.shutdown(wait=True)
