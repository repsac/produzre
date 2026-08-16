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
    for tr in mid.tracks:
        for m in tr:
            if m.type == "pitchwheel":
                pw_channels.add(m.channel)
            elif m.type == "note_on" and m.velocity > 0:
                note_channels.add(m.channel)

    # Lead vibrato/bend-ins (3), bass slide-ins (1), rhythm chord vibrato (2);
    # seed 23 deterministically lights up all three.
    assert pw_channels == {1, 2, 3}, f"pitchwheel on bass/rhythm/lead, got {pw_channels}"
    assert 9 not in pw_channels, "drums must never get pitch expression"
    assert 0 not in note_channels, "no notes may leak onto the piano channel"
