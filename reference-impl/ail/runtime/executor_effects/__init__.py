"""Mixin classes for `Executor` effect families.

Stage 1 of the executor split RFC (`docs/proposals/executor-split.md`).
Each domain lives in a small module exposing a single `*EffectMixin`
class; `EffectsMixin` composes them. The umbrella mixin is what
`Executor` inherits.

Bringing a new domain over: copy the `_<name>_*` methods out of
`executor.py` into a `<name>.py` module here, declare a
`<Name>EffectMixin` class with those methods, add it to
`EffectsMixin`'s bases, and delete the originals from `executor.py`.
The dispatch entries in `Executor._builtin_effect` keep referencing
`self._<name>` and resolve via MRO to the mixin.

No behavior change — same input → same output → same ledger.
"""

from .clock import ClockEffectMixin


class EffectsMixin(ClockEffectMixin):
    """Aggregate mixin for all effect-domain methods on `Executor`.

    Add new mixins to the bases as the split progresses (state, env,
    schedule, queue, http, …). MRO order does not matter while each
    mixin owns disjoint method names — but keep them disjoint.
    """
    pass


__all__ = ["EffectsMixin", "ClockEffectMixin"]
