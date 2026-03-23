"""
Banner generation pipeline
══════════════════════════
1. Load params from params.conf (layout, colors, sizes, files)
2. Load content from prompt.txt (title, subtitle, icon_prompt)
3. Build enriched icon prompt (auto-injects solid bg + color palette)
4. Generate icon via Pollinations/flux API
5. Remove background via flood fill → transparent icon
6. Anti-alias edges
7. Composite icon + title + badge onto background with Pillow
"""
import requests
import base64
import io
import time
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ── DEFAULT PARAMS ────────────────────────────────────────────────────────
DEFAULTS = {
    # layout
    "icon_y":             0.26,
    "title_y":            0.52,
    "badge_y":            0.64,
    # icon
    "icon_size":          320,
    "icon_api_size":      512,
    "icon_seed":          42,
    "cache_icon":         True,
    # fonts
    "title_font_size":    0.085,
    "subtitle_font_size": 0.038,
    # colors
    "title_color":        (20, 55, 105, 255),
    "badge_color":        (93, 172, 229, 235),
    "badge_text_color":   (255, 255, 255, 255),
    "icon_keep_colors":   True,
    "icon_tint_color":    (26, 90, 154, 255),
    # files
    "background":         "background.png",
    "output":             "output.webp",
}

FONT_BOLD  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PARAMS_PATH = "params.conf"
PROMPT_PATH = "input.json"


# ── PARSERS ───────────────────────────────────────────────────────────────
def hex_to_rgba(value: str, alpha: int = 255) -> tuple:
    v = value.strip().lstrip("#")
    return (int(v[0:2],16), int(v[2:4],16), int(v[4:6],16), alpha)


def parse_color(value: str, alpha: int = 255) -> tuple:
    value = value.strip()
    if value.startswith("#"):
        return hex_to_rgba(value, alpha)
    parts = [int(x.strip()) for x in value.split(",")]
    return (parts[0], parts[1], parts[2], alpha)


def parse_value(key: str, raw: str) -> object:
    """Auto-cast value based on key name."""
    raw = raw.strip()
    if key in ("cache_icon", "icon_keep_colors"):
        return raw.lower() in ("true", "1", "yes")
    if key in ("icon_size", "icon_api_size", "icon_seed"):
        return int(raw)
    if key in ("icon_y", "title_y", "badge_y", "title_font_size", "subtitle_font_size"):
        return float(raw)
    if key in ("title_color", "badge_text_color", "icon_tint_color"):
        return parse_color(raw)
    if key == "badge_color":
        return parse_color(raw, alpha=235)
    return raw  # string (background, output)


def load_conf(path: str = PARAMS_PATH) -> dict:
    """Load params.conf → dict, falling back to DEFAULTS."""
    params = dict(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # support both = and : as separator
                sep = "=" if "=" in line else (":" if ":" in line else None)
                if not sep:
                    continue
                key, _, val = line.partition(sep)
                key = key.strip().lower().replace(" ", "_")
                val = val.strip()
                if key in DEFAULTS:
                    params[key] = parse_value(key, val)
        print(f"Params loaded from {path}")
    except FileNotFoundError:
        print(f"params.conf not found — using defaults")
    return params


def load_prompt(path: str = PROMPT_PATH) -> dict:
    """Load input.json → title, subtitle, icon_prompt."""
    import json, os
    defaults = {
        "title":       "My Banner",
        "subtitle":    "My subtitle",
        "icon_prompt": "A single padlock icon, flat modern illustration style, clean minimalistic, no shadows, no text, centered square composition",
    }
    if not os.path.exists(path):
        example = path.replace(".json", ".example.json")
        if os.path.exists(example):
            print(f"WARNING: {path} not found. Copy {example} to {path} and fill in your content.")
        else:
            print(f"WARNING: {path} not found. Create it based on input.example.json.")
        exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    defaults.update({k: v for k, v in data.items() if k in defaults})
    return defaults


def load_api_key(env_path: str = ".env") -> str:
    """Read POLLINATIONS_KEY from .env file."""
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == "POLLINATIONS_KEY":
                return val.strip()
    raise ValueError("POLLINATIONS_KEY not found in .env")


# ── STEP 1: Build enriched icon prompt ──────────────────────────────────
def build_icon_prompt(prompt: dict, params: dict) -> str:
    def to_hex(c): return "#{:02X}{:02X}{:02X}".format(c[0], c[1], c[2])
    bg      = "solid flat pure white background (#FFFFFF), no gradient, no texture, no shadows"
    palette = f"color palette: primary {to_hex(params['title_color'])}, accent {to_hex(params['badge_color'])}"
    return f"{prompt['icon_prompt'].rstrip('.')}. {bg}, {palette}."


# ── STEP 2: Generate icon via Pollinations ───────────────────────────────
def generate_icon(api_key: str, prompt: str, params: dict) -> Image.Image:
    print(f"Calling Pollinations API...")
    print(f"Icon prompt: {prompt}")
    response = requests.post(
        "https://gen.pollinations.ai/v1/images/generations",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "prompt": prompt,
            "model":  "flux",
            "width":  params["icon_api_size"],
            "height": params["icon_api_size"],
            "seed":   params["icon_seed"],
            "nologo": True,
            "n":      1,
        },
        timeout=120,
    )
    if response.status_code != 200:
        raise Exception(f"Pollinations error {response.status_code}: {response.text}")

    data = response.json()["data"][0]
    if "b64_json" in data:
        img_bytes = base64.b64decode(data["b64_json"])
    elif "url" in data:
        img_bytes = requests.get(data["url"], timeout=60).content
    else:
        raise Exception("No image data in response")

    icon = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    icon = icon.resize((params["icon_size"], params["icon_size"]), Image.LANCZOS)
    print(f"Icon received and resized to {params['icon_size']}px")
    return icon


