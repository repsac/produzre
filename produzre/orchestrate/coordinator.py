"""Semantic coordination helpers for engine-to-engine interaction (Sprint 3-4).

This module provides high-level coordination methods that engines can use to
implement the 5 coordination patterns identified in the MIDI analysis:

1. Inverse density: Lead-rhythm inverse relationship
2. Rhythmic pocket alignment: Bass-kick alignment (already in bass engine via lock_to_kick)
3. Fill at transitions: Drum fills at section boundaries
4. Coordinated accents: Ensemble accent sync
5. Solo support: Rhythm simplification during solos

The coordinator wraps the PerformancePlan and provides semantic methods that
engines call during rendering. It reads from plan data (transitions.map, groove cues, etc.)
and returns actionable coordination hints.

Design Philosophy:
- Engines QUERY the coordinator, they don't depend on it
- All coordination is opt-in and probabilistic
- Coordinator is stateless (all state in PerformancePlan)
- Methods return simple types (float, bool, list) not complex objects
"""

from __future__ import annotations

import logging
from typing import List, Optional, Set

from .plan import PerformancePlan

__all__ = ["EngineCoordinator"]


class EngineCoordinator:
    """High-level coordination interface for engines (Sprint 3-4).

    Provides semantic methods that engines can call during rendering to
    coordinate with other engines based on learned patterns from MIDI analysis.

    All coordination is advisory and probabilistic - engines can ignore hints
    if they conflict with other constraints.

    Attributes:
        plan: PerformancePlan with shared state.
        logger: Optional logger for debug output.
    """

    def __init__(self, plan: PerformancePlan, logger: Optional[logging.Logger] = None):
        """Initialize coordinator with a PerformancePlan.

        Args:
            plan: PerformancePlan object containing shared state.
            logger: Optional logger for debug output.
        """
        self.plan = plan
        self.logger = logger or logging.getLogger(__name__)

    # =========================================================================
    # Rule 1: Inverse Density (Lead-Rhythm Coordination)
    # =========================================================================

    def get_rhythm_intensity_adjustment(self, section_id: str, lead_rest_threshold: float = 0.2) -> float:
        """Get rhythm intensity adjustment based on lead activity (Rule 1).

        Implements inverse density rule: When lead rests, rhythm should fill.
        When lead is busy, rhythm should pull back.

        MIDI analysis showed lead-rhythm inverse relationship with:
        - Lead rest > 20%: Rhythm boosts intensity by ~30%
        - Lead rest < 20%: Rhythm reduces intensity by ~30%

        Args:
            section_id: Section identifier.
            lead_rest_threshold: Rest ratio threshold (default 0.2 = 20%).

        Returns:
            float: Intensity multiplier for rhythm (0.7 = reduce 30%, 1.3 = boost 30%).
        """
        # Check if lead has provided feedback about rest ratio
        lead_rest_key = f"lead_rest_ratio.{section_id}"
        lead_rest_ratio = self.plan.get(lead_rest_key)

        if lead_rest_ratio is None:
            # No lead feedback available, return neutral
            return 1.0

        lead_rest = float(lead_rest_ratio)

        # Use a restrained continuous relationship. Extreme 30% jumps made
        # accompaniment change density more than role and caused choruses with
        # modest lead rests to become busier, not clearer.
        if lead_rest >= 0.55:
            adjustment = 1.12
            self.logger.debug(
                f"[COORDINATION] Lead rest {lead_rest:.2f} is spacious "
                f"in '{section_id}': rhythm boost {adjustment:.2f}x"
            )
        elif lead_rest <= 0.25:
            adjustment = 0.82
            self.logger.debug(
                f"[COORDINATION] Lead rest {lead_rest:.2f} is active "
                f"in '{section_id}': rhythm reduce {adjustment:.2f}x"
            )
        else:
            # Interpolate 0.82..1.12 across the useful middle range.
            adjustment = 0.82 + ((lead_rest - 0.25) / 0.30) * 0.30

        return adjustment

    def get_instrument_role(self, section_id: str, instrument: str) -> str:
        """Return the section-level role assigned to an instrument."""
        section_plan = self.plan.get(f"ensemble.{section_id}", {})
        return str(section_plan.get("roles", {}).get(instrument, {}).get("role", ""))

    def get_density_multiplier(self, section_id: str, instrument: str) -> float:
        """Return the density budget assigned by the ensemble planner."""
        section_plan = self.plan.get(f"ensemble.{section_id}", {})
        value = section_plan.get("roles", {}).get(instrument, {}).get("density_multiplier", 1.0)
        try:
            return max(0.0, min(1.25, float(value)))
        except (TypeError, ValueError):
            return 1.0

    def get_lead_activity_windows(self, section_id: str) -> List[tuple[float, float]]:
        """Return section-local windows where lead guitar owns foreground space."""
        section_plan = self.plan.get(f"ensemble.{section_id}", {})
        windows = section_plan.get("lead_activity_windows", [])
        return [(float(start), float(end)) for start, end in windows]

    def get_fill_owner(self, section_id: str) -> Optional[str]:
        """Return the instrument assigned to play the section transition fill."""
        section_plan = self.plan.get(f"ensemble.{section_id}", {})
        owner = section_plan.get("fill_owner")
        return str(owner) if owner else None

    # =========================================================================
    # Rule 2: Rhythmic Pocket Alignment (Bass-Kick)
    # =========================================================================

    def get_kick_alignment_beats(self, section_id: str) -> List[float]:
        """Get kick beats for bass alignment (Rule 2).

        Returns kick beats from drums for bass to align with. Bass engine
        already supports lock_to_kick parameter, this provides the beat list.

        MIDI analysis showed 60% probability of bass-kick alignment on strong beats.

        Args:
            section_id: Section identifier.

        Returns:
            List[float]: List of kick beat positions in the section.
        """
        # Check if drums have contributed kick beats to the plan
        kick_beats_key = f"groove.kick_beats.{section_id}"
        kick_beats = self.plan.get(kick_beats_key)

        if kick_beats is None:
            return []

        # Return as list of floats
        if isinstance(kick_beats, (list, tuple, set)):
            beats = sorted(float(b) for b in kick_beats)
            self.logger.debug(
                f"[COORDINATION] Found {len(beats)} kick beats for '{section_id}'"
            )
            return beats

        return []

    # =========================================================================
    # Rule 3: Fill at Transitions (Drum Fills at Section Boundaries)
    # =========================================================================

    def is_section_boundary(self, bar_idx: int, section_id: str, lead_in_bars: int = 1) -> bool:
        """Check if current bar is near a section boundary (Rule 3).

        Used by drums engine to trigger fills before section transitions.
        MIDI analysis showed 80% probability of fills at section boundaries.

        Args:
            bar_idx: Current bar index (0-based within section).
            section_id: Current section identifier.
            lead_in_bars: Number of bars before transition to consider as boundary (default 1).

        Returns:
            bool: True if this bar is within lead_in_bars of section end.
        """
        # Get section metadata
        section_meta = self.plan.get_section(section_id)
        if section_meta is None:
            return False

        # Get transition directive
        transitions_map = self.plan.get("transitions.map")
        if transitions_map is None:
            return False

        transition = transitions_map.get(section_id)
        if transition is None:
            return False

        # Check if this is the last section (no transition out)
        is_last = transition.get("is_last_section", False)
        if is_last:
            # Still trigger fill at song end
            pass

        # Calculate section length in bars
        section_beats = section_meta.length_beats
        beats_per_bar = section_meta.beats_per_bar
        section_bars = int(section_beats / beats_per_bar)

        # Check if current bar is within lead_in_bars of section end
        bars_from_end = section_bars - bar_idx - 1
        is_boundary = bars_from_end < lead_in_bars

        if is_boundary:
            self.logger.debug(
                f"[COORDINATION] Bar {bar_idx} in '{section_id}' is section boundary "
                f"({bars_from_end} bars from end, lead_in={lead_in_bars})"
            )

        return is_boundary

    def get_fill_probability_for_transition(self, section_id: str) -> float:
        """Get fill probability based on transition type (Rule 3).

        Returns higher probability for major transitions (verse→chorus, bridge→chorus).

        Args:
            section_id: Current section identifier.

        Returns:
            float: Fill probability (0.0-1.0). Default 0.8 for section boundaries.
        """
        transitions_map = self.plan.get("transitions.map")
        if transitions_map is None:
            return 0.8  # Default high probability

        transition = transitions_map.get(section_id)
        if transition is None:
            return 0.8

        # Check turnaround hint
        turnaround_hint = transition.get("turnaround_hint", "none")

        if turnaround_hint == "heavy":
            return 1.0  # Always fill for heavy transitions
        elif turnaround_hint == "light":
            return 0.6  # Moderate fill for light transitions
        else:
            return 0.8  # Default for section boundaries

    # =========================================================================
    # Rule 4: Coordinated Accents (Ensemble Accent Sync)
    # =========================================================================

    def get_accent_beats(self, section_id: str) -> Set[float]:
        """Get accent beats for ensemble coordination (Rule 4).

        Returns beat positions where drums have strong accents (kicks+snare, crashes).
        Other instruments can align accents with drums for cohesion.

        Args:
            section_id: Section identifier.

        Returns:
            Set[float]: Set of accent beat positions.
        """
        # Check if drums have contributed accent beats
        accent_beats_key = f"groove.accent_beats.{section_id}"
        accent_beats = self.plan.get(accent_beats_key)

        if accent_beats is None:
            return set()

        if isinstance(accent_beats, (list, tuple, set)):
            beats = set(float(b) for b in accent_beats)
            self.logger.debug(
                f"[COORDINATION] Found {len(beats)} accent beats for '{section_id}'"
            )
            return beats

        return set()

    # =========================================================================
    # Rule 5: Solo Support (Rhythm Simplification During Solos)
    # =========================================================================

    def is_solo_section(self, section_id: str) -> bool:
        """Check if current section is a solo (Rule 5).

        Used by rhythm instruments to simplify during lead solos.

        Args:
            section_id: Section identifier.

        Returns:
            bool: True if section type is 'solo'.
        """
        section_meta = self.plan.get_section(section_id)
        if section_meta is None:
            return False

        is_solo = section_meta.type.lower() in ("solo", "lead")

        if is_solo:
            self.logger.debug(f"[COORDINATION] Section '{section_id}' is a solo section")

        return is_solo

    def get_rhythm_simplification_factor(self, section_id: str) -> float:
        """Get rhythm simplification factor for solo sections (Rule 5).

        Returns density multiplier for rhythm instruments during solos.
        Rhythm should play simpler patterns to support lead without competing.

        Args:
            section_id: Section identifier.

        Returns:
            float: Density multiplier (0.6 = reduce density 40% during solo).
        """
        if self.is_solo_section(section_id):
            return 0.6  # Reduce rhythm density by 40% during solos
        return 1.0  # No change for non-solo sections

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_section_transition(self, section_id: str) -> Optional[dict]:
        """Get transition directive for a section.

        Args:
            section_id: Section identifier.

        Returns:
            Optional[dict]: Transition directive dict, or None if not found.
        """
        transitions_map = self.plan.get("transitions.map")
        if transitions_map is None:
            return None
        return transitions_map.get(section_id)
