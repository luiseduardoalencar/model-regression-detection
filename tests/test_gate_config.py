"""`config/gate.yaml`: the committed values, and the contents that must be refused."""

from pathlib import Path

import pytest

from regression_detector.compare.gate_config import (
    AdversarialMode,
    GateConfigError,
    load_gate_config,
)

REPO_GATE = Path(__file__).parents[1] / "config" / "gate.yaml"

VALID = """
golden_edition: 1
infra_error_limit_percent: 2
net_drop: {warn: 5, block: 7}
adversarial_invariant: block
absolute_floor: {acceptable_accuracy: null, format_pass_rate: null}
"""


def test_the_committed_gate_holds_the_decided_values():
    config = load_gate_config(REPO_GATE)
    assert config.golden_edition == 1
    assert config.infra_error_limit_percent == 2
    assert (config.net_drop.warn, config.net_drop.block) == (5, 7)
    assert config.adversarial_invariant == AdversarialMode.BLOCK
    # The floor stays empty until the first measured run (build step 12).
    assert config.absolute_floor.acceptable_accuracy is None
    assert config.absolute_floor.format_pass_rate is None


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "gate.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_floor_can_be_set(tmp_path):
    text = VALID.replace("acceptable_accuracy: null", "acceptable_accuracy: 0.9")
    assert load_gate_config(write(tmp_path, text)).absolute_floor.acceptable_accuracy == 0.9


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("warn: 5, block: 7", "warn: 7, block: 7", "lower than net_drop.block"),
        ("warn: 5", "warn: 0", "greater than 0"),
        ("acceptable_accuracy: null", "acceptable_accuracy: 95", "less than or equal to 1"),
        ("adversarial_invariant: block", "adversarial_invariant: ignore", "'block' or 'warn'"),
        ("golden_edition: 1", "golden_edition: 1\nthreshold: 3", "Extra inputs"),
        ("infra_error_limit_percent: 2\n", "", "infra_error_limit_percent"),
    ],
)
def test_invalid_contents_are_refused(tmp_path, old, new, message):
    with pytest.raises(GateConfigError, match=message):
        load_gate_config(write(tmp_path, VALID.replace(old, new)))


def test_a_missing_or_broken_file_is_refused(tmp_path):
    with pytest.raises(GateConfigError, match="cannot be read"):
        load_gate_config(tmp_path / "missing.yaml")
    with pytest.raises(GateConfigError, match="not valid YAML"):
        load_gate_config(write(tmp_path, "net_drop: [warn"))
    with pytest.raises(GateConfigError, match="must be a YAML mapping"):
        load_gate_config(write(tmp_path, "- 1\n- 2\n"))
