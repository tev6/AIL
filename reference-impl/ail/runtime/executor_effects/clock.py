"""`clock.now` effect — wall-clock read.

Extracted from `executor.py` as Stage 1 of the executor split RFC
(`docs/proposals/executor-split.md`). Behavior unchanged.
"""

import time

from ..provenance import Origin


class ClockEffectMixin:
    def _clock_now(self, args: list,
                   kwargs: dict,
                   origin: Origin):
        """Return the current wall-clock time as an ISO-8601 UTC string.

        Shape:
            perform clock.now()            -> "2026-04-23T15:02:34Z"
            perform clock.now("iso")       -> same as above
            perform clock.now("unix")      -> "1776879154" (seconds since epoch)

        Returning a plain Text (not a Result) because clock access does
        not fail on any platform we support. The value carries an
        effect-origin node so provenance queries can tell that a
        timestamp came from clock.now rather than being hardcoded.

        Deliberately no `tz` argument in v0 — non-developers won't
        know to pass one, and UTC is the right default. A pure fn
        library can format for a locale later.
        """
        # Local import: ConfidentValue lives in executor.py; importing
        # it at module level would create a circular import since
        # executor.py imports this mixin.
        from ..executor import ConfidentValue
        fmt = (args[0].value if args else "iso")
        if isinstance(fmt, str):
            fmt = fmt.lower()
        if fmt in ("unix", "epoch", "seconds"):
            value = str(int(time.time()))
        else:
            value = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return ConfidentValue(value, 1.0, origin=origin)
