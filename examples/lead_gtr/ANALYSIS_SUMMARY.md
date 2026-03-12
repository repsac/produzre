# Lead Guitar Analysis Summary

## Initial Findings (2026-02-03)

### Problem Confirmed

The lead guitar engine produces **significantly lower density** than expected, even with maximum parameter settings.

### Density Comparison Test Results

**Test File**: `basics/density-comparison.yaml`
**Total Events**: 57 notes across 24 bars

| Section | Config | Expected | Actual | Status |
|---------|--------|----------|--------|--------|
| Sparse | intensity: 0.5<br>rest_probability: 0.5 | 1-2 notes/bar | **1.5 notes/bar** | ✓ PASS |
| Moderate | intensity: 0.7<br>rest_probability: 0.25 | 3-5 notes/bar | **2.6 notes/bar** | ✗ FAIL |
| Dense | intensity: 0.9<br>solo: true<br>rest_probability: 0.1 | 5-8 notes/bar | **3.0 notes/bar** | ✗ FAIL |

### Rock Solo Test Results

**Test File**: `styles/rock-solo.yaml`
**Total Events**: 99 notes across 40 bars

| Section | Bars | Config | Actual Density |
|---------|------|--------|----------------|
| Verse | 8 | intensity: 0.5 | ~1.1 notes/bar |
| Chorus | 8 | intensity: 0.75 | ~1.9 notes/bar |
| Guitar Solo | 16 | intensity: 1.0<br>solo: true<br>rest_probability: 0.05 | ~4.0 notes/bar |
| Chorus (repeat) | 8 | intensity: 0.75 | ~1.9 notes/bar |

**Expected for Guitar Solo**: 6-10 notes/bar minimum for a compelling rock solo
**Actual**: Only 4.0 notes/bar - still very sparse

## Root Cause Analysis

The lead guitar engine has sophisticated features but appears to have one or more of these issues:

1. **Density calculation too conservative**: The formula `density = intensity * 0.65 + 0.25` (for solo) may cap too low
2. **Rest probability overriding density**: High rest_probability might be removing too many notes
3. **Grid position selection too strict**: May be rejecting too many potential note placements
4. **Phrase generation limiting notes**: Motif-based phrasing may create inherently sparse patterns

## Parameter Effectiveness

Based on initial tests:

| Parameter | Effect Observed | Notes |
|-----------|-----------------|-------|
| intensity | Modest effect | Increases from 0.5→1.0 only doubles density (1.5→3.0 notes/bar) |
| solo | Slight boost | Adds ~0.5-1.0 notes/bar |
| rest_probability | Works as expected | Lower values = slightly more notes |
| contour_style | Not yet tested | Needs analysis |
| phrase_len_bars | Not yet tested | Needs analysis |

## Comparison to Other Instruments

For reference, in the same test songs:

- **Bass**: 100+ events per 8-bar section (12-13 notes/bar) - Very dense
- **Rhythm Guitar**: 60+ events per 8-bar section (7-8 notes/bar) - Moderate/dense  
- **Lead Guitar**: 12-24 events per 8-bar section (1.5-3.0 notes/bar) - Very sparse

Lead guitar is producing **4-8x fewer notes** than rhythm guitar with maximum intensity settings.

## Recommendations for Engine Improvement

1. **Increase base density multiplier**: 
   - Current: `density = intensity * 0.65 + 0.25` (solo mode)
   - Suggested: `density = intensity * 1.2 + 0.3` or higher

2. **Reduce rest probability impact**:
   - Current rest_probability defaults seem too high
   - Even 0.05 (5% rest) produces very sparse output

3. **Review note placement algorithm**:
   - May be rejecting too many grid positions
   - Check if accent avoidance is too aggressive

4. **Add density override parameter**:
   - Allow users to directly specify notes-per-bar target
   - Bypass calculation formulas for explicit control

## Next Steps

1. ✅ Created 6 example files covering different use cases
2. ⏳ Build remaining examples and analyze outputs
3. ⏳ Profile engine code to identify bottleneck in note generation
4. ⏳ Experiment with parameter overrides to find usable settings
5. ⏳ Propose engine code changes to improve default density

## Example Files Created

### Basics
- ✅ `density-comparison.yaml` - Sparse vs moderate vs dense
- ✅ `resolution-comparison.yaml` - Harmonic resolution strength

### Styles
- ✅ `blues-lead.yaml` - 12-bar blues lead guitar
- ✅ `rock-solo.yaml` - High-energy rock solo
- ✅ `jazz-lead.yaml` - Jazz improvisation

### Advanced
- ✅ `contour-comparison.yaml` - Stepwise vs balanced vs leaping
- ✅ `phrase-length-comparison.yaml` - 1-bar vs 2-bar vs 4-bar phrases

All examples have exports enabled for TSV/grid analysis.
