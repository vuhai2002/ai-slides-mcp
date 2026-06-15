# ai-slides-mcp

An MCP server (and CLI) that generates images through the ChatGPT web backend and assembles them into full-bleed PowerPoint decks (brand-aware and reference-styled).

## ⚠️ Disclaimer

This project is provided **for personal learning and research only**. It **reverse-engineers the ChatGPT web backend**:

- **Not affiliated with, endorsed by, or sponsored by OpenAI.**
- Using it **violates OpenAI's Terms of Service**. Your account may be rate-limited or **permanently banned**.
- **Use a throwaway / secondary account — never your important one.**

Provided **as-is, with no warranty**. You assume all risk. If you are not comfortable with these terms, do not use this software.

## What it does

- Generates images from text prompts at a chosen aspect ratio (16:9, 1:1, 3:4, 4:3, 9:16, or raw `WxH`).
- **Reasoning effort** (`thinking`): optionally make the model think harder before drawing (`standard` < `extended` < `max`) — markedly improves rendered text fidelity, e.g. Vietnamese diacritics.
- **Auto-enhances** prompts via your ChatGPT account's text model before drawing (mirrors what the web UI does silently). Three slide styles: `auto`, `slide`, `fintech`.
- Builds full-bleed PowerPoint (`.pptx`) decks from a set of images.
- **Branded decks**: auto-detects brand colors from your logo, generates slides in those colors, and composites your logo onto every slide.
- **Styled decks**: matches the design style and palette of a reference image (without copying its text/content).
- **Multiple accounts (auto-rotation)**: log in several ChatGPT accounts; the tool probes each account's remaining image quota and rotates to the next when one runs dry, so several free accounts' daily caps combine into one deck. If all run out mid-deck you get a partial deck plus when quota resets.
- Works as an MCP server across **Claude Code, Codex, and Antigravity** over stdio.
- Multi-account, fully local auth - your tokens never leave your machine.

## Requirements

