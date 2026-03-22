# Banner Generator

A Python pipeline that generates professional banners by combining an AI-generated icon (via Pollinations/Flux) with your background image, title, and badge — all configured from simple files.

---

## Project Structure

```
project/
├── generate.py            ← main script
├── params.conf            ← visual config (layout, colors, sizes, files)
├── input.json             ← your banner content (create from example below)
├── input.example.json     ← example content file — copy and rename to input.json
├── input.schema.json      ← JSON schema for input.json validation
├── .env                   ← API key (never commit)
├── .gitignore             ← git ignore rules
├── requirements.txt       ← Python dependencies
├── background.png         ← your background image (not committed)
└── output.webp            ← generated banner (auto-created, not committed)
```

---

## Getting Started

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API key
Create a `.env` file:
```ini
POLLINATIONS_KEY=your_pollinations_key_here
```
Get your free key at [enter.pollinations.ai](https://enter.pollinations.ai).

### 3. Create your input file
```bash
cp input.example.json input.json
```
Then edit `input.json` with your content.

### 4. Add your background image
Place your background image as `background.png` (or update `params.conf`).

### 5. Run
```bash
python generate.py
```

---

## Configuration

### `input.json` — Banner content
```json
{
  "$schema": "./input.schema.json",
  "title": "Créez, apprenez, transmettez",
  "subtitle": "La plateforme pour construire, enrichir et partager votre savoir",
  "icon_prompt": "A single open book with a lightbulb above it, flat modern illustration style, vibrant multi-color, clean minimalistic, no shadows, no text, centered square composition"
}
```

| Field | Description |
|---|---|
| `title` | Main bold text on the banner |
| `subtitle` | Text inside the badge |
| `icon_prompt` | Icon description sent to Pollinations/Flux. The script auto-appends background color and color palette. |

> Validate with VS Code by adding `"$schema": "./input.schema.json"` — you get autocomplete and error highlighting.

---

### `params.conf` — Visual configuration

```ini
# Layout (fraction of image height 0.0–1.0)
icon_y    = 0.26
title_y   = 0.52
badge_y   = 0.64

# Icon
icon_size     = 320       # final icon size in px
icon_api_size = 512       # size requested from Pollinations
icon_seed     = 42        # change for different icon variations
cache_icon    = true      # save raw icon as icon_<timestamp>.png

# Font sizes (fraction of image height)
title_font_size    = 0.085
subtitle_font_size = 0.038

# Colors (hex #RRGGBB)
title_color      = #143769
badge_color      = #7FCCE9
badge_text_color = #FFFFFF

# Icon coloring
icon_keep_colors = true       # preserve AI-generated colors
icon_tint_color  = #1a5a9a   # used only when icon_keep_colors=false

# Files
background = background.png
output     = output.webp      # supports .webp, .jpg, .png
```

---

## Usage

### Generate icon via Pollinations API
```bash
python generate.py
```

### Use a custom icon (skip API call)
```bash
python generate.py --icon=icon_1234567890.png
```

> When `cache_icon = true`, each Pollinations-generated icon is saved as `icon_<timestamp>.png` — reuse it with `--icon=` to avoid extra API calls.

---

## Pipeline

```
input.json
    ↓ load content
build_icon_prompt()        → appends solid bg + color palette to icon_prompt
    ↓
Pollinations/Flux API      → generates icon (512×512)
    ↓
remove_background_flood()  → flood fill from corners → transparent icon
    ↓
anti-alias edges           → Gaussian blur on alpha channel only
    ↓
compose()                  → icon + title + badge on background.png
    ↓
output.webp
```

---

## Output Formats

Set the `output` key in `params.conf`:

| Extension | Format | Quality |
|---|---|---|
| `.webp` | WebP | 90 |
| `.jpg` / `.jpeg` | JPEG | 95 |
| `.png` | PNG | lossless |

---

## Git Setup

```bash
git init
git add generate.py params.conf input.example.json input.schema.json requirements.txt README.md .gitignore
git commit -m "initial commit"
```

> `.env`, `input.json`, `background.png`, `output.*`, and `icon_*.png` are excluded by `.gitignore`.

---

## Tips

- **Icon prompt**: describe shape and style only — background color and palette are injected automatically.
- **icon_keep_colors = true**: Flux generates full color. Set to `false` to force a single `icon_tint_color`.
- **icon_seed**: change the number to get a different icon variation from the same prompt.
- **Background removal**: flood fill detects background color automatically from the 4 corners — works regardless of what color Flux generates.
