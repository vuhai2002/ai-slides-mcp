# AGENTS.md - guidance for AI agents working on (or with) ai-slides-mcp

Single source of truth for any AI tool (Claude Code, Codex, Cursor, ...) working
on this repo. `CLAUDE.md` just points here. Read this before editing.

## What this is

`ai-slides-mcp` is an MCP server + CLI that generates images through the **ChatGPT
web backend** (no API key - it drives a logged-in ChatGPT account over OAuth) and
assembles them into full-bleed PowerPoint decks (plain, brand-aware, or
reference-styled).

> Disclaimer: this reverse-engineers ChatGPT's web backend and violates OpenAI's
> ToS. Use a throwaway/secondary account. Details in `README.md`.

## How a *consuming* AI discovers capabilities (no repo scan needed)

When an agent connects to this server over MCP, the server auto-advertises every
tool's name, description (the function docstring), and JSON-Schema input -
including `enum`s for `style` and `thinking`. A consuming agent does **not** read
this repo to call the tools; it gets the contract from the protocol. This file is
for agents that **develop** the repo, and as a human-readable mirror of the tools.

## MCP tools (`src/cgimg/server.py`)

| Tool | Key params (defaults) | Returns |
|------|-----------------------|---------|
| `login_status` | - | `{authed, ...}` |
| `generate_image` | `prompt`, `aspect="16:9"`, `n=1`, `out_dir="out"`, `enhance=True`, `style="auto"`, `thinking="auto"` | `{paths}` |
| `build_pptx` | `image_paths`, `out_path="deck.pptx"`, `aspect="16:9"` | `{path}` |
| `generate_slide_deck` | `prompts`, `aspect`, `out_pptx`, `out_dir`, `enhance=True`, `style="slide"`, `thinking="auto"` | `{path, image_paths}` |
| `branded_deck` | `logo_path`, `prompts`, ..., `logo_position`, `logo_scale`, `thinking="auto"` | `{path, image_paths, brand_colors}` |
| `styled_deck` | `ref_image`, `prompts`, ..., `thinking="auto"` | `{path, image_paths, brand_colors}` |

The same functions back the CLI (`uv run cgimg <gen|ppt|branded|styled|login>`).

### Parameter value sets (enforced as schema enums - keep in `src/cgimg/types.py`)
- `aspect`: `16:9` `1:1` `3:4` `4:3` `9:16`, or raw `WxH` (free string, not an enum).
- `style`: `auto` `slide` `fintech`.
- `thinking`: `auto` `standard` `extended` `max`. Reasoning effort before drawing;
  higher = better rendered text (esp. Vietnamese diacritics) but slower. Sent to the
  backend as `thinking_effort`; **only these values are valid** (others -> HTTP 422).

## Quick start (dev)

```bash
uv sync
uv run cgimg login                              # then: cgimg login --callback "<url>"
uv run pytest                                   # 32 tests, must pass
uv run cgimg gen "test" --aspect 4:3 --thinking max --no-enhance
```

## Architecture & the vendoring model (READ before editing engine code)

Layout:
- `src/cgimg/` - **our** code: `server.py`, `cli.py`, `sizes.py`, `types.py`,
  `engine/` (`generate.py`, `enhance.py`, `image_thinking.py`), `ppt/`, `branding/`,
  `auth/`.
- `src/cgimg/_vendor/` - chatgpt2api, vendored. Two classes of file:
  - **VERBATIM** - byte-identical to upstream, auto-re-pulled. Everything except:
  - **LOCAL shims** - ours, never auto-overwritten: `services/account_service.py`
    (single-account shim), `services/protocol/__init__.py`,
    `services/storage/factory.py`, `_vendor/__init__.py`.

Rules (important):
- **NEVER hand-edit a VERBATIM `_vendor/` file.** To change vendored behavior, patch
  it from our code. Reference pattern: `engine/image_thinking.py` monkey-patches the
  image-prepare payload at runtime so `_vendor/services/openai_backend_api.py` stays
  byte-identical (and thus auto-updatable).
- `VENDOR_REV` pins the synced upstream commit. Re-sync with
  `scripts/update-vendor.sh` (or `update-vendor.ps1`): it overwrites VERBATIM files,
  leaves shims untouched, warns if upstream changed a shimmed file, and re-pins SHA.
- `tests/test_vendor_contract.py` fails if upstream starts calling an
  `account_service` method our shim does not handle explicitly. Keep it green after
  every vendor update.

## Conventions
- Python 3.12, `uv`. Files < 200 lines, kebab-case names, descriptive comments.
- `thinking`/`style` value sets live ONCE in `src/cgimg/types.py` (drives both the
  MCP schema enums and the CLI `choices`). Add new values there, not inline.
- Plain ASCII punctuation in generated text; **preserve Vietnamese diacritics**.
- Don't commit `auth.json` or any secret.

## Gotchas
- Vietnamese text garbled in an image -> use `thinking="max"`, often with
  `--no-enhance` + a verbatim prompt.
- Generation is slow (~30-120s; higher `thinking` is slower). Expected, not a hang.
- Auth token: `%APPDATA%\cgimg\auth.json` (Windows) / `~/.config/cgimg/auth.json`.
  Re-run `cgimg login` if expired.
- `scratch/` is gitignored - the update-vendor upstream checkout lives there.

## Pointers
- `README.md` - user-facing install + usage.
- `docs/specs/`, `docs/plans/` - historical design/plan snapshot (2026-06-06).
- `NOTICE` - vendoring attribution + the LOCAL-file list.
