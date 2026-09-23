"""Compatibility launcher for the former single-file application."""

from opencandles.app import main


if __name__ == "__main__":
    raise SystemExit(main())
