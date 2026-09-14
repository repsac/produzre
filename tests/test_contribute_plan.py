"""Tests for engine contribute_plan hook (Phase N4).

Verifies that:
1. Engines without contribute_plan continue to work (backward compatibility)
2. Engines with contribute_plan have it called before render
3. contribute_plan can write to the performance plan
4. render can read data written by contribute_plan
5. contribute_plan receives correct parameters
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from produzre.config.errors import ConfigError
from produzre.model import Engine, RootConfig
from produzre.orchestrate.plan import PerformancePlan
from produzre.orchestrate.render import render_section_instruments
from produzre.timeline import InstrumentTimeline


@dataclass
class MockRNG:
    """Mock RNG with getstate for make_instrument_rng compatibility."""
    def random(self):
        return 0.5
    def getstate(self):
        return (3, (0,) * 625, None)


def create_mock_engine(
    name: str,
    has_contribute_plan: bool = False,
    requires: Optional[List[str]] = None,
    provides: Optional[List[str]] = None,
    priority: int = 50,
) -> Engine:
    """Create a mock Engine for testing."""

    # Track calls for verification
    calls = []

    def mock_contribute_plan(plan, section_ctx, rng, logger):
        """Mock contribute_plan that writes to the plan."""
        calls.append(("contribute_plan", section_ctx["instrument_name"]))
        # Write some data to the plan
        plan.set(f"{name}.data", {"test": "data from contribute_plan"})

    def mock_render(*args, **kwargs):
        """Mock render that records it was called."""
        calls.append(("render", name))

    engine = Engine(
        name=name,
        module_path=f".engine.{name}",
        priority=priority,
        channel=0,
        program=None,
        render=mock_render,
        contribute_plan=mock_contribute_plan if has_contribute_plan else None,
        enabled=True,
        requires=requires or [],
        provides=provides or [],
        roles=[],
    )

    # Store calls list on engine for verification
    engine._test_calls = calls  # type: ignore

    return engine


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


def create_mock_section(instruments: List[str]):
    """Create a minimal mock section."""
    @dataclass
    class MockSection:
        id: str = "test_section"
        type: str = "verse"
        instruments: Dict[str, Any] = field(default_factory=dict)

    sec = MockSection()
    for inst in instruments:
        sec.instruments[inst] = {}
    return sec


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


def test_engine_without_contribute_plan_works():
    """Engines without contribute_plan should work normally (backward compatibility)."""
    import logging
    logger = logging.getLogger(__name__)

    # Create engine without contribute_plan
    engine = create_mock_engine("test_engine", has_contribute_plan=False)
    cfg = create_mock_config({"test_engine": engine})
    sec = create_mock_section(["test_engine"])
    plan = create_mock_performance_plan()
    timelines = {"test_engine": InstrumentTimeline(instrument="test_engine")}

    # Should not raise
    render_section_instruments(
        cfg=cfg,
        sec=sec,
        hplan=None,
        rgrid=None,
        section_start_beat=0.0,
        section_rng=MockRNG(),
        timelines=timelines,
        performance_plan=plan,
        transition_context=None,
        logger=logger,
    )

    # Verify render was called but contribute_plan was not
    calls = engine._test_calls  # type: ignore
    assert len(calls) == 1, f"Expected 1 call, got {calls}"
    assert calls[0] == ("render", "test_engine")


def test_engine_with_contribute_plan_called_before_render():
    """Engines with contribute_plan should have it called before render."""
    import logging
    logger = logging.getLogger(__name__)

    # Create engine with contribute_plan
    engine = create_mock_engine("test_engine", has_contribute_plan=True)
    cfg = create_mock_config({"test_engine": engine})
    sec = create_mock_section(["test_engine"])
    plan = create_mock_performance_plan()
    timelines = {"test_engine": InstrumentTimeline(instrument="test_engine")}

    render_section_instruments(
        cfg=cfg,
        sec=sec,
        hplan=None,
        rgrid=None,
        section_start_beat=0.0,
        section_rng=MockRNG(),
        timelines=timelines,
        performance_plan=plan,
        transition_context=None,
        logger=logger,
    )

    # Verify both contribute_plan and render were called in correct order
    calls = engine._test_calls  # type: ignore
    assert len(calls) == 2, f"Expected 2 calls, got {calls}"
    assert calls[0] == ("contribute_plan", "test_engine")
    assert calls[1] == ("render", "test_engine")


def test_contribute_plan_can_write_to_performance_plan():
    """contribute_plan should be able to write data to the performance plan."""
    import logging
    logger = logging.getLogger(__name__)

    engine = create_mock_engine("test_engine", has_contribute_plan=True)
    cfg = create_mock_config({"test_engine": engine})
    sec = create_mock_section(["test_engine"])
    plan = create_mock_performance_plan()
    timelines = {"test_engine": InstrumentTimeline(instrument="test_engine")}

    # Plan should be empty initially
    assert not plan.has("test_engine.data")

    render_section_instruments(
        cfg=cfg,
        sec=sec,
        hplan=None,
        rgrid=None,
        section_start_beat=0.0,
        section_rng=MockRNG(),
        timelines=timelines,
        performance_plan=plan,
        transition_context=None,
        logger=logger,
    )

    # Verify data was written to plan
    assert plan.has("test_engine.data")
    data = plan.get("test_engine.data")
    assert data == {"test": "data from contribute_plan"}


def test_multiple_engines_with_contribute_plan_priority_order():
    """Multiple engines with contribute_plan should execute in priority order."""
    import logging
    logger = logging.getLogger(__name__)

    # Create engines with different priorities
    engine1 = create_mock_engine("engine1", has_contribute_plan=True, priority=1)
    engine2 = create_mock_engine("engine2", has_contribute_plan=True, priority=2)
    engine3 = create_mock_engine("engine3", has_contribute_plan=True, priority=3)

    cfg = create_mock_config({
        "engine1": engine1,
        "engine2": engine2,
        "engine3": engine3,
    })
    sec = create_mock_section(["engine1", "engine2", "engine3"])
    plan = create_mock_performance_plan()
    timelines = {
        "engine1": InstrumentTimeline(instrument="engine1"),
        "engine2": InstrumentTimeline(instrument="engine2"),
        "engine3": InstrumentTimeline(instrument="engine3"),
    }

    render_section_instruments(
        cfg=cfg,
        sec=sec,
        hplan=None,
        rgrid=None,
        section_start_beat=0.0,
        section_rng=MockRNG(),
        timelines=timelines,
        performance_plan=plan,
        transition_context=None,
        logger=logger,
    )

    # Verify all contribute_plan calls happened in priority order
    all_calls = []
    all_calls.extend(engine1._test_calls)  # type: ignore
    all_calls.extend(engine2._test_calls)  # type: ignore
    all_calls.extend(engine3._test_calls)  # type: ignore

    # Extract just the contribute_plan calls
    contribute_calls = [c for c in all_calls if c[0] == "contribute_plan"]
    assert len(contribute_calls) == 3
    assert contribute_calls[0] == ("contribute_plan", "engine1")
    assert contribute_calls[1] == ("contribute_plan", "engine2")
    assert contribute_calls[2] == ("contribute_plan", "engine3")

    # Verify data written by all engines
    assert plan.has("engine1.data")
    assert plan.has("engine2.data")
    assert plan.has("engine3.data")


def test_mixed_engines_with_and_without_contribute_plan():
    """Mix of engines with and without contribute_plan should work."""
    import logging
    logger = logging.getLogger(__name__)

    engine1 = create_mock_engine("engine1", has_contribute_plan=False, priority=1)
    engine2 = create_mock_engine("engine2", has_contribute_plan=True, priority=2)
    engine3 = create_mock_engine("engine3", has_contribute_plan=False, priority=3)

    cfg = create_mock_config({
        "engine1": engine1,
        "engine2": engine2,
        "engine3": engine3,
    })
    sec = create_mock_section(["engine1", "engine2", "engine3"])
    plan = create_mock_performance_plan()
    timelines = {
        "engine1": InstrumentTimeline(instrument="engine1"),
        "engine2": InstrumentTimeline(instrument="engine2"),
        "engine3": InstrumentTimeline(instrument="engine3"),
    }

    render_section_instruments(
        cfg=cfg,
        sec=sec,
        hplan=None,
        rgrid=None,
        section_start_beat=0.0,
        section_rng=MockRNG(),
        timelines=timelines,
        performance_plan=plan,
        transition_context=None,
        logger=logger,
    )

    # Verify engine1 (no contribute_plan) had only render called
    calls1 = engine1._test_calls  # type: ignore
    assert len(calls1) == 1
    assert calls1[0] == ("render", "engine1")

    # Verify engine2 (has contribute_plan) had both called
    calls2 = engine2._test_calls  # type: ignore
    assert len(calls2) == 2
    assert calls2[0] == ("contribute_plan", "engine2")
    assert calls2[1] == ("render", "engine2")

    # Verify engine3 (no contribute_plan) had only render called
    calls3 = engine3._test_calls  # type: ignore
    assert len(calls3) == 1
    assert calls3[0] == ("render", "engine3")

    # Verify only engine2 wrote to plan
    assert not plan.has("engine1.data")
    assert plan.has("engine2.data")
    assert not plan.has("engine3.data")


def test_all_planning_hooks_finish_before_first_render():
    """An early-priority render can consume intent from a later planner."""
    import logging

    calls = []

    def early_plan(**kwargs):
        calls.append("early_plan")
        kwargs["plan"].set("early.intent", True)

    def late_plan(**kwargs):
        calls.append("late_plan")
        kwargs["plan"].set("late.intent", True)

    def early_render(**kwargs):
        calls.append("early_render")
        assert kwargs["plan"].get("late.intent") is True

    def late_render(**kwargs):
        calls.append("late_render")

    early = Engine(
        name="early", module_path=".engine.early", priority=1, channel=0,
        program=None, render=early_render, contribute_plan=early_plan,
        enabled=True, requires=[], provides=["early.intent"], roles=[],
    )
    late = Engine(
        name="late", module_path=".engine.late", priority=9, channel=1,
        program=None, render=late_render, contribute_plan=late_plan,
        enabled=True, requires=[], provides=["late.intent"], roles=[],
    )
    cfg = create_mock_config({"early": early, "late": late})
    sec = create_mock_section(["early", "late"])

    render_section_instruments(
        cfg=cfg,
        sec=sec,
        hplan=None,
        rgrid=None,
        section_start_beat=0.0,
        section_rng=MockRNG(),
        timelines={},
        performance_plan=create_mock_performance_plan(),
        transition_context=None,
        logger=logging.getLogger(__name__),
    )

    assert calls == ["early_plan", "late_plan", "early_render", "late_render"]


if __name__ == "__main__":
    # Run all tests
    test_engine_without_contribute_plan_works()
    print("✓ test_engine_without_contribute_plan_works passed")

    test_engine_with_contribute_plan_called_before_render()
    print("✓ test_engine_with_contribute_plan_called_before_render passed")

    test_contribute_plan_can_write_to_performance_plan()
    print("✓ test_contribute_plan_can_write_to_performance_plan passed")

    test_multiple_engines_with_contribute_plan_priority_order()
    print("✓ test_multiple_engines_with_contribute_plan_priority_order passed")

    test_mixed_engines_with_and_without_contribute_plan()
    print("✓ test_mixed_engines_with_and_without_contribute_plan passed")

    print("\nAll Phase N4 contribute_plan tests passed!")
