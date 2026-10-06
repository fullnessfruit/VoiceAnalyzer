"""Shared ImageAnalyzer/VoiceAnalyzer key; installation is the only creator."""

from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import sys
import tempfile

ENV_NAME = "OCR_BROKER_SECRET"


def _secret_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "announcement-analyzers" / "auth.json"


def _stored_secret() -> str:
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, ENV_NAME)
        except FileNotFoundError:
            return ""
        if not isinstance(value, str):
            raise ValueError("Invalid shared analyzer user environment value")
        return value
    try:
        raw = _secret_path().read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    try:
        value = json.loads(raw)[ENV_NAME]
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("Invalid shared analyzer key file") from exc
    if not isinstance(value, str) or not value:
        raise ValueError("Invalid shared analyzer key file")
    return value


def read_secret() -> str:
    return os.environ.get(ENV_NAME) or _stored_secret()


def require_secret() -> str:
    value = read_secret()
    if not value:
        raise RuntimeError("OCR_BROKER_SECRET is required; run the installer or configure the shared key")
    return value


def _notify_windows_environment() -> None:
    import ctypes
    from ctypes import wintypes
    send = ctypes.windll.user32.SendMessageTimeoutW
    send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR,
                     wintypes.UINT, wintypes.UINT, ctypes.c_void_p]
    send(0xFFFF, 0x001A, 0, "Environment", 2, 5000, None)


def ensure_secret() -> str:
    # A stale shell must not replace a key installed by the other analyzer.
    existing = _stored_secret()
    if existing:
        return existing
    secret = os.environ.get(ENV_NAME) or secrets.token_hex(32)
    if os.name == "nt":
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            winreg.SetValueEx(key, ENV_NAME, 0, winreg.REG_SZ, secret)
        # Refresh the environment inherited by future Explorer-launched processes.
        _notify_windows_environment()
        return _stored_secret()
    target = _secret_path()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix="auth.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({ENV_NAME: secret}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Match the Node installer: never overwrite a concurrent installer's file.
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
    finally:
        os.unlink(temporary)
    return _stored_secret()


def delete_secret() -> None:
    # Uninstallers must never call this; deletion is an explicit separate action.
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, ENV_NAME)
        except FileNotFoundError:
            pass
        _notify_windows_environment()
    else:
        _secret_path().unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        command = sys.argv[1] if len(sys.argv) == 2 else ""
        if command == "ensure":
            ensure_secret()
            print("Shared OCR_BROKER_SECRET is ready; existing keys are preserved.")
        elif command == "show":
            print(_stored_secret() or require_secret())
        elif command == "delete":
            delete_secret()
            print("Deleted the persisted shared OCR_BROKER_SECRET. Reconfigure both analyzers and their clients together.")
            print("Running services and terminals retain their old environment until restarted.")
        else:
            raise ValueError("Usage: shared_secret.py ensure|show|delete")
    except Exception as error:
        print(f"Shared analyzer key setup failed: {error}", file=sys.stderr)
        sys.exit(1)
