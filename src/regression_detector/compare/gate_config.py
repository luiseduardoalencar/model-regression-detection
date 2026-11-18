"""Contents of `config/gate.yaml`: the numbers that decide the gate (decisions 3.4, 3.5, 5.1)."""

from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

DEFAULT_GATE_PATH = Path("config/gate.yaml")


class GateConfigError(Exception):
    """`config/gate.yaml` cannot be used; no verdict can be given."""


class AdversarialMode(StrEnum):
    """What an adversarial case going from pass to fail does to the verdict."""

    BLOCK = "block"
    WARN = "warn"


class NetDropThresholds(BaseModel):
    """Net drop, in cases, from which a signal warns and from which it blocks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    warn: int = Field(gt=0)
    block: int = Field(gt=0)

    @model_validator(mode="after")
    def warn_below_block(self) -> Self:
        if self.warn >= self.block:
            raise ValueError("net_drop.warn must be lower than net_drop.block")
        return self


class AbsoluteFloor(BaseModel):
    """Minimum rates of the candidate (fractions); None turns the rule off."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    acceptable_accuracy: float | None = Field(default=None, ge=0, le=1)
    format_pass_rate: float | None = Field(default=None, ge=0, le=1)


class GateConfig(BaseModel):
    """The whole `config/gate.yaml`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    golden_edition: int = Field(gt=0)
    infra_error_limit_percent: int = Field(ge=0, le=100)
    net_drop: NetDropThresholds
    adversarial_invariant: AdversarialMode
    absolute_floor: AbsoluteFloor


def load_gate_config(path: Path = DEFAULT_GATE_PATH) -> GateConfig:
    """Read and validate the gate configuration."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise GateConfigError(f"{path}: cannot be read ({error.strerror})") from error
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise GateConfigError(f"{path}: not valid YAML ({error})") from error
    if not isinstance(data, dict):
        raise GateConfigError(f"{path}: must be a YAML mapping")
    try:
        return GateConfig.model_validate(data)
    except ValidationError as error:
        raise GateConfigError(f"{path}: invalid contents\n{error}") from error
