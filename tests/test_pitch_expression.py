"""Tests for the pitch-expression layer (vibrato + bend-in) and the
transition channel fixes.

The expression layer tags NoteEvents with an `expression` spec in the lead
engine (seeded draws) and renders pitchwheel messages in the MIDI writer.
These tests pin the writer contract and the end-to-end channel behavior so
the feature cannot silently regress.
"""

import mido
import pytest

from produzre.timeline import InstrumentTimeline


def _write(tl):
    from produzre.export.midi import write_timeline_to_track

    track = mido.MidiTrack()
    write_timeline_to_track(track, tl)
    return track


def _abs_msgs(track):
    """Flatten a track into (abs_tick, msg) pairs."""
    out = []
    t = 0
    for msg in track:
        t += msg.time
        out.append((t, msg))
    return out


def test_vibrato_renders_pitchwheel_on_note_channel():
    tl = InstrumentTimeline(instrument="lead_gtr")
    tl.add_note(
        start_beat=0.0,
        duration_beats=2.0,
        pitch=64,
        velocity=100,
        channel=3,
        expression={
            "vibrato": {"depth_cents": 30.0, "period_beats": 0.25, "delay_beats": 0.25}
        },
    )
    msgs = _abs_msgs(_write(tl))

    pw = [(t, m) for t, m in msgs if m.type == "pitchwheel"]
    assert pw, "expected pitchwheel messages for a vibrato note"
    assert all(m.channel == 3 for _, m in pw), "wheel must ride the note's channel"

    # No wheel movement before the delay (0.25 beats = 120 ticks at PPQ 480).
    assert all(t >= 120 for t, _ in pw)

    # Real wobble: both positive and negative values after the delay.
    vals = [m.pitch for _, m in pw]
    assert any(v > 0 for v in vals) and any(v < 0 for v in vals)

    # Wheel returns to center at the note's end tick (2.0 beats = 960 ticks).
    end_pw = [m.pitch for t, m in pw if t == 960]
    assert end_pw and end_pw[-1] == 0, "wheel must reset to 0 at note end"

    # Note itself is untouched.
    ons = [m for _, m in msgs if m.type == "note_on"]
    assert len(ons) == 1 and ons[0].note == 64 and ons[0].channel == 3


def test_bend_in_ramps_from_negative_to_zero():
    tl = InstrumentTimeline(instrument="lead_gtr")
    tl.add_note(
        start_beat=1.0,
        duration_beats=1.0,
        pitch=64,
        velocity=100,
        channel=3,
        expression={"bend_in": {"semitones": 2, "ramp_beats": 0.2}},
    )
    msgs = _abs_msgs(_write(tl))
    pw = [(t, m) for t, m in msgs if m.type == "pitchwheel"]
    assert pw, "expected pitchwheel messages for a bend-in note"

    start_tick = 480
    ramp_end = start_tick + int(round(0.2 * 480))  # 576

    # First wheel message is at the note start, bent fully down (GM +-2
    # semitones => 2 semitones down is -8191).
    first_t, first_m = pw[0]
    assert first_t == start_tick
    assert first_m.pitch == -8191

    # Ramp rises monotonically and reaches center exactly at the ramp end.
    ramp = [(t, m.pitch) for t, m in pw if t <= ramp_end]
    assert ramp[-1] == (ramp_end, 0)
    vals = [v for _, v in ramp]
    assert vals == sorted(vals), "bend-in ramp must rise monotonically"

    # Wheel precedes the note_on at the start tick.
    at_start = [m for t, m in msgs if t == start_tick]
    assert at_start[0].type == "pitchwheel"
    assert any(m.type == "note_on" for m in at_start)


def test_no_expression_no_pitchwheel():
    tl = InstrumentTimeline(instrument="lead_gtr")
    tl.add_note(start_beat=0.0, duration_beats=1.0, pitch=64, velocity=100, channel=3)
    track = _write(tl)
    assert not [m for m in track if m.type == "pitchwheel"]


