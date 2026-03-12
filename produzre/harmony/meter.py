from __future__ import annotations

"""Time signature utilities.

Produzre represents musical time internally in quarter-note beats ("beats").
Meters (time signatures) are therefore expressed in terms of how many
quarter-note beats occur per bar.

This module provides:
- `Meter`: a small dataclass for holding numerator/denominator.
- `parse_meter()`: parsing from a human-friendly "N/D" string.

These helpers are used by harmony planning and pattern/section timing code,
including mixed-meter arrangements.
"""

from dataclasses import dataclass


@dataclass
class Meter:
    """Representation of a musical meter (time signature).

    Attributes:
        numerator: The number of denominator-units per bar (e.g., 4 in 4/4).
        denominator: The note value that gets the beat (e.g., 4 in 4/4, 8 in 6/8).

    Notes:
        Produzre's internal time unit is the *quarter-note beat*. This means
        meters with denominators other than 4 map to fractional beats-per-bar.
        For example, 6/8 is 3.0 quarter-note beats per bar.
    """

    numerator: int
    denominator: int

    @property
    def beats_per_bar(self) -> float:
        """Return beats-per-bar expressed in quarter-note beat units.

        Produzre uses quarter-note beats as its internal timing unit regardless
        of the meter denominator. This property converts a time signature into
        the equivalent number of quarter-note beats per bar.

        Examples:
            - 4/4 -> 4.0 beats per bar
            - 3/4 -> 3.0 beats per bar
            - 6/8 -> 3.0 beats per bar
            - 7/8 -> 3.5 beats per bar

        Returns:
            float: Number of quarter-note beats in a single bar.
        """
        if self.denominator == 4:
            return float(self.numerator)
        return float(self.numerator) * (4.0 / float(self.denominator))


def parse_meter(meter_str: str) -> Meter:
    """Parse a meter string like "4/4" or "7/8" into a `Meter`.

    Parsing rules:
      - The string must be in "N/D" form where N and D are integers.
      - Whitespace around N and D is ignored.
      - Both values must be positive.

    Args:
        meter_str: Meter string in "N/D" form.

    Returns:
        Meter: Parsed meter dataclass.

    Raises:
        ValueError: If the string is not in N/D form, contains non-integers,
            or has non-positive values.
    """
    try:
        num_str, den_str = meter_str.split("/")
        num = int(num_str.strip())
        den = int(den_str.strip())
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Invalid meter string: {meter_str!r}") from e

    if num <= 0 or den <= 0:
        raise ValueError(f"Meter must have positive numbers: {meter_str!r}")

    return Meter(numerator=num, denominator=den)
