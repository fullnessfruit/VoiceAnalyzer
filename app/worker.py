"""Pull voice jobs from the common broker; never open an incoming port."""

from __future__ import annotations

import logging
import os
import time
from urllib.parse import quote

from app.battery import BatteryShutdown
from app.broker import Broker, BrokerError
from app.config import load_config
from app.match_log import MatchAuditLog
from app.named_match import match_requested, requested_speakers
from app.shared_secret import require_secret

logger = logging.getLogger("voiceanalyzer")


def run_job(config, job: dict, audit: MatchAuditLog) -> dict:
    if job.get("kind") != "voice":
        raise ValueError("voice worker received a non-voice job")
    names = job.get("names", [])
    selected, skipped = requested_speakers(config, names)
    if not selected:
        return {"found": [], "matches": [], "skippedNames": skipped}
    matches = []
    errors = []
    for url in dict.fromkeys(job.get("mediaUrls", [])):
        try:
            result = match_requested(config, selected, url)
            matches.extend({**item, "mediaUrl": url} for item in result["matches"])
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        audit.record("voice_media_result", jobId=job["jobId"], postUrl=job.get("postUrl"),
                     mediaUrl=url, matches=matches, errors=errors)
    if errors and not matches:
        raise RuntimeError("; ".join(errors))
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
    battery.start()
    logger.info("voice worker ready - broker=%s workerId=%s batteryThreshold=%s", broker.url, worker_id, battery.percent)
    verified = False
    try:
        while True:
            job = None
            try:
                if not verified:
                    status = broker.request("GET", "/status")
                    if "voice" not in status.get("kinds", []):
                        raise RuntimeError("update the common broker: voice jobs are not supported")
                    verified = True
                result = broker.request("POST", "/claim", {"workerId": worker_id, "max": 1, "kinds": ["voice"]})
                jobs = result.get("jobs", [])
                if jobs:
                    job = jobs[0]
                    started = time.monotonic()
                    audit.record("voice_job_started", jobId=job["jobId"], postUrl=job.get("postUrl"), names=job.get("names"))
                    payload = run_job(config, job, audit)
                    payload["elapsedMs"] = round((time.monotonic() - started) * 1000)
                    broker.request("POST", f"/jobs/{quote(job['jobId'], safe='')}/result", payload)
                    audit.record("voice_job_finished", jobId=job["jobId"], **payload)
                    continue
            except Exception as exc:
                audit.record("voice_job_error", jobId=job.get("jobId") if job else None, error=str(exc))
                logger.error("voice worker failed - jobId=%s error=%s", job.get("jobId") if job else "-", str(exc).replace("\n", " "))
                if job:
                    if isinstance(exc, BrokerError) and exc.status == 409:
                        continue
                    try:
                        broker.request("POST", f"/jobs/{quote(job['jobId'], safe='')}/release", {})
                    except Exception as release_error:
                        logger.warning("voice release failed - error=%s", str(release_error).replace("\n", " "))
            time.sleep(interval)
    finally:
        battery.stopped.set()


if __name__ == "__main__":
    main()
