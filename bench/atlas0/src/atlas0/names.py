"""Names are made of sand (design §2.2).

Every symbol name is two or three *stems* from one fixed vocabulary
joined with ``_``; an absent name is built the same way, so nothing in
its pieces says whether it exists. Distances between names are measured
on stems, never characters (§6.5): one stem swapped or one stem
appended is distance 1.

The vocabulary is fixed here and not per seed, so that the same stem
has the same identity across worlds; which stems a class uses, and in
what order, is the seed's.
"""

from __future__ import annotations

import random

# 300 stems. Code-shaped, one piece each, none a word the statement or
# query templates use (those words tokenize on their own under B1 and
# must not collide with a stem), none a prefix the generator reserves
# (``mod``, ``test``).
STEMS: tuple[str, ...] = tuple("""
range join merge lane site span node edge graph tier fact rule scope bind
slot hole fill trace read write emit parse walk scan probe cell unit arm
seed hash key ring pool heap stack queue list map set tree leaf root
branch fork twig trunk bark seam weld rivet bolt nut gear cog axle wheel
hub spoke rim tyre brake clutch shaft pump valve pipe duct vent flue grate
mesh net web knot loop coil spring lever cam pin peg hook latch hinge
clasp buckle strap belt cord wire fibre thread yarn cloth felt silk wool linen
weave plait braid twist fold crease pleat tuck hem cuff seal cap lid plug
stub cork bung stopper gasket washer shim wedge chock block brick tile slab plank
beam joist rafter lintel sill jamb frame sash pane glass lens prism mirror shade
blind screen filter sieve funnel spout nozzle jet spray mist drip leak flood surge
tide wave ripple eddy swirl vortex drift wind gust breeze draft chill frost snow
hail sleet rain cloud fog haze smoke ash ember flame spark flash glow gleam
ray flare torch lamp bulb wick fuse cable socket outlet switch dial knob toggle
tongs crank pedal treadle rung ladder stair step ramp slope bank ridge crest peak
summit pass gap notch cleft rift chasm gorge canyon basin bowl dish plate tray
shelf rack hanger bracket clamp vice anvil hammer mallet chisel gouge awl drill bit
auger rasp spool plane saw blade tooth cutter shear snip clip crimp punch stamp
press roll mill lathe grinder polish buff wax gloss stain tint dye pigment paint
brush roller pad sponge swab wipe rag mop broom dust lint fluff pile bobbin
batch lot bundle sheaf bale crate carton box bin tub vat drum keg cask
barrel flask vial phial ampoule ladle
""".split())

assert len(STEMS) == 300, len(STEMS)
assert len(set(STEMS)) == 300, "stem vocabulary has a duplicate"


def stem_distance(a: list[str], b: list[str]) -> int:
    """Levenshtein distance between two stem sequences."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, sa in enumerate(a, 1):
        cur = [i]
        for j, sb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (sa != sb)))
        prev = cur
    return prev[-1]


def split_name(name: str) -> list[str]:
    """A symbol name back into its stems."""
    return name.split("_")


def join_name(stems: list[str]) -> str:
    return "_".join(stems)


class StemCycle:
    """Draws stems so that a class uses every stem equally often.

    A seeded permutation of the vocabulary is consumed in order and
    reshuffled when exhausted; after ``k`` draws every stem has been
    drawn ``floor(k/300)`` or ``ceil(k/300)`` times. This is what makes
    stem frequency balanced across classes by construction (§6.2's
    check on **W**) rather than by rejection.
    """

    def __init__(self, seed: str):
        self._rng = random.Random(seed)
        self._deck: list[str] = []

    def draw(self, avoid: set[str] = frozenset()) -> str:
        """Next stem not in ``avoid``; a skipped stem is put back on top."""
        skipped: list[str] = []
        while True:
            if not self._deck:
                self._deck = list(STEMS)
                self._rng.shuffle(self._deck)
            s = self._deck.pop()
            if s in avoid:
                skipped.append(s)
                continue
            self._deck.extend(reversed(skipped))
            return s


class NameIndex:
    """Real and absent names indexed by stem, for fast nearest-name queries.

    ``within(stems, d)`` returns every indexed name at stem distance
    ``<= d``. Two names within distance 2 of each other share at least
    one stem when either has three stems or fewer, which is every name
    here, so the candidates are the union of the per-stem buckets.
    """

    def __init__(self):
        self._by_stem: dict[str, set[str]] = {}
        self._names: set[str] = set()

    def add(self, name: str) -> None:
        self._names.add(name)
        for s in split_name(name):
            self._by_stem.setdefault(s, set()).add(name)

    def __contains__(self, name: str) -> bool:
        return name in self._names

    def __len__(self) -> int:
        return len(self._names)

    def within(self, stems: list[str], d: int) -> dict[str, int]:
        """Indexed names at distance ``<= d`` from ``stems`` → their distance."""
        seen: set[str] = set()
        out: dict[str, int] = {}
        for s in stems:
            for name in self._by_stem.get(s, ()):
                if name in seen:
                    continue
                seen.add(name)
                dist = stem_distance(stems, split_name(name))
                if dist <= d:
                    out[name] = dist
        return out

    def nearest(self, stems: list[str], exclude: str | None = None) -> tuple[str | None, int]:
        """The nearest indexed name (ties broken by name) and its distance.

        Names sharing no stem are at distance ``max(len)`` ≥ 2; if no
        name shares a stem the nearest is reported as ``None`` at that
        floor distance.
        """
        best: tuple[int, str] | None = None
        for s in stems:
            for name in self._by_stem.get(s, ()):
                if name == exclude:
                    continue
                dist = stem_distance(stems, split_name(name))
                cand = (dist, name)
                if best is None or cand < best:
                    best = cand
        if best is None:
            return None, max(len(stems), 2)
        return best[1], best[0]