def test_expression_writer_is_deterministic():
    def make():
        tl = InstrumentTimeline(instrument="lead_gtr")
        tl.add_note(
            start_beat=0.0,
            duration_beats=2.0,
            pitch=64,
            velocity=100,
            channel=3,
            expression={
                "bend_in": {"semitones": 1, "ramp_beats": 0.15},
                "vibrato": {"depth_cents": 40.0, "period_beats": 0.22, "delay_beats": 0.3},
            },
        )
        return _write(tl)

    a, b = make(), make()
    assert [bytes(m.bin()) for m in a] == [bytes(m.bin()) for m in b]


def test_expression_span_follows_overlap_truncation():
    """When a later same-pitch note truncates the first, the vibrato must stop
    at the truncated end, not the original one."""
    tl = InstrumentTimeline(instrument="lead_gtr")
    tl.add_note(
        start_beat=0.0,
        duration_beats=2.0,
        pitch=64,
        velocity=100,
        channel=3,
        expression={
            "vibrato": {"depth_cents": 30.0, "period_beats": 0.25, "delay_beats": 0.1}
        },
    )
    tl.add_note(start_beat=1.0, duration_beats=1.0, pitch=64, velocity=90, channel=3)

    msgs = _abs_msgs(_write(tl))
    pw = [(t, m) for t, m in msgs if m.type == "pitchwheel"]
    assert pw
    # First note is truncated to tick 480; no wheel move may pass it, and the
    # reset to 0 lands there.
    assert all(t <= 480 for t, _ in pw)
    assert [m.pitch for t, m in pw if t == 480][-1] == 0


def test_expression_never_leaks_to_drum_channel():
    """Expression-tagged lead notes must not put wheel messages on ch 9."""
    tl = InstrumentTimeline(instrument="lead_gtr")
    tl.add_note(
        start_beat=0.0,
        duration_beats=2.0,
        pitch=64,
        velocity=100,
        channel=3,
        expression={
            "bend_in": {"semitones": 2, "ramp_beats": 0.2},
            "vibrato": {"depth_cents": 45.0, "period_beats": 0.2, "delay_beats": 0.2},
        },
    )
    track = _write(tl)
    assert not [m for m in track if m.type == "pitchwheel" and m.channel == 9]


def test_newer_expression_window_wins_the_wheel():
    """Pitchwheel is channel-wide: when two expression-tagged notes overlap on
    one channel (e.g. a sustained chord ringing into the next strum), the
    older window must stop at the newer note's start instead of fighting."""
    tl = InstrumentTimeline(instrument="rhythm_gtr")
    tl.add_note(
        start_beat=0.0,
        duration_beats=4.0,
        pitch=52,
        velocity=90,
        channel=2,
        expression={
            "vibrato": {"depth_cents": 25.0, "period_beats": 0.25, "delay_beats": 0.2}
        },
    )
    tl.add_note(
        start_beat=2.0,
        duration_beats=2.0,
        pitch=55,
        velocity=90,
        channel=2,
        expression={
            "vibrato": {"depth_cents": 25.0, "period_beats": 0.25, "delay_beats": 0.2}
        },
    )
    msgs = _abs_msgs(_write(tl))
    pw = [(t, m) for t, m in msgs if m.type == "pitchwheel"]

    # First window's samples stop at tick 960 (second note's start) even
    # though its note sustains to tick 1920, and the wheel is re-centered
    # there before the second window begins.
    first = [(t, m.pitch) for t, m in pw if t < 960]
    assert first, "first vibrato window should render before truncation"
    resets = [m.pitch for t, m in pw if t == 960]
    assert resets and resets[0] == 0, "wheel must re-center where the newer window begins"
    second = [(t, m.pitch) for t, m in pw if 960 < t < 1920]
    assert second, "second vibrato window should render after the handoff"


# ---------------------------------------------------------------------------
# Integration: the demo song renders wheel data only on the lead channel, and
# transition material (pickups/turnarounds) stays off the piano channel (0).
# ---------------------------------------------------------------------------

