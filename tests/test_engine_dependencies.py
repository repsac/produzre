"""Tests for engine dependency validation (Phase N3).

Verifies that:
1. Engines with unsatisfied requirements produce clear error messages
2. Error messages suggest which engines provide the missing requirements
3. Engines with no requirements pass validation
4. Engines with satisfied requirements pass validation
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from produzre.config.errors import ConfigError
from produzre.model import Engine, RootConfig
from produzre.orchestrate.plan import PerformancePlan
from produzre.orchestrate.render import (
    _find_providers_for_requirement,
    _validate_engine_dependencies,
)


def create_mock_engine(
    name: str,
    requires: Optional[List[str]] = None,
    provides: Optional[List[str]] = None,
    priority: int = 50,
) -> Engine:
    """Create a mock Engine for testing."""
    def mock_render(*args, **kwargs):
        pass

    return Engine(
        name=name,
        module_path=f".engine.{name}",
        priority=priority,
        channel=0,
        program=None,
        render=mock_render,
        enabled=True,
        requires=requires or [],
        provides=provides or [],
        roles=[],
    )


def create_mock_config(engines: Dict[str, Engine]) -> RootConfig:
    """Create a minimal mock RootConfig for testing."""
    @dataclass
    class MockSongConfig:
        title: str = "test"
        bpm: float = 120.0
        key: str = "C"
        mode: str = "ionian"
        meter: str = "4/4"
        beats_per_bar: int = 4
        seed: int = 0
        take: int = 0
        variation: float = 0.0
        humanize_velocity: float = 0.0
        humanize_timing: float = 0.0
        exports_root: str = "exports"
        pattern_bars: int = 1
        song_name_override: Optional[str] = None
        transitions: Any = None

    @dataclass
    class MockConfig:
        version: int = 1
        song: MockSongConfig = field(default_factory=MockSongConfig)
        sections: Dict = field(default_factory=dict)
        arrangement: List = field(default_factory=list)
        engines: Dict[str, Engine] = field(default_factory=dict)
        runtime: Any = None
        raw: Dict = field(default_factory=dict)

    cfg = MockConfig(engines=engines)
    return cfg  # type: ignore


def create_mock_performance_plan() -> PerformancePlan:
    """Create an empty mock PerformancePlan for testing."""
    return PerformancePlan(
        bpm=120.0,
        meter="4/4",
        key="C",
        mode="ionian",
        beats_per_bar=4.0,
        total_beats=32.0,
    )


def test_find_providers_for_requirement():
    """Test finding engines that provide a specific requirement."""
    engines = {
        "drums": create_mock_engine("drums", provides=["groove.cues", "kick_pattern"]),
        "bass": create_mock_engine("bass", provides=["bass_line"]),
        "harmony": create_mock_engine("harmony", provides=["harmony.plan"]),
    }
    cfg = create_mock_config(engines)

    # Test finding providers for existing requirements
    groove_providers = _find_providers_for_requirement(cfg, "groove.cues")
    assert groove_providers == ["drums"]

    harmony_providers = _find_providers_for_requirement(cfg, "harmony.plan")
    assert harmony_providers == ["harmony"]

    # Test finding multiple providers (if same thing is provided by multiple engines)
    engines["drums2"] = create_mock_engine("drums2", provides=["groove.cues"])
    cfg = create_mock_config(engines)
    groove_providers = _find_providers_for_requirement(cfg, "groove.cues")
    assert set(groove_providers) == {"drums", "drums2"}

    # Test no providers for missing requirement
    missing_providers = _find_providers_for_requirement(cfg, "nonexistent.key")
    assert missing_providers == []


def test_validate_engine_dependencies_no_requirements():
    """Engines with no requirements should pass validation."""
    import logging
    logger = logging.getLogger(__name__)

    engine = create_mock_engine("test_engine", requires=[])
    cfg = create_mock_config({"test_engine": engine})
    plan = create_mock_performance_plan()

    # Should not raise
    _validate_engine_dependencies("test_engine", engine, plan, cfg, logger)


def test_validate_engine_dependencies_satisfied_requirements():
    """Engines with satisfied requirements should pass validation."""
    import logging
    logger = logging.getLogger(__name__)

    engine = create_mock_engine("bass", requires=["groove.cues", "harmony.plan"])
    cfg = create_mock_config({"bass": engine})
    plan = create_mock_performance_plan()

    # Add required data to plan
    plan.set("groove.cues", {"kick_beats": [0.0, 1.0, 2.0]})
    plan.set("harmony.plan", {"chords": ["I", "IV", "V"]})

    # Should not raise
    _validate_engine_dependencies("bass", engine, plan, cfg, logger)


def test_validate_engine_dependencies_missing_single_requirement():
    """Engine with missing requirement should raise ConfigError with helpful message."""
    import logging
    logger = logging.getLogger(__name__)

    bass_engine = create_mock_engine("bass", requires=["groove.cues"])
    drums_engine = create_mock_engine("drums", provides=["groove.cues"])
    cfg = create_mock_config({"bass": bass_engine, "drums": drums_engine})
    plan = create_mock_performance_plan()

    # groove.cues is not in plan yet
    try:
        _validate_engine_dependencies("bass", bass_engine, plan, cfg, logger)
        assert False, "Should have raised ConfigError"
    except ConfigError as e:
        error_message = str(e)
        # Verify error message contains key information
        assert "bass" in error_message
        assert "groove.cues" in error_message
        assert "drums" in error_message  # Drums provides this requirement
        assert "unsatisfied dependencies" in error_message.lower()


def test_validate_engine_dependencies_missing_multiple_requirements():
    """Engine with multiple missing requirements should list all in error."""
    import logging
    logger = logging.getLogger(__name__)

    lead_engine = create_mock_engine("lead_gtr", requires=["harmony.plan", "groove.cues"])
    harmony_engine = create_mock_engine("harmony", provides=["harmony.plan"])
    drums_engine = create_mock_engine("drums", provides=["groove.cues"])
    cfg = create_mock_config({
        "lead_gtr": lead_engine,
        "harmony": harmony_engine,
        "drums": drums_engine,
    })
    plan = create_mock_performance_plan()

    # Neither requirement is in plan
    try:
        _validate_engine_dependencies("lead_gtr", lead_engine, plan, cfg, logger)
        assert False, "Should have raised ConfigError"
    except ConfigError as e:
        error_message = str(e)
        # Verify error message contains all missing requirements
        assert "lead_gtr" in error_message
        assert "harmony.plan" in error_message
        assert "groove.cues" in error_message
        assert "harmony" in error_message  # Provider for harmony.plan
        assert "drums" in error_message  # Provider for groove.cues


def test_validate_engine_dependencies_no_known_providers():
    """Error message should indicate when no providers exist for a requirement."""
    import logging
    logger = logging.getLogger(__name__)

    engine = create_mock_engine("test_engine", requires=["unknown.requirement"])
    cfg = create_mock_config({"test_engine": engine})
    plan = create_mock_performance_plan()

    try:
        _validate_engine_dependencies("test_engine", engine, plan, cfg, logger)
        assert False, "Should have raised ConfigError"
    except ConfigError as e:
        error_message = str(e)
        assert "unknown.requirement" in error_message
        assert "no known providers" in error_message.lower()


def test_validate_engine_dependencies_no_performance_plan():
    """Validation should be skipped gracefully when no performance plan is available."""
    import logging
    logger = logging.getLogger(__name__)

    engine = create_mock_engine("test_engine", requires=["some.requirement"])
    cfg = create_mock_config({"test_engine": engine})

    # Should not raise when performance_plan is None
    _validate_engine_dependencies("test_engine", engine, None, cfg, logger)


if __name__ == "__main__":
    # Run all tests
    test_find_providers_for_requirement()
    print("✓ test_find_providers_for_requirement passed")

    test_validate_engine_dependencies_no_requirements()
    print("✓ test_validate_engine_dependencies_no_requirements passed")

    test_validate_engine_dependencies_satisfied_requirements()
    print("✓ test_validate_engine_dependencies_satisfied_requirements passed")

    test_validate_engine_dependencies_missing_single_requirement()
    print("✓ test_validate_engine_dependencies_missing_single_requirement passed")

    test_validate_engine_dependencies_missing_multiple_requirements()
    print("✓ test_validate_engine_dependencies_missing_multiple_requirements passed")

    test_validate_engine_dependencies_no_known_providers()
    print("✓ test_validate_engine_dependencies_no_known_providers passed")

    test_validate_engine_dependencies_no_performance_plan()
    print("✓ test_validate_engine_dependencies_no_performance_plan passed")

    print("\nAll Phase N3 dependency tests passed!")
