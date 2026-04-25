#!/usr/bin/env python3
"""Shared CLI helpers for umlgen scripts.

Provides an ArgumentParser subclass that prints the full help text (with
emphasis on mandatory arguments) whenever a parse error occurs, instead of the
terse default argparse error line.
"""

from __future__ import annotations

import argparse
import sys


class HelpOnErrorParser(argparse.ArgumentParser):
    """ArgumentParser that shows full help + a prominent error line on failure.

    This replaces the default one-liner error output with a user-friendly
    display that highlights which mandatory arguments are missing.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_help(sys.stderr)
        self.exit(2, f"\n{'='*60}\nERROR: {message}\n{'='*60}\n")
