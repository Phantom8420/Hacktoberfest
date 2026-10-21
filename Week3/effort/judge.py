"""Did it actually get tidier? Two independent checks, and "unclear" when they disagree.

1. Gemma compares before and after, asked twice with the photos swapped, because models
   lean towards whichever photo comes first. Only an answer that survives the swap counts.
2. Gemma lists the items again on the after photo; whatever is gone counts as removed.
"""
import difflib
import io

from PIL import Image, ImageDraw, ImageFont

from . import gemma, see

SCHEMA = {"type": "object", "required": ["tidier", "margin"],
          "properties": {"tidier": {"type": "string", "enum": ["A", "B", "same"]},
                         "margin": {"type": "integer"}}}

PROMPT = """These are two photos of a room, labelled A (left) and B (right).
Which shows the tidier room? Answer "same" if you can't see a real difference.
margin: 1 = slightly tidier, 2 = clearly tidier, 3 = much tidier (0 if same)."""


def side_by_side(a, b, height=640):
    """One image, A left and B right, so the model can't mix up which photo is which."""
    imgs = [Image.open(io.BytesIO(x)).convert("RGB") for x in (a, b)]
    imgs = [i.resize((round(i.width * height / i.height), height)) for i in imgs]
    out = Image.new("RGB", (imgs[0].width + imgs[1].width + 16, height), "white")
    out.paste(imgs[0], (0, 0))
    out.paste(imgs[1], (imgs[0].width + 16, 0))
    d = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=56)
    for x, label in ((12, "A"), (imgs[0].width + 28, "B")):
        d.rectangle((x - 4, 8, x + 48, 76), fill="black")
        d.text((x + 6, 10), label, fill="white", font=font)
    buf = io.BytesIO()
    out.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def compare(before, after):
    """{"verdict": "tidier" | "messier" | "same" | "unclear", "margin", "raw"} from both orders."""
    first = gemma.chat(PROMPT, [side_by_side(before, after)], schema=SCHEMA)   # after is B
    second = gemma.chat(PROMPT, [side_by_side(after, before)], schema=SCHEMA)  # after is A
    flip = {"A": "B", "B": "A", "same": "same"}
    a1, a2 = first.get("tidier"), flip.get(second.get("tidier"))
    raw = [first, second]
    if a1 != a2:
        return {"verdict": "unclear", "margin": 0, "raw": raw}
    verdict = {"B": "tidier", "A": "messier", "same": "same"}[a1]
    margin = 0 if verdict == "same" else min(int(first.get("margin", 1)), int(second.get("margin", 1)))
    return {"verdict": verdict, "margin": max(margin, 0), "raw": raw}


def same_item(x, y):
    return x["zone"] == y["zone"] and difflib.SequenceMatcher(None, x["what"], y["what"]).ratio() >= 0.6


def removed(before_items, after_items):
    """Items from before with no match after."""
    return [b for b in before_items if not any(same_item(b, a) for a in after_items)]


def verdict(before, after, before_items):
    cmp = compare(before, after)
    after_items = see.look(after)
    gone = removed(before_items, after_items)
    total = sum(i["mess"] for i in before_items) or 1
    share = sum(i["mess"] for i in gone) / total
    agree = (cmp["verdict"] == "tidier") == (share > 0)
    return {**cmp, "items_before": len(before_items), "items_after": len(after_items),
            "gone": [g["id"] for g in gone], "mess_removed": round(share, 3) if agree else None,
            "after_items": after_items}
