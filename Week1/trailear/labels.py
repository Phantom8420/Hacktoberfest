"""Split Perch 2.0's 14,795 labels into what the receipt cares about.

Species are binomials. The 198 FSD50k classes are everything else, and I
sorted those by hand into nature / human-made / ambiguous.
"""
from pathlib import Path

LABEL_FILE = Path(__file__).resolve().parent.parent / "data" / "perch_labels.csv"

NATURE = {
    "Rain", "Raindrop", "Stream", "Thunder", "Thunderstorm", "Waves_and_surf",
    "Ocean", "Wind", "Water", "Trickle_and_dribble", "Splash_and_splatter",
}
WILD = {
    "Frog", "Insect", "Cricket", "Chirp_and_tweet", "Crow", "Fowl",
    "Gull_and_seagull", "Wild_animals", "Animal",
}
# neither proof of grass nor proof of a room
AMBIGUOUS = {
    "Dog", "Bark", "Cat", "Meow", "Purr", "Domestic_animals_and_pets",
    "Livestock_and_farm_animals_and_working_animals", "Chicken_and_rooster",
    "Breathing", "Respiratory_sounds", "Walk_and_footsteps", "Run", "Fire",
    "Crackle", "Crack", "Hiss", "Buzz", "Squeak", "Screech", "Growling",
    "Boom", "Rattle", "Tick", "Drip", "Whoosh_and_swoosh_and_swish", "Hands",
    "Wood", "Gurgling", "Liquid", "Pour", "Thump_and_thud", "Scratching_(performance_technique)",
}

BIRD_LIKE_KINGDOM = "species"


def load_labels(path=LABEL_FILE):
    rows = [l.rstrip("\r\n") for l in open(path, encoding="utf8")][1:]
    assert len(rows) == 14795, len(rows)
    return rows


def group_of(label):
    if " " in label:
        return "species"
    if label in WILD:
        return "wild"
    if label in NATURE:
        return "nature"
    if label in AMBIGUOUS:
        return "ambiguous"
    return "human"


def group_indices(labels):
    g = {}
    for i, l in enumerate(labels):
        g.setdefault(group_of(l), []).append(i)
    return {k: __import__("numpy").array(v) for k, v in g.items()}
