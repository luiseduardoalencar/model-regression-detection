"""Loader of versioned prompt files and of the `prompts/active.yaml` pointer (decision 1.3)."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from regression_detector.feature.prompt_config import PromptConfig

PROMPTS_DIR = Path("prompts")
ACTIVE_FILE_NAME = "active.yaml"
CLASSIFIER_FOLDER = "classifier"


class PromptFileError(Exception):
    """A prompt file or the active pointer cannot be used; the run must not start."""


class ActivePrompts(BaseModel):
    """The contents of `prompts/active.yaml`: which version of each prompt is in use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    classifier: str = Field(pattern=r"^v\d+$")


@dataclass(frozen=True)
class LoadedPrompt:
    """A validated prompt plus the identity every run records: version and file hash."""

    config: PromptConfig
    path: Path
    sha256: str

    @property
    def version_id(self) -> str:
        return self.config.version_id


def load_classifier_prompt(path: Path) -> LoadedPrompt:
    """Read, validate and fingerprint one classifier prompt file."""
    raw = _read_bytes(path)
    config = _validate(PromptConfig, _parse_yaml(path, raw), path)
    if config.version_id != path.stem:
        raise PromptFileError(
            f"{path}: version_id {config.version_id!r} does not match the file name"
        )
    return LoadedPrompt(config=config, path=path, sha256=hashlib.sha256(raw).hexdigest())


def load_active_classifier(prompts_dir: Path = PROMPTS_DIR) -> LoadedPrompt:
    """The classifier prompt that `active.yaml` points to."""
    active_path = prompts_dir / ACTIVE_FILE_NAME
    active = _validate(
        ActivePrompts, _parse_yaml(active_path, _read_bytes(active_path)), active_path
    )
    return load_classifier_prompt(prompts_dir / CLASSIFIER_FOLDER / f"{active.classifier}.yaml")


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise PromptFileError(f"{path}: cannot be read ({error.strerror})") from error


def _parse_yaml(path: Path, raw: bytes) -> dict[str, Any]:
    # safe_load builds only plain mappings, lists and scalars, never Python objects.
    try:
        data = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise PromptFileError(f"{path}: not valid YAML ({error})") from error
    if not isinstance(data, dict):
        raise PromptFileError(f"{path}: must be a YAML mapping")
    return data


def _validate[M: BaseModel](model: type[M], data: dict[str, Any], path: Path) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise PromptFileError(f"{path}: invalid contents\n{error}") from error
