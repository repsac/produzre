from __future__ import annotations

"""Core data models for Produzre.

This module defines the primary dataclasses that represent:

- Author-authored configuration loaded from song YAML (song/sections/arrangement)
- The engine registry (instrument engines resolved from `config/engines.yml` plus
  project-level overrides)
- Runtime-only context derived from local per-user state (projects registry)

These models are intentionally lightweight, mostly-serializable, and designed to
be shared across CLI, orchestration, export, and engine modules.

Time conventions:
- Musical time is expressed internally in quarter-note beats.
- Section lengths may be specified in beats or bars (converted using beats-per-bar).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union


@dataclass
class Engine:
    """Descriptor for a loaded instrument engine.

    Produzre treats engines as *functional* modules that share a common
    interface:

      - module-level constants describing defaults (priority/channel/program)
      - a single entry point `render_into_timeline(...)`
      - an optional entry point `contribute_plan(...)` (Phase N4)

    The config loader resolves an engine module path (from `config/engines.yml`
    and optional project YAML overrides), imports it, reads its defaults, and
    stores the callable render function on this dataclass.

    Attributes:
        name: Logical instrument name (e.g., "drums", "bass", "rhythm_gtr").
        module_path: Python import path for the engine module.
        priority: Engine execution order. Lower values render earlier.
        channel: Default MIDI channel (0-15) used by the engine.
        program: Optional General MIDI program number for program_change.
        render: Callable bound to the imported module's `render_into_timeline`.
        contribute_plan: Optional callable bound to `contribute_plan` if present (Phase N4).
        enabled: Whether this engine is enabled (default: True).
        requires: List of feature/slot names this engine depends on (e.g., ["drums", "harmony"]).
        provides: List of feature/slot names this engine exports (e.g., ["kick_pattern", "groove"]).
        roles: List of musical roles this engine can fulfill (e.g., ["rhythm", "lead"]).

    Notes:
        Engines should be designed so that identical inputs produce identical
        outputs when provided the same effective seed.
    """
    name: str
    module_path: str
    priority: int
    channel: int
    program: Optional[int]
    render: Callable[..., None]
    contribute_plan: Optional[Callable[..., None]] = None
    enabled: bool = True
    requires: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)


@dataclass
class RhythmIntent:
    """Rhythmic guidance from orchestrator to instrument engines (Phase B11).

    This structure allows the orchestrator to suggest rhythmic emphasis points
    and constraints without fully dictating the instrument's behavior.

    Attributes:
        accent_beats: Set of beat positions (section-local) that should be
            emphasized. Engines are free to interpret this as velocity boosts,
            note placement, or other emphasis techniques.
        space_budget: Optional density constraint (0.0-1.0+). When provided,
            engines should reduce their density to this level or below.
            - None means no constraint (default behavior)
            - 0.5 means reduce density to 50% or less
            - 1.0 means use full density
        fill_windows: Optional list of (start_beat, end_beat) tuples indicating
            when fills are appropriate or should be avoided.
        extra: Extension map for future orchestration hints.
    """
    accent_beats: set[float] = field(default_factory=set)
    space_budget: Optional[float] = None
    fill_windows: List[tuple[float, float]] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstrumentNegotiationFeatures:
    """Features exported by an instrument for orchestration (Phase B11).

    Instruments export these features after rendering to help the orchestrator
    understand what they played and coordinate with other instruments.

    Attributes:
        onset_map: Dictionary mapping beat positions to note count at that beat.
            Useful for understanding rhythmic density and collision detection.
        accent_map: Dictionary mapping beat positions to accent strength (0.0-1.0+).
            Indicates which notes were emphasized.
        fill_windows_used: List of (start_beat, end_beat) tuples showing when
            fills were played. Helps avoid fill collisions between instruments.
        register_profile: Dictionary containing pitch range information:
            - min_pitch: Lowest MIDI pitch used
            - max_pitch: Highest MIDI pitch used
            - avg_pitch: Average MIDI pitch
            - pitch_range: max - min
        event_count: Total number of notes rendered.
        extra: Extension map for future negotiation features.
    """
    onset_map: Dict[float, int] = field(default_factory=dict)
    accent_map: Dict[float, float] = field(default_factory=dict)
    fill_windows_used: List[tuple[float, float]] = field(default_factory=list)
    register_profile: Dict[str, Any] = field(default_factory=dict)
    event_count: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HarmonyConfig:
    """Harmony configuration for a section.

    Harmony is represented as Roman numeral progressions relative to the
    section's key/mode. Planning code converts this configuration into a
    section-scoped harmony plan consisting of timed chord slots.

    Attributes:
        progression: Space-separated Roman numeral tokens (e.g., "i bVII VI i")
            OR a list of Roman numeral strings (e.g., ["I", "IV", "V", "I"]).
            Both formats are supported for user convenience.
        chord_rate: Harmonic rhythm in beats per chord. For example:
            - 4.0 means one chord per bar in 4/4
            - 2.0 means two chords per bar in 4/4
        extra: Free-form extension map for future harmony features.
    """
    progression: Union[str, List[str]]
    chord_rate: float = 4.0  # beats per chord by default
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstrumentConfig:
    """Per-section configuration for a single instrument.

    A section may declare multiple instruments under `SectionConfig.instruments`.
    Each instrument receives its own config block which engines can interpret.

    Produzre intentionally keeps this model broad:
    - Some fields are generic and expected to work across many engines.
    - Others are hints that only certain engines may use.
    - `extra` exists to hold engine-specific keys without breaking parsing.

    Common fields:
        enabled: Optional mute/enable flag for this instrument in this section.
            - None means "enabled unless the instrument is omitted from section".
        intensity: 0.0..1.0+ scalar controlling density/velocity/complexity.
        style_bias: Engine-specific scalar used to bias stylistic choices.
        offset_beats: Beat offset applied to events in this section.
        seed: Optional instrument-specific seed override.
        variation: Optional instrument-specific variation override.
        groove: Optional groove preset override (engine-defined strings).
        recipe: Optional explicit recipe name. Overrides auto-selection from
            genre/section-type scoring. See produzre/config/recipes.py.

    Voicing/register/role fields:
        voicing: Hint for chord voicings (e.g., "open", "close").
        register: Hint for range selection (e.g., "low", "mid", "high").
        role: Hint for instrument role (e.g., "rhythm", "lead", "pad", "arp").

    Export/behavior flags:
        patterns: Optional per-instrument request to extract patterns.
        solo: Optional per-section flag indicating a featured/solo passage.

    Humanization overrides:
        humanize_velocity: Optional override for velocity variation.
        humanize_timing: Optional override for micro-timing variation.

    Genre override:
        genre: Optional genre string that overrides song.genre for this
            instrument's recipe auto-selection. Enables genre mashups where
            different instruments use different genre recipe pools.
            Fallback: instrument genre -> song.genre -> None.

    Engine extensions:
        extra: Arbitrary key/value overrides for engine-specific behavior
            (e.g., "chug", "slap", swing feel, articulations).
    """
    enabled: Optional[bool] = None
    intensity: float = 1.0
    style_bias: float = 0.0
    offset_beats: float = 0.0
    seed: Optional[int] = None
    variation: Optional[float] = None
    groove: Optional[str] = None
    recipe: Optional[str] = None    # Explicit recipe name (overrides auto-selection)
    genre: Optional[str] = None     # Per-instrument genre override (fallback: song.genre)

    # Voicing & register
    voicing: Optional[str] = None       # e.g., "root_octave", "open", "close"
    register: Optional[str] = None      # e.g., "low", "mid", "high"

    # Role & behavior
    role: Optional[str] = None          # e.g., "rhythm", "lead", "pad", "arp"
    patterns: Optional[bool] = None     # whether to export patterns
    solo: Optional[bool] = None         # treat as solo feature in this section

    # Humanization overrides
    humanize_velocity: Optional[float] = None
    humanize_timing: Optional[float] = None

    # Transition settings override (per-instrument)
    transitions: Optional[TransitionSettings] = None

    # Catch-all for engine-specific options (e.g., "chug", "slap", etc.)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SectionConfig:
    """A logical song section (verse, chorus, bridge, etc.).

    Sections are referenced by ID from `RootConfig.arrangement`.

    Length:
        A section can be defined by either:
        - `beats`: explicit duration in beats, or
        - `bars`: number of bars (converted using the song's beats-per-bar)

    Local overrides:
        Sections may override global song settings such as meter/key/mode.

    Harmony:
        Harmony may be provided via `harmony` (preferred) or `progression`
        (legacy convenience string).

    Instruments:
        Instruments are declared as a mapping of instrument name ->
        `InstrumentConfig`.

    Attributes:
        id: Section identifier (must match its key in the sections mapping).
        type: Section type label used for presets (e.g., "verse", "chorus").
        bars: Optional length in bars.
        beats: Optional length in beats.
        meter: Optional local meter override (e.g., "7/8").
        key: Optional local key override (e.g., "E").
        mode: Optional local mode override (e.g., "dorian").
        seed: Optional section-specific seed override. When set, this section
            uses its own RNG seed instead of deriving from the song seed.
            Useful for re-rolling a single section while keeping others fixed.
        variation: Optional section-specific variation scalar (0.0..1.0+).
            Overrides song.variation for this section only.
        harmony: Optional structured harmony configuration.
        progression: Optional legacy progression string.
        instruments: Per-instrument configs active in this section.
        extras: Misc. section flags and engine hints.
    """
    id: str
    type: str
    bars: Optional[int] = None
    beats: Optional[float] = None

    # Local overrides
    meter: Optional[str] = None  # e.g. "7/8"
    key: Optional[str] = None
    mode: Optional[str] = None

    # Seed & variation overrides
    seed: Optional[int] = None       # Override song seed for this section
    variation: Optional[float] = None  # Override song.variation for this section

    harmony: Optional[HarmonyConfig] = None
    progression: Optional[str] = None   # e.g. "i bVII VI i"

    # Instruments defined in this section
    instruments: Dict[str, InstrumentConfig] = field(default_factory=dict)

    # Intent: bridge/break contrast patterns (Phase 15)
    # Values: "drop", "half_time", "build", "stomp", "open", or None
    intent: Optional[str] = None

    # Solo/lead section flag (Phase B10)
    solo: Optional[bool] = None  # True if this is a solo/featured section
    role: Optional[str] = None   # "lead" or other role for this section

    # Additional, section-specific flags (e.g., "lead_spot", etc.)
    extras: Dict[str, Any] = field(default_factory=dict)

    def total_beats(self, global_beats_per_bar: int) -> float:
        """Return the section duration in beats.

        Priority order:
          1) If `beats` is provided, it is used directly.
          2) Else if `bars` is provided, beats are computed as:
             `bars * global_beats_per_bar`.
          3) Otherwise, the section is treated as length 0.

        Args:
            global_beats_per_bar: Beats-per-bar (quarter-note beat units) used
                when converting `bars` to beats.

        Returns:
            float: Total section length in quarter-note beats.
        """
        if self.beats is not None:
            return float(self.beats)
        if self.bars is not None:
            return float(self.bars * global_beats_per_bar)
        # No explicit length; treat as empty.
        return 0.0


@dataclass
class TransitionSettings:
    """Configuration for transition-aware arranging features.

    These settings control how the arrangement engine handles transitions
    between sections, including pickups, turnarounds, ramps, and bridge
    introductions.

    Attributes:
        enabled: Master switch for transition features (default: True).
        strength: Overall transition intensity scalar (0.0-1.0, default: 0.5).
            Controls how prominent transition features are.
        ramp_bars: Number of bars for energy ramps between sections (0-2, default: 1).
            Used for crescendo/decrescendo effects.
        pickup_rate: Probability of generating pickup phrases before sections (0.0-1.0, default: 0.35).
        turnaround_rate: Probability of turnaround phrases at section endings (0.0-1.0, default: 0.25).
        bridge_start_bars: Number of bars for bridge introduction effects (0-2, default: 1).
        debug: Enable debug logging for transition features (default: False).
    """
    enabled: bool = True
    strength: float = 0.5
    ramp_bars: int = 1
    pickup_rate: float = 0.35
    turnaround_rate: float = 0.25
    bridge_start_bars: int = 1
    debug: bool = False


@dataclass
class SongConfig:
    """Global song configuration.

    This structure holds defaults that apply to the entire song unless
    overridden at the section or instrument levels.

    Attributes:
        title: User-facing song title; also used as the default export prefix.
        bpm: Tempo in beats per minute.
        key: Global key (e.g., "C", "E").
        mode: Global mode (e.g., "ionian", "dorian").
        meter: Global meter in "N/D" form (e.g., "4/4").
        project: Optional project name to resolve a local project seed.
        beats_per_bar: Beats-per-bar used when converting `SectionConfig.bars`
            to beats. (Quarter-note beat units.)

        seed: User-controlled integer seed used for exploration.
        take: Optional take number (0..N) for controlled micro-variation.
            Different takes produce different outputs while remaining reproducible.
            Same YAML + same take = same output.
        variation: 0.0..1.0+ scalar that biases randomness and style.

        humanize_velocity: Global velocity humanization scalar.
        humanize_timing: Global timing humanization scalar.

        exports_root: Root exports directory (string path; may be relative).

        pattern_bars: Pattern window length in bars used by pattern extraction.

        song_name_override: Optional runtime-only override for naming outputs.
            This is typically set by the CLI `--song-name` flag.
    """
    title: str = "produzre"
    bpm: float = 120.0
    key: str = "C"
    mode: str = "ionian"
    meter: str = "4/4"
    genre: Optional[str] = None     # Hints groove recipe auto-selection
    project: Optional[str] = None
    beats_per_bar: int = 4

    seed: int = 0
    take: int = 0  # Optional take number for controlled micro-variation (0..N)
    variation: float = 0.0

    humanize_velocity: float = 0.0
    humanize_timing: float = 0.0

    exports_root: str = "exports"
    pattern_bars: int = 1  # number of bars per pattern window

    # Transition-aware arranging settings
    transitions: TransitionSettings = field(default_factory=TransitionSettings)

    # Derived / optional runtime-only name for files (can differ from title)
    song_name_override: Optional[str] = None


@dataclass
class RuntimeContext:
    """Runtime-only context resolved at config-load time.

    This context is derived from:
      - authored song YAML (`song.project`, `song.seed`), and
      - local per-user state (projects registry under the user's config dir).

    It enables a collaboration-friendly workflow:
      - users can share the same song YAML while still having unique project
        seeds by default;
      - users can import/export projects to synchronize seeds when desired.

    Attributes:
        project_name: Resolved project name (from song.project or default).
        project_seed: Local per-user seed for the project.
        song_seed: Authored seed from the song configuration.
        effective_seed: Combined seed used for deterministic generation.
        projects_registry_path: Filesystem path to the local projects registry.
    """
    project_name: str
    project_seed: int
    song_seed: int
    effective_seed: int
    projects_registry_path: str


@dataclass
class RootConfig:
    """Top-level configuration loaded from YAML.

    This is the object passed through the entire pipeline:
      - CLI config loading
      - planning/orchestration
      - engine rendering
      - export

    Attributes:
        version: Configuration schema version.
        song: Global song configuration.
        sections: Mapping of section id -> `SectionConfig`.
        arrangement: Ordered list of section ids.
        engines: Engine registry mapping instrument name -> `Engine`.
        runtime: Optional runtime-only context resolved during config load.
        raw: Raw parsed YAML mapping retained for debugging/show-config.
    """
    version: int
    song: SongConfig
    sections: Dict[str, SectionConfig]
    arrangement: List[str]
    engines: Dict[str, Engine]
    runtime: Optional[RuntimeContext] = None

    raw: Dict[str, Any] = field(default_factory=dict)  # keep raw YAML for debug

    def get_effective_song_name(self) -> str:
        """Return the effective song name used for filenames and export folders.

        Resolution order:
          1) `song.song_name_override` (typically set by CLI)
          2) `song.title`
          3) Fallback: "produzre"

        Returns:
            str: The effective (possibly unsanitized) song name.
        """
        if self.song.song_name_override:
            return self.song.song_name_override
        if self.song.title:
            return self.song.title
        return "produzre"
