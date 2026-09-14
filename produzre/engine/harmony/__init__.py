"""Harmony engine for exporting harmony plans to PerformancePlan (Phase N7).

This engine does not render any audio events. Its sole purpose is to
provide a stable harmony.plan artifact that other engines (bass, rhythm_gtr,
lead_gtr) can consume.

The harmony engine should run early in the priority order to ensure harmony
data is available before melodic/harmonic instruments render.
"""

from typing import Any, Optional
import logging

from ...harmony import build_harmony_plan, HarmonySectionPlan, ChordSlot
from ...model import RootConfig, SectionConfig
from ...melody import harmonic_function


def _serialize_chord_slot(slot: ChordSlot, slot_count: int) -> dict:
    """Serialize a ChordSlot to a plain dictionary.

    Args:
        slot: ChordSlot object to serialize

    Returns:
        Dict with keys: index, numeral, start_beat, end_beat
    """
    return {
        "index": slot.index,
        "numeral": slot.numeral,
        "start_beat": slot.start_beat,
        "end_beat": slot.end_beat,
        "function": harmonic_function(slot.numeral),
        "is_phrase_end": (slot.index + 1) % 4 == 0 or slot.index == slot_count - 1,
        "is_section_cadence": slot.index == slot_count - 1,
    }


def _serialize_harmony_plan(hplan: HarmonySectionPlan) -> dict:
    """Serialize a HarmonySectionPlan to a plain dictionary.

    Args:
        hplan: HarmonySectionPlan object to serialize

    Returns:
        Dict with keys: section_id, meter, total_beats, chord_rate, chord_slots
    """
    return {
        "section_id": hplan.section_id,
        "meter": {
            "numerator": hplan.meter.numerator,
            "denominator": hplan.meter.denominator,
        },
        "total_beats": hplan.total_beats,
        "chord_rate": hplan.chord_rate,
        "chord_slots": [
            _serialize_chord_slot(slot, len(hplan.chord_slots))
            for slot in hplan.chord_slots
        ],
    }


def contribute_plan(*args: Any, **kwargs: Any) -> None:
    """Export harmony.plan to the PerformancePlan (Phase N7).

    This function is called before render_into_timeline to provide harmony
    structure that other engines can consume for melodic/harmonic generation.

    Exports to plan:
        - harmony.plan: Section-level harmony plan with chord slots

    Expected kwargs:
        plan: PerformancePlan object for writing shared data
        section_ctx: Dict with section metadata (cfg, section, etc.)
        rng: random.Random for deterministic generation (unused for harmony)
        logger: logging.Logger for debug output
    """
    if args:
        raise TypeError("harmony.contribute_plan only supports keyword arguments")

    plan = kwargs.get("plan")
    section_ctx = kwargs.get("section_ctx", {})
    logger = kwargs.get("logger")

    if plan is None:
        if logger:
            logger.debug("harmony.contribute_plan: no plan provided, skipping")
        return

    # Extract cfg and section from section_ctx
    cfg: Optional[RootConfig] = section_ctx.get("cfg")
    section: Optional[SectionConfig] = section_ctx.get("section")

    if cfg is None or section is None:
        if logger:
            logger.warning(
                "harmony.contribute_plan: missing cfg or section in section_ctx, skipping"
            )
        return

    # Build harmony plan using existing harmony module
    hplan = build_harmony_plan(cfg, section, logger or logging.getLogger(__name__))

    # If no harmony plan (harmony disabled for section), skip export
    if hplan is None:
        if logger:
            logger.debug(
                f"[HARMONY_PLAN] Section '{section.id}': no harmony defined, skipping export"
            )
        return

    # Serialize harmony plan to plain dict format
    serialized_plan = _serialize_harmony_plan(hplan)

    # Store in PerformancePlan
    plan.set("harmony.plan", serialized_plan)

    if logger:
        logger.debug(
            f"[HARMONY_PLAN] Exported harmony.plan for section '{section.id}': "
            f"{len(hplan.chord_slots)} chord slots, chord_rate={hplan.chord_rate:.2f}, "
            f"total_beats={hplan.total_beats:.2f}"
        )


# This engine has no render function - it only contributes to the plan
def render_into_timeline(*args: Any, **kwargs: Any) -> None:
    """No-op render function for harmony engine.

    The harmony engine does not produce audio events. It only exports
    harmony data via contribute_plan.
    """
    # Intentionally empty - harmony engine only contributes plan data
    pass
