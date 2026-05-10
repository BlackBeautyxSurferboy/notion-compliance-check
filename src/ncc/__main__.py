"""Allow `python -m ncc audit ...`."""

from ncc.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
