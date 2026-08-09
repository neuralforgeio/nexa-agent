"""
OpenForge — Bootstrap Module
=============================

This module is imported **first** by every entry point. It ensures UTF-8
stdio encoding on all platforms (critical on Windows where the default
console encoding may be cp1252).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import sys


def _ensure_utf8_stdio() -> None:
    """
    Force UTF-8 encoding on stdin/stdout/stderr.

    On Windows, the default console encoding can cause UnicodeEncodeError
    when printing emoji or non-ASCII characters. This reconfigures the
    streams to use UTF-8 with error replacement.
    """
    for stream_name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        # Reconfigure the stream's encoding if the method is available
        # (Python 3.7+). Fall back silently on older interpreters.
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (TypeError, ValueError):
                pass


# Run on import so any subsequent print() calls are UTF-8 safe.
_ensure_utf8_stdio()