# ── STEP 3: Flood fill background removal + anti-alias ───────────────────
def remove_background_flood(img: Image.Image, tolerance: int = 40) -> Image.Image:
    from collections import deque
    img = img.convert("RGBA")
    w, h = img.size
    pixels = img.load()

    seeds = [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]
    corner_colors = [pixels[sx,sy][:3] for sx,sy in seeds]
    bg = tuple(sum(c[i] for c in corner_colors)//4 for i in range(3))
    print(f"Detected background: rgb{bg}")

    visited = set()
    queue = deque(seeds)
    visited.update(seeds)

    def dist(c1, c2): return max(abs(c1[i]-c2[i]) for i in range(3))

    while queue:
        x, y = queue.popleft()
        px = pixels[x, y]
        if dist(px[:3], bg) <= tolerance:
            pixels[x, y] = (px[0], px[1], px[2], 0)
            for nx, ny in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
                if 0 <= nx < w and 0 <= ny < h and (nx,ny) not in visited:
                    visited.add((nx,ny))
                    queue.append((nx,ny))

    print("Flood fill done")

    # smooth edges — blur alpha only on edge pixels
    r, g, b, a = img.split()
    a_blur = a.filter(ImageFilter.GaussianBlur(radius=1.2))
    ad  = list(a.tobytes())
    abd = list(a_blur.tobytes())
    a = Image.frombytes('L', a.size, bytes([abd[i] if 0 < ad[i] < 255 else ad[i] for i in range(len(ad))]))
    print("Edge anti-aliasing applied")
    return Image.merge('RGBA', (r, g, b, a))


# ── STEP 4: Draw smooth anti-aliased badge ───────────────────────────────
def draw_badge(overlay, cx, cy, w, h, color):
    scale = 4
    big = Image.new("RGBA", (w*scale, h*scale), (0,0,0,0))
    ImageDraw.Draw(big).rounded_rectangle(
        [0, 0, w*scale-1, h*scale-1], radius=(h//2)*scale, fill=color)
    sm = big.resize((w, h), Image.LANCZOS)
    overlay.paste(sm, (cx-w//2, cy-h//2), sm)


# ── STEP 5: Draw smooth anti-aliased text ────────────────────────────────
def draw_text_smooth(overlay, text, font_size, cx, cy, color):
    scale = 3
    try:
        fb = ImageFont.truetype(FONT_BOLD, font_size*scale)
        fr = ImageFont.truetype(FONT_BOLD, font_size)
    except:
        fb = fr = ImageFont.load_default()

    dummy = ImageDraw.Draw(Image.new("RGBA",(1,1)))
    tb     = dummy.textbbox((0,0), text, font=fr)
    tb_big = dummy.textbbox((0,0), text, font=fb)
    tw, th = tb[2]-tb[0], tb[3]-tb[1]
    twb, thb = tb_big[2]-tb_big[0], tb_big[3]-tb_big[1]

    pad = 20
    canvas = Image.new("RGBA", (twb+pad*2, thb+pad*2), (0,0,0,0))
    ImageDraw.Draw(canvas).text((pad, pad-tb_big[1]), text, font=fb, fill=color)
    small = canvas.resize(((twb+pad*2)//scale, (thb+pad*2)//scale), Image.LANCZOS)
    overlay.paste(small, (cx-tw//2-pad//scale, cy-th//2-pad//scale), small)


# ── STEP 6: Composite banner ──────────────────────────────────────────────
def compose(icon: Image.Image, prompt: dict, params: dict) -> None:
    bg = Image.open(params["background"]).convert("RGBA")
    W, H = bg.size
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    draw    = ImageDraw.Draw(overlay)
    cx      = W // 2

    # optionally tint icon
    if not params.get("icon_keep_colors", True):
        r, g, b, _ = params["icon_tint_color"]
        tinted = Image.new("RGBA", icon.size, (r,g,b,255))
        tinted.putalpha(icon.getchannel("A"))
        icon = tinted

    # icon
    overlay.paste(icon,
                  (cx - icon.size[0]//2, int(H*params["icon_y"]) - icon.size[1]//2),
                  icon)

    # title
    draw_text_smooth(overlay, prompt["title"],
                     int(H*params["title_font_size"]),
                     cx, int(H*params["title_y"]),
                     params["title_color"])

    # badge
    font_sub = ImageFont.truetype(FONT_BOLD, int(H*params["subtitle_font_size"]))
    sb = draw.textbbox((0,0), prompt["subtitle"], font=font_sub)
    sw, sh   = sb[2]-sb[0], sb[3]-sb[1]
    px, py   = int(W*0.050), int(H*0.032)
    bw, bh   = sw+px*2, sh+py*2
    by       = int(H*params["badge_y"])
    draw_badge(overlay, cx, by, bw, bh, params["badge_color"])
    draw.text((cx-sw//2, by-bh//2+py-sb[1]),
              prompt["subtitle"], font=font_sub, fill=params["badge_text_color"])

    result = Image.alpha_composite(bg, overlay).convert("RGB")
    ext = params["output"].rsplit(".", 1)[-1].lower()
    if ext == "webp":
        result.save(params["output"], format="WEBP", quality=90, method=6)
    elif ext in ("jpg", "jpeg"):
        result.save(params["output"], format="JPEG", quality=95)
    else:
        result.save(params["output"], format="PNG")
    print(f"Banner saved → {params['output']} ({W}×{H})")


# ── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    # parse --icon=<path> argument
    custom_icon_path = None
    for arg in sys.argv[1:]:
        if arg.startswith("--icon="):
            custom_icon_path = arg.split("=", 1)[1]
            break

    params = load_conf(PARAMS_PATH)
    prompt = load_prompt(PROMPT_PATH)

    print(f"Title   : {prompt['title']}")
    print(f"Subtitle: {prompt['subtitle']}")
    print()

    # check background exists before doing anything
    import os
    if not os.path.exists(params["background"]):
        print(f"\nWARNING: Background image not found: '{params['background']}'")
        print(f"   Add your background image or update 'background' in params.conf\n")
        exit(1)

    if custom_icon_path:
        # use custom icon — skip Pollinations API call
        print(f"Using custom icon: {custom_icon_path}")
        icon_raw = Image.open(custom_icon_path).convert("RGBA")
        icon_raw = icon_raw.resize(
            (params["icon_size"], params["icon_size"]), Image.LANCZOS)
    else:
        # Step 1 — build prompt
        icon_prompt = build_icon_prompt(prompt, params)

        # Step 2 — call Pollinations API
        api_key  = load_api_key()
        icon_raw = generate_icon(api_key, icon_prompt, params)

        # Step 3 — save raw icon if cache enabled
        if params["cache_icon"]:
            icon_filename = f"icon_{int(time.time())}.png"
            icon_raw.save(icon_filename)
            print(f"Icon cached → {icon_filename}")

    # Step 4 — remove background + anti-alias
    icon_clean = remove_background_flood(icon_raw)

    # Step 5 — composite
    compose(icon_clean, prompt, params)