def test_demo_build_expression_and_channels(tmp_path):
    import subprocess
    import sys

    from tests.conftest import REPO_ROOT

    result = subprocess.run(
        [sys.executable, "-m", "produzre.cli", "build", "examples/lead_metal_demo.yaml"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    export_root = None
    for line in result.stderr.splitlines():
        if "Export root:" in line:
            export_root = REPO_ROOT / line.split("Export root:")[1].strip()
    assert export_root is not None, f"No export root in:\n{result.stderr}"

    mid = mido.MidiFile(str(export_root / "Flying_High.mid"))
    pw_channels = set()
    note_channels = set()
    cc_channels = set()
    pc_channels = set()
    for tr in mid.tracks:
        for m in tr:
            if m.type == "pitchwheel":
                pw_channels.add(m.channel)
            elif m.type == "note_on" and m.velocity > 0:
                note_channels.add(m.channel)
            elif m.type == "control_change":
                cc_channels.add(m.channel)
            elif m.type == "program_change":
                pc_channels.add(m.channel)

    # Lead vibrato/bend-ins (3), bass slide-ins (1), rhythm chord vibrato (2);
    # seed 23 deterministically lights up all three.
    assert pw_channels == {1, 2, 3}, f"pitchwheel on bass/rhythm/lead, got {pw_channels}"
    assert 9 not in pw_channels, "drums must never get pitch expression"
    assert 0 not in note_channels, "no notes may leak onto the piano channel"
    # Solo-section dive bombs widen the lead channel's bend range via RPN.
    assert cc_channels == {3}, f"RPN bend-range messages only on lead, got {cc_channels}"
    # Drum channel carries an explicit Standard Kit program (FL Studio import).
    assert 9 in pc_channels, "drum channel must carry a program change"

    # Feedback swells ride CC11 on the lead channel (seed 23 fires two).
    cc11 = [
        m for tr in mid.tracks for m in tr
        if m.type == "control_change" and m.control == 11
    ]
    assert cc11 and all(m.channel == 3 for m in cc11)

    # Ring-out: the lead line sustains into rests — the longest lead note
    # exceeds the old 2.0-beat cap that grid cells imposed.
    tsv = export_root / "analysis" / "lead_gtr" / "Flying_High_lead_gtr.events.tsv"
    lines = tsv.read_text().strip().split("\n")[1:]
    durations = [float(l.split("\t")[5]) for l in lines if l.strip()]
    assert max(durations) >= 3.0, f"ring-out should sustain past 2 beats, max={max(durations)}"


def test_dive_widens_bend_range_and_restores_it():
    """A dive bomb must set RPN pitch-bend sensitivity before the wheel moves
    and restore the GM default (+/-2) after the note ends."""
    tl = InstrumentTimeline(instrument="lead_gtr")
    tl.add_note(
        start_beat=0.0,
        duration_beats=3.0,
        pitch=69,
        velocity=110,
        channel=3,
        expression={"dive": {"semitones": 12, "drop_beats": 2.0}},
    )
    msgs = _abs_msgs(_write(tl))

    # RPN select + data entry (12 semitones) at the start tick, before note_on.
    at_start = [m for t, m in msgs if t == 0]
    cc = [m for m in at_start if m.type == "control_change"]
    assert [(m.control, m.value) for m in cc] == [(101, 0), (100, 0), (6, 12), (38, 0)]
    assert any(m.type == "pitchwheel" for m in at_start)
    assert at_start[-1].type == "note_on", "range setup must precede the note"

    # Wheel falls to full down by the end of the drop (2.0 beats = 960 ticks).
    pw = [(t, m.pitch) for t, m in msgs if m.type == "pitchwheel"]
    assert (960, -8191) in pw
    assert min(v for _, v in pw) == -8191

    # At note end (3.0 beats = 1440 ticks): wheel re-centers, then the range
    # is restored to +/-2 and the RPN is closed (null select).
    end_tick = 1440
    at_end = [m for t, m in msgs if t == end_tick]
    wheel_reset_idx = next(i for i, m in enumerate(at_end)
                           if m.type == "pitchwheel" and m.pitch == 0)
    restore = [m for m in at_end[wheel_reset_idx:] if m.type == "control_change"]
    assert [(m.control, m.value) for m in restore] == [
        (101, 0), (100, 0), (6, 2), (38, 0), (101, 127), (100, 127)
    ]


def test_drum_channel_gets_explicit_kit_program():
    """FL Studio and friends don't assume channel 10 = drums on import, so the
    drum channel must carry an explicit Standard Kit program change."""
    from produzre.export.midi import add_channel_setup

    track = mido.MidiTrack()
    add_channel_setup(track, None, "drums", 9)
    pc = [m for m in track if m.type == "program_change"]
    assert [(m.channel, m.program) for m in pc] == [(9, 0)]

    # Melodic channels still get their configured program (and nothing when
    # no program is configured).
    class _Cfg:
        engines = {"lead_gtr": type("E", (), {"program": 30})(),
                   "mystery": type("E", (), {"program": None})()}

    track = mido.MidiTrack()
    add_channel_setup(track, _Cfg(), "lead_gtr", 3)
    assert [(m.channel, m.program) for m in track if m.type == "program_change"] == [(3, 30)]

    track = mido.MidiTrack()
    add_channel_setup(track, _Cfg(), "mystery", 5)
    assert not [m for m in track if m.type == "program_change"]


def test_extra_view_flattens_loader_nesting():
    """The config loader can wrap user params as extra.extra; the lead engine
    must see them flat, with user keys winning over persona-merged keys."""
    from produzre.engine.lead_gtr import _extra_view
    from produzre.model import InstrumentConfig

    ic = InstrumentConfig(extra={"extra": {"solo": True, "vibrato_rate": 0.9},
                                 "vibrato_rate": 0.1})
    flat = _extra_view(ic)
    assert flat["solo"] is True
    assert flat["vibrato_rate"] == 0.9, "user (nested) key must beat persona (top level)"
    assert _extra_view(InstrumentConfig(extra=None)) == {}


def test_swell_ramps_expression_cc11():
    """A feedback swell fades the note in via channel expression (CC11),
    starting quiet so the attack is softened like a volume pedal."""
    tl = InstrumentTimeline(instrument="lead_gtr")
    tl.add_note(
        start_beat=0.0,
        duration_beats=2.0,
        pitch=69,
        velocity=110,
        channel=3,
        expression={"swell": {"from": 40, "ramp_beats": 1.5, "to": 127}},
    )
    msgs = _abs_msgs(_write(tl))

    sw = [(t, m.value) for t, m in msgs
          if m.type == "control_change" and m.control == 11]
    assert sw, "expected CC11 ramp messages"
    # Starts low at the note's start tick (before the note_on), rises
    # monotonically, and lands exactly on full at the ramp end (720 ticks).
    assert sw[0] == (0, 40)
    vals = [v for _, v in sw]
    assert vals == sorted(vals), "swell ramp must rise monotonically"
    assert sw[-1] == (720, 127)
    at_start = [m for t, m in msgs if t == 0]
    assert at_start[0].type == "control_change", "swell must precede the attack"
    assert any(m.type == "note_on" for m in at_start)


def test_swell_ending_low_restores_full_expression():
    tl = InstrumentTimeline(instrument="lead_gtr")
    tl.add_note(
        start_beat=0.0,
        duration_beats=2.0,
        pitch=69,
        velocity=110,
        channel=3,
        expression={"swell": {"from": 90, "ramp_beats": 0.5, "to": 100}},
    )
    msgs = _abs_msgs(_write(tl))
    sw = [(t, m.value) for t, m in msgs
          if m.type == "control_change" and m.control == 11]
    # Ramp tops out at 100 at tick 240, then 127 is restored at note end.
    assert (240, 100) in sw
    assert (960, 127) in sw
