"""Inspection report from Gemma running in local Ollama. Photos go to
127.0.0.1 only. Without Ollama the report is a plain template, and says so.
"""
import json
import os
import urllib.request

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("THUD_GEMMA", "gemma3:4b")

SYSTEM = """You write floor inspection reports. You get a tile map from an acoustic tap test and
optional photos. Rules: only state what the data or photos show; give tile positions as
row-column (A1 is top-left); say how confident the tap test is for each flagged tile; describe
visible defects in photos plainly (cracks, gaps, stains, lippage) and say when a photo shows nothing
wrong. Sections: Summary, Flagged tiles, Photo findings, Recommended next steps. Plain markdown, no
preamble, under 350 words."""


def tile_name(r, c):
    return f"{chr(65 + r)}{c + 1}"


def facts(insp):
    tiles = insp["tiles"]
    flagged = sorted((t for t in tiles if t.get("p_hollow") is not None and t["p_hollow"] >= 0.5),
                     key=lambda t: -t["p_hollow"])
    return {
        "site": insp.get("site", ""),
        "room": insp.get("room", ""),
        "grid": f'{insp["rows"]} rows x {insp["cols"]} columns',
        "tiles_tapped": sum(1 for t in tiles if t.get("tapped")),
        "confirmed_by_inspector": {
            "solid": [tile_name(t["r"], t["c"]) for t in tiles if t.get("label") == "solid"],
            "hollow": [tile_name(t["r"], t["c"]) for t in tiles if t.get("label") == "hollow"],
        },
        "flagged_hollow": [{"tile": tile_name(t["r"], t["c"]), "p_hollow": t["p_hollow"]} for t in flagged],
        "model": insp.get("backend", "none"),
    }


def template(f, n_photos):
    lines = [f"## Summary", f'{f["room"] or "Room"}: {f["tiles_tapped"]} tiles tapped on a {f["grid"]} grid. '
             f'{len(f["flagged_hollow"])} flagged as likely hollow.', "", "## Flagged tiles"]
    flagged = [f'- {t["tile"]}: {round(t["p_hollow"] * 100)}% likely hollow' for t in f["flagged_hollow"]]
    if f["confirmed_by_inspector"]["hollow"]:
        flagged.append(f'- Confirmed hollow by the inspector: {", ".join(f["confirmed_by_inspector"]["hollow"])}')
    lines += flagged or ["- None"]
    lines += ["", "## Photo findings",
              f"{n_photos} photo(s) attached. Not described: the local Gemma model was not running.",
              "", "## Recommended next steps", "- Re-tap flagged tiles and confirm by pressing on the edges.",
              "- Ask for flagged tiles to be lifted and re-bedded before signing off."]
    return "\n".join(lines)


def write(insp, photos_b64, timeout=600):
    """Returns (markdown, model_used). photos_b64: base64 JPEG/PNG strings."""
    f = facts(insp)
    msg = {"role": "user", "content": f"Tile map facts:\n{json.dumps(f, indent=1)}\n\n{len(photos_b64)} photo(s) attached."}
    if photos_b64:
        msg["images"] = photos_b64
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps({
        "model": MODEL, "stream": False, "options": {"temperature": 0.2},
        "messages": [{"role": "system", "content": SYSTEM}, msg]}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["message"]["content"].strip(), MODEL
    except Exception:
        return template(f, len(photos_b64)), "template (Ollama not reachable)"
