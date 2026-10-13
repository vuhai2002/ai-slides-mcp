"""Shared typed enums for tool parameters.

Annotating the MCP tool functions with these `Literal` aliases makes FastMCP
emit a JSON-Schema `enum` for each parameter, so any connecting AI agent sees the
exact set of valid values (not just a free-form string) - it can't guess an
invalid value like "high" and get an HTTP 422. The CLI derives its argparse
`choices` from the same aliases (via typing.get_args), keeping one source of truth.
"""
from __future__ import annotations

from typing import Literal

# Image reasoning effort, sent to ChatGPT's image backend as `thinking_effort`.
# "auto" sends no field (ChatGPT default). standard < extended < max.
Thinking = Literal["auto", "standard", "extended", "max"]

# Default effort for the deck tools (generate_slide_deck / branded_deck /
# styled_deck and CLI deck/branded/styled). Slides are text-heavy and often
# Vietnamese; "max" renders diacritics most reliably. Single-image generation
# (generate_image / CLI gen) keeps "auto".
DECK_THINKING: Thinking = "max"

# Slide design treatment applied by the prompt enhancer.
Style = Literal["auto", "slide", "fintech"]

# What the model should do with an attached reference image (see engine/ref_modes.py).
# "asset" aliases "logo"; "restyle" / "architecture" alias "render".
RefMode = Literal["style", "logo", "asset", "render", "restyle", "architecture"]
