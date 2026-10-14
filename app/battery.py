"""Optional Windows battery shutdown, independent of the inference loop."""

from __future__ import annotations

import logging
import os
import subprocess
import threading

logger = logging.getLogger("voiceanalyzer")


def read_battery() -> tuple[int, bool] | None:
    if os.name != "nt":
        return None
    command = ("$b = Get-CimInstance Win32_Battery | Select-Object -First 1; "
               "if ($null -ne $b) { \"$($b.EstimatedChargeRemaining) $($b.BatteryStatus)\" }")
    try:
        result = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", command],
                                capture_output=True, text=True, timeout=20, check=True,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if not result.stdout.strip():
            return None
        percent, status = map(int, result.stdout.split())
        return (percent, status == 1) if 0 <= percent <= 100 else None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        logger.warning("battery read failed - error=%s", str(exc).replace("\n", " "))
        return None


class BatteryShutdown:
    def __init__(self, percent: int, interval_ms: int = 60000, grace_sec: int = 120):
        if not 0 <= percent <= 100 or interval_ms < 1000 or grace_sec < 0:
            raise ValueError("invalid VoiceAnalyzer battery shutdown settings")
        self.percent = percent
        self.interval = interval_ms / 1000
        self.grace = grace_sec
        self.scheduled = False
        self.stopped = threading.Event()

    def check(self):
        if not self.percent or self.scheduled:
            return
        battery = read_battery()
        if not battery or not battery[1] or battery[0] > self.percent:
            return
        try:
            # Replace an existing timed shutdown, as the battery may run out sooner.
            subprocess.run(["shutdown", "/a"], capture_output=True, timeout=20, check=False)
            subprocess.run(["shutdown", "/s", "/t", str(self.grace), "/c",
                            f"VoiceAnalyzer worker: battery {battery[0]}%"],
                           capture_output=True, timeout=20, check=True)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.error("battery shutdown failed - error=%s", str(exc).replace("\n", " "))
            return
        self.scheduled = True
        logger.warning("battery shutdown scheduled - percent=%s threshold=%s graceSec=%s",
                       battery[0], self.percent, self.grace)

    def start(self):
        if not self.percent or os.name != "nt":
            return
        def loop():
            while not self.stopped.is_set():
                self.check()
                if self.stopped.wait(self.interval):
                    break
        threading.Thread(target=loop, name="battery-check", daemon=True).start()

    @classmethod
    def from_env(cls):
        return cls(int(os.environ.get("VOICE_WORKER_BATTERY_SHUTDOWN_PERCENT", "0")),
                   int(os.environ.get("VOICE_WORKER_BATTERY_CHECK_MS", "60000")),
                   int(os.environ.get("VOICE_WORKER_BATTERY_GRACE_SEC", "120")))
