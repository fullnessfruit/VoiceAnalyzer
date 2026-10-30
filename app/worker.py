"""Pull voice jobs from the common broker; never open an incoming port."""

from __future__ import annotations

import logging
import os
import sys
import time
from urllib.parse import quote

from app.battery import BatteryShutdown
from app.broker import Broker, BrokerError
from app.config import load_config
from app.diagnostics import error_details, error_summary
from app.match_log import MatchAuditLog
from app.named_match import match_requested, requested_speakers
from app.shared_secret import require_secret

logger = logging.getLogger("voiceanalyzer")


def _record_event(audit, event: str, **fields) -> None:
    # Audit failure must not stop broker recovery or release of a failed job.
    try:
        audit.record(event, **fields)
    except Exception as exc:
        logger.error("voice error audit failed - jobId=%s error=%s", fields.get("jobId"), error_summary(exc))


def run_job(config, job: dict, audit: MatchAuditLog) -> dict:
    if job.get("kind") != "voice":
        raise ValueError("voice worker received a non-voice job")
    names = job.get("names", [])
    selected, skipped = requested_speakers(config, names)
    if not selected:
        return {"found": [], "matches": [], "skippedNames": skipped}
    matches = []
    errors = []
    media_failures = []
    for url in dict.fromkeys(job.get("mediaUrls", [])):
        media_matches = []
        details = None
        error = None
        try:
            result = match_requested(config, selected, url)
            media_matches = [{**item, "mediaUrl": url} for item in result["matches"]]
            matches.extend(media_matches)
        except Exception as exc:
            details = error_details(exc)
            error = error_summary(exc)
            errors.append(f"{url}: {error}")
            media_failures.append({"mediaUrl": url, "causes": details})
        audit.record("voice_media_result", jobId=job["jobId"], postUrl=job.get("postUrl"),
                     mediaUrl=url, matches=media_matches, errors=[error] if error else [],
                     **({"errorDetail": details} if details is not None else {}))
    if errors and not matches:
        failure = RuntimeError(f"all {len(errors)} media inputs failed")
        failure.diagnostics = {"mediaFailures": media_failures}
        raise failure
    return {"found": list(dict.fromkeys(item["speaker_id"] for item in matches if item["present"])),
            "matches": matches, "skippedNames": skipped,
            "error": None, "warnings": errors}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    broker = Broker(os.environ.get("OCR_BROKER_URL", "http://localhost:3100"), require_secret())
    worker_id = os.environ.get("VOICE_WORKER_ID", f"voiceanalyzer-{os.getpid()}")
    interval = max(1, int(os.environ.get("VOICE_WORKER_INTERVAL_MS", "60000")) / 1000)
    audit = MatchAuditLog(config.log_dir)
    battery = BatteryShutdown.from_env()
    verified = False
    claim_error_pending = False
    try:
        battery.start()
        _record_event(audit, "voice_worker_started", workerId=worker_id)
        logger.info("voice worker ready - broker=%s workerId=%s batteryThreshold=%s", broker.url, worker_id, battery.percent)
        while True:
            job = None
            stage = "claim"
            try:
                if not verified:
                    status = broker.request("GET", "/status")
                    if "voice" not in status.get("kinds", []):
                        raise RuntimeError("update the common broker: voice jobs are not supported")
                    verified = True
                result = broker.request("POST", "/claim", {"workerId": worker_id, "max": 1, "kinds": ["voice"]})
                if claim_error_pending:
                    _record_event(audit, "voice_broker_recovered", workerId=worker_id)
                    claim_error_pending = False
                jobs = result.get("jobs", [])
                if jobs:
                    job = jobs[0]
                    started = time.monotonic()
                    audit.record("voice_job_started", jobId=job["jobId"], postUrl=job.get("postUrl"), names=job.get("names"))
                    stage = "analysis"
                    payload = run_job(config, job, audit)
                    payload["elapsedMs"] = round((time.monotonic() - started) * 1000)
                    stage = "result_upload"
                    broker.request("POST", f"/jobs/{quote(job['jobId'], safe='')}/result", payload)
                    audit.record("voice_job_finished", jobId=job["jobId"], **payload)
                    continue
            except Exception as exc:
                if job is None and stage == "claim":
                    claim_error_pending = True
                error = error_summary(exc)
                _record_event(audit, "voice_job_error", jobId=job.get("jobId") if job else None,
                             workerId=worker_id, stage=stage, error=error, errorDetail=error_details(exc))
                logger.error("voice worker failed - jobId=%s stage=%s error=%s", job.get("jobId") if job else "-", stage, error)
                if job:
                    if isinstance(exc, BrokerError) and exc.status == 409:
                        continue
                    try:
                        broker.request("POST", f"/jobs/{quote(job['jobId'], safe='')}/release", {"error": f"{stage}: {error}"})
                        _record_event(audit, "voice_job_released", jobId=job["jobId"], workerId=worker_id, error=error)
                    except Exception as release_error:
                        _record_event(audit, "voice_release_error", jobId=job["jobId"], workerId=worker_id,
                                     error=error_summary(release_error))
                        logger.warning("voice release failed - jobId=%s error=%s", job["jobId"], error_summary(release_error))
            time.sleep(interval)
    finally:
        battery.stopped.set()
        uncaught = sys.exc_info()[1]
        reason = type(uncaught).__name__ if uncaught is not None else "normal"
        fields = {"workerId": worker_id, "reason": reason}
        if uncaught is not None:
            fields["error"] = error_summary(uncaught)
            fields["errorDetail"] = error_details(uncaught)
        _record_event(audit, "voice_worker_stopped", **fields)
        logger.info("voice worker stopped - workerId=%s reason=%s", worker_id, reason)


if __name__ == "__main__":
    main()
