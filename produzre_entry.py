"""Entry point for PyInstaller-built standalone executable.

Eagerly imports all engine subpackages so PyInstaller includes them in the
frozen bundle. Without these explicit imports, PyInstaller cannot trace the
dynamic ``importlib.import_module(".engine.bass", package="produzre")`` calls
in ``produzre.config.engines``.
"""

# -- Ensure all dynamically-loaded engine modules are importable -----------
import produzre.engine  # noqa: F401
import produzre.engine.acoustic_gtr  # noqa: F401
import produzre.engine.arpeggiator  # noqa: F401
import produzre.engine.bass  # noqa: F401
import produzre.engine.drums  # noqa: F401
import produzre.engine.harmony  # noqa: F401
import produzre.engine.lead_gtr  # noqa: F401
import produzre.engine.rhythm_gtr  # noqa: F401

from produzre.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
