"""Inspection report from Gemma running in local Ollama. Photos go to
127.0.0.1 only. Without Ollama the report is a plain template, and says so.
"""
import json
import os
import urllib.request

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("THUD_GEMMA", "gemma3:4b")

# Every fact (summary, tile list, photo count) is written by code, never by the model: a 1B model
# swaps tiles and numbers even when handed them. Gemma writes only advice and photo descriptions.
STEPS = """You advise after a floor inspection by acoustic tap test. Write two to four markdown
bullets of practical next steps for the owner or inspector, given the facts. Do not name tiles, give
numbers or mention photos. Only the bullets, no heading, no preamble."""

PHOTOS = """You describe photos of a tiled floor for an inspection report. For each photo, one bullet:
"Photo N:" then the visible defects (cracks, gaps, stains, lippage, loose grout) or "nothing
visibly wrong". Only describe what is in the photo. No preamble."""


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


def tiles_md(f):
    out = [f'- {t["tile"]}: {round(t["p_hollow"] * 100)}% likely hollow' for t in f["flagged_hollow"]]
    if f["confirmed_by_inspector"]["hollow"]:
        out.append(f'- Confirmed hollow by the inspector: {", ".join(f["confirmed_by_inspector"]["hollow"])}')
    return ["## Flagged tiles"] + (out or ["- None"])


def summary(f):
    return (f'{f["room"] or "Room"}: {f["tiles_tapped"]} tiles tapped on a {f["grid"]} grid. '
            f'{len(f["flagged_hollow"])} flagged as likely hollow, '
            f'{len(f["confirmed_by_inspector"]["hollow"])} confirmed hollow by hand.')


def assemble(f, photos, steps):
    return "\n".join(["## Summary", summary(f), "", *tiles_md(f), "", "## Photo findings", photos, "",
                      "## Recommended next steps", steps])


def template(f, n_photos):
    return assemble(f, f"{n_photos} photo(s) attached. Not described: the local Gemma model was not running.",
                    "- Re-tap flagged tiles and confirm by pressing on the edges.\n"
                    "- Ask for flagged tiles to be lifted and re-bedded before signing off.")


def _chat(system, content, images, timeout):
    msg = {"role": "user", "content": content}
    if images:
        msg["images"] = images
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps({
        "model": MODEL, "stream": False, "options": {"temperature": 0.2},
        "messages": [{"role": "system", "content": system}, msg]}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"].strip()


def write(insp, photos_b64, timeout=600):
    """Returns (markdown, model_used). photos_b64: base64 JPEG/PNG strings."""
    f = facts(insp)
    try:
        steps = _chat(STEPS, f"Facts:\n{json.dumps(f, indent=1)}", None, timeout)
        photos = (_chat(PHOTOS, f"{len(photos_b64)} photo(s), in order.", photos_b64, timeout)
                  if photos_b64 else "No photos attached.")
    except Exception:
        return template(f, len(photos_b64)), "template (Ollama not reachable)"
    return assemble(f, photos, steps), MODEL
