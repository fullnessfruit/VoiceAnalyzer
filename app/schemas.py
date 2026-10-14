"""HTTP bodies."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


def _speaker_id(value: str) -> str:
    if value != value.strip() or not value or value.endswith("."):
        raise ValueError("invalid speaker_id")
    # These characters are illegal in Windows directory names.
    if any(char in value for char in '<>:"/\\|?*') or any(ord(char) < 32 for char in value):
        raise ValueError("invalid speaker_id")
    return value


class MatchRequest(BaseModel):
    file_path: str = Field(min_length=1)
    speaker_id: str = Field(min_length=1, max_length=128)
    separate_bgm: bool = False
    source_url: str | None = Field(default=None, max_length=4096)

    @field_validator("speaker_id")
    @classmethod
    def check_speaker_id(cls, value: str) -> str:
        return _speaker_id(value)

    @field_validator("source_url")
    @classmethod
    def check_source_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = urlsplit(value)
            valid = (parsed.scheme in {"http", "https"} and parsed.hostname is not None
                     and parsed.username is None and parsed.password is None)
        except ValueError:
            valid = False
        if not valid or any(char.isspace() or ord(char) < 32 for char in value):
            raise ValueError("source_url must be an HTTP(S) URL without credentials")
        return value


class NamesMatchRequest(BaseModel):
    names: list[str] = Field(min_length=1, max_length=200)
    file_path: str | None = None
    media_url: str | None = None
    separate_bgm: bool = False

    @field_validator("names")
    @classmethod
    def check_names(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(_speaker_id(value) for value in values))

    @model_validator(mode="after")
    def check_input(self):
        if bool(self.file_path) == bool(self.media_url):
            raise ValueError("provide exactly one of file_path or media_url")
        return self


class EnrollRequest(BaseModel):
    speaker_id: str | None = None
    file_paths: list[str] | None = None

    @field_validator("speaker_id")
    @classmethod
    def check_speaker_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _speaker_id(value)
