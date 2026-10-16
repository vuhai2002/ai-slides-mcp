"""`cgimg models`: list the chat models the account pool may use for images."""
from __future__ import annotations

import argparse
import sys


def _cmd_models(args: argparse.Namespace) -> int:
    """Print valid --model values, marking the newest and the default.

    Uses the first account with quota (one pool probe) plus 2 light backend calls;
    run it once in a while, not in a loop (heavy probing can revoke sessions).
    """
    from cgimg.engine.generate import get_pool
    from cgimg.engine.upstream_model import list_chat_models, newest_model

    try:
        models = list_chat_models(get_pool().current_token())
    except Exception as exc:  # no accounts / no quota / network
        print(f"error: could not list models: {exc}", file=sys.stderr)
        return 1
    newest = newest_model(models)
    for m in models:
        tags = [t for t, hit in (("newest", m == newest), ("default", m == "gpt-5-5")) if hit]
        print(m + (f"  ({', '.join(tags)})" if tags else ""))
    # The list differs per account; the vendor default may be absent yet still accepted.
    print("default when --model is omitted: gpt-5-5"
          + ("" if "gpt-5-5" in models else " (not listed for this account)"))
    return 0