- **[uv](https://docs.astral.sh/uv/)** — handles Python and dependencies (you do **not** need to install Python separately; `uv` fetches Python 3.12 automatically).
- **git**
- A **ChatGPT account** (use a secondary one — see disclaimer)

Install `uv` (one time per machine):

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Install

### One-click installer (recommended)

After cloning, run the installer — it installs `uv` if missing, syncs deps, walks you through login, and registers the MCP server:

```bash
git clone https://github.com/vuhai2002/ai-slides-mcp.git
cd ai-slides-mcp
```
```powershell
# Windows (PowerShell) — or right-click install.ps1 -> Run with PowerShell
powershell -ExecutionPolicy Bypass -File install.ps1
```
```bash
# macOS / Linux
bash install.sh
```

### Manual install

```bash
git clone https://github.com/vuhai2002/ai-slides-mcp.git
cd ai-slides-mcp
uv sync
uv run cgimg login
# A browser opens -> log into ChatGPT -> you land on a platform.openai.com page (it may say "Oops").
# Copy the FULL callback URL from the address bar, then run:
uv run cgimg login --callback "<paste the callback URL here>"
```

> If you keep your repo **private**, the cloning machine must be signed into a GitHub account with access (e.g. `gh auth login`).

### Why login is two steps

Login uses OAuth with PKCE. Step 1 builds the authorization URL and stashes a one-time secret (the PKCE *verifier*) on disk. Step 2 exchanges the code in the callback URL for tokens — and that exchange needs the **same verifier** that step 1 generated. Splitting it into two commands lets the verifier persist between building the URL and redeeming the code, instead of being lost when the browser hands control back to you.

## Register as an MCP server

The config is the **same shape for Claude Code, Codex, and Antigravity**:

```json
{
  "mcpServers": {
    "ai-slides": {
      "command": "uv",
      "args": ["run", "cgimg-mcp"],
      "cwd": "<absolute path to the cloned repo>"
    }
  }
}
```

Replace `cwd` with the absolute path where you cloned the repo (e.g. `D:\\ai-slides-mcp` on Windows — note the doubled backslashes in JSON). For Claude Code you can instead run:

```bash
claude mcp add ai-slides -- uv run cgimg-mcp
```

## MCP tools

Six tools are exposed by the server (`src/cgimg/server.py`):

| Tool | Params | Returns | Description |
|------|--------|---------|-------------|
| `login_status` | — | `{authed, accounts, ready_count}` | List logged-in accounts (cheap, hint-based; use the CLI `cgimg accounts` for live quota). |
| `generate_image` | `prompt`, `aspect="16:9"`, `n=1`, `out_dir="out"`, `enhance=True`, `style="auto"`, `thinking="auto"`, `brand_colors=None`, `reserve_corner=None` | `{paths}` | Generate `n` image(s) from a prompt. Returns saved PNG paths. |
| `build_pptx` | `image_paths`, `out_path="deck.pptx"`, `aspect="16:9"` | `{path}` | Assemble existing images into a full-bleed PPTX. |
| `generate_slide_deck` | `prompts`, `aspect="16:9"`, `out_pptx="deck.pptx"`, `out_dir="out"`, `enhance=True`, `style="slide"`, `thinking="auto"`, `brand_colors=None`, `reserve_corner=None` | `{path, image_paths, incomplete, generated, total, reset_at}` | Generate one image per prompt (one slide each, named `s01.png`...), then assemble into a PPTX. Returns a partial deck (`incomplete=true`) if accounts run out of quota. |
| `branded_deck` | `logo_path`, `prompts`, `aspect="16:9"`, `out_pptx="deck.pptx"`, `out_dir="out"`, `logo_position="top-left"`, `logo_scale=0.15`, `thinking="auto"` | `{path, image_paths, brand_colors, incomplete, generated, total, reset_at}` | Auto-detects brand colors from the logo, generates slides in those colors, and composites the **original logo** onto each slide. |
| `styled_deck` | `ref_image`, `prompts`, `aspect="16:9"`, `out_pptx="deck.pptx"`, `out_dir="out"`, `thinking="auto"` | `{path, image_paths, brand_colors, incomplete, generated, total, reset_at}` | Matches a **reference image's** design style + colors (does **not** copy its text/content). |

For `generate_slide_deck` / `branded_deck` / `styled_deck`, each prompt is the **content of one slide** — pass raw slide content and the enhancer designs it.

## Slide styles

When `enhance=True`, the prompt is expanded by your ChatGPT account's text model before drawing. The `style` argument picks the design treatment:

| Style | Look | Enhancement |
|-------|------|-------------|
| `auto` | General — a dense infographic, or a photographic scene if the prompt names a real scene. | Skipped if the prompt is already long (≥280 chars). |
| `slide` | Clean editorial presentation slide: light cream background, ONE warm accent color, a soft 3D hero visual, slide-number pill, bottom takeaway banner. | **Always runs.** |
| `fintech` | Premium light-blue dashboard look: glassmorphism cards, circular blue-gradient icon badges, optional 3D robot + chart widgets, bottom blue banner. | **Always runs.** |

**Content completion (for `slide` / `fintech`):** these styles complete your content into a **full, information-rich slide** — every main point gets a bold label **plus** a 2-line supporting description, sparse input is intelligently expanded into a sensible slide, and the prompt explicitly demands that **all** text be rendered in full (never dropped or abbreviated). It stays legible (not a wall of tiny text) and never fabricates fake statistics. See [`docs/styles.md`](./docs/styles.md) for a full reference.

> `generate_image` and the CLI `gen` accept `style` values `auto`, `slide`, and `fintech`. `generate_slide_deck` defaults to `slide`.

## Reasoning effort (`thinking`)

ChatGPT's web UI has an "Intelligence" selector that makes the image model reason more before drawing. `generate_image`, the deck tools, and the CLI expose the same via `thinking`:

| `thinking` | Effect |
|------------|--------|
| `auto` (default) | Sends no preference — ChatGPT's own default (fast). |
| `standard` | Light reasoning. |
| `extended` | More reasoning. |
| `max` | Most reasoning — best for **rendered text** (e.g. Vietnamese diacritics), slowest. |

Higher effort noticeably improves text fidelity inside the image. If generated slides garble Vietnamese diacritics at the default, try `--thinking max` (CLI) or `thinking="max"` (MCP). Values are passed to ChatGPT's image backend as `thinking_effort`; anything outside the set above is rejected by the backend.

## CLI usage

```bash
# 1. Log in (two-step, see Install above)
uv run cgimg login
uv run cgimg login --callback "<paste callback URL>"

# Multiple accounts (auto-rotation): repeat the login for EACH account. To add a
# DIFFERENT account, sign out of chatgpt.com first or use an incognito/private
# window (login captures whichever account is signed in). Then:
uv run cgimg accounts                    # list accounts with live remaining quota
uv run cgimg logout you@example.com      # remove one (by email or user_id)
uv run cgimg logout --all                # remove every account
#   The pool auto-rotates: it drains one account, then moves to the next. A deck
#   bigger than your total quota stops and returns a PARTIAL deck + reset time.
#   Note: rotating many accounts raises ban-detection risk - use throwaway accounts.

# 2. Generate image(s)  (auto-enhance is ON by default; add --no-enhance to send the prompt as-is)
uv run cgimg gen "a serene mountain lake at dawn" --aspect 16:9 --n 1 --out out
uv run cgimg gen "AI agents for customer support" --style slide      # clean editorial slide
uv run cgimg gen "real-time fraud detection" --style fintech         # light-blue dashboard slide
uv run cgimg gen "ai agent" --aspect 1:1 --no-enhance                # send prompt verbatim
uv run cgimg gen "Trí tuệ nhân tạo cho doanh nghiệp" --thinking max  # max reasoning = best Vietnamese text
uv run cgimg gen "RAG pipeline" --style slide --accent "#10B981" --reserve-corner top-left  # brand color + clear corner for a logo

# 3. Generate a multi-slide deck (one image per prompt; slides saved s01.png, s02.png...)
uv run cgimg deck --prompts "Intro" "How it works" "Pricing" --style slide --out deck.pptx
uv run cgimg deck --prompts-file slides.txt --thinking max --accent "#10B981" --reserve-corner top-left
#   --prompts-file: one prompt per line (blank lines and lines starting with # are skipped)
#   --no-enhance + --style: applies the slide look via a concise offline template (good for dense Vietnamese text)

# 4. Build a deck from existing images
uv run cgimg ppt img1.png img2.png --out deck.pptx --aspect 16:9

# 5. Branded deck — slides in your brand colors with your logo composited on each
uv run cgimg branded logo.png \
  --prompts "What is RAG?" "RAG pipeline" "Benefits" \
  --out deck.pptx --position top-left --scale 0.15

# 6. Styled deck — match a reference image's design (its text/content is NOT copied)
uv run cgimg styled reference-slide.png \
  --prompts "Intro" "How it works" "Pricing" \
  --out deck.pptx
```

`gen` and `deck` accept `--accent <hex>` (forces a brand color) and `--reserve-corner <pos>` (keeps a corner clear for a logo you add later; the model draws no logo/text there). `branded` and `styled` also accept `--aspect` and `--out-dir` (default `out`). They print the deck path and each generated image path.

## Aspect ratios

| Aspect | Size sent | ChatGPT returns |
|--------|-----------|-----------------|
| `16:9` | 1920x1080 | ~1672x941 |
| `1:1`  | 1024x1024 | 1024x1024 |
| `3:4`  | 1024x1536 | ~1086x1448 |
| `9:16` | 1080x1920 | ~941x1672 |
| `4:3`  | 1440x1080 | ~1448x1086 |
| `WxH`  | as given  | normalized by ChatGPT |

ChatGPT honors the **ratio**, not exact pixels — it normalizes to its own native dimensions (so `16:9` yields roughly `1672x941`, not exactly `1920x1080`). This is expected.

PPTX output is **full-bleed**: the image fills the slide edge to edge, so the image aspect should match the deck aspect to avoid cropping or letterboxing.

## How it works

- Vendors [chatgpt2api](https://github.com/basketikun/chatgpt2api)'s proven OAuth + image backend (under `src/cgimg/_vendor/`).
- Stores a single account token locally at `%APPDATA%\cgimg\auth.json` (Windows) or `~/.config/cgimg/auth.json` (Linux/macOS). It is **never committed**.
- Auto-refreshes the access token via the stored `refresh_token` when it expires.

## Examples

Showcase slides generated by this server live in [`examples/sample-slides/`](./examples/sample-slides/) — a mix of `slide`/`fintech` styles, dense multi-task slides, custom layouts, and tables.

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `not logged in` | Run `uv run cgimg login` (two steps). |
| Token expired / auth errors | Re-run the login flow. |
| Generation is slow (~30–90s per image) | Normal — it polls ChatGPT until the image is ready. |
| Prompt rejected / blocked | ChatGPT's content moderation refused it. Adjust the prompt and retry — refusals are often transient (`styled_deck` auto-retries up to 3×). |
| Text in the image looks imperfect on a very dense slide | Image models can garble small text when a slide is packed. Reduce the content or split into more slides. |
| Image dims aren't exactly what you asked | Expected — ChatGPT honors the ratio and normalizes to its native size. |

## Attribution & License

This project vendors code from:

- [**chatgpt2api**](https://github.com/basketikun/chatgpt2api) — Copyright (c) 2026 kunkun, MIT License. Powers the OAuth + image backend. Vendored under `src/cgimg/_vendor/`.

Vendored files retain their original behavior. See [`NOTICE`](./NOTICE) for details.
