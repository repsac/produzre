"""Allow the CLI package to be executed with `python -m produzre.cli`."""

from . import main

if __name__ == "__main__":
    raise SystemExit(main())
