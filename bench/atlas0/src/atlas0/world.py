"""The world (design §2): an authored graph with the shape of a code graph.

``generate(seed, config)`` builds it and ``write`` lays it out as files;
the same seed gives the same bytes (§2.6). Nothing here is learned: the
classes, the mention budgets, the absences and the arms are all
functions of the seed, and every choice is made through a stage-named
``random.Random`` so a later stage cannot disturb an earlier one.

What is authored, in order:

1. **Entities** — modules ``mod_<stem>``, tests ``test_<stem>_<stem>``,
   symbols of two or three stems (§2.2), every class drawing its stems
   from its own balanced cycle.
2. **Classes and budgets** (§2.3) — ``dense-real`` (24–40 statements),
   ``sparse-real`` (exactly 1 or 2), and a *mid* background (3–23) that
   is real but unclassed, so that density is a continuum whose tails
   are the two classed rows and the module shape has mass to live on.
   The design's ``n ≈ 4,000`` symbols is read as the three together.
3. **Facts** — one ``defined_in`` per symbol (withheld for the
   module-inference subset, §6.5), ``reached_by`` from tests over one or
   two modules, and ``calls`` filled in against the budgets, intra-module
   with probability 0.7. A statement mentions every symbol in it, so
   the budget is consumed jointly; a symbol left short at the end
   re-renders one of its facts through another template ("across
   templates"). ``Config.renderings`` renders every fact through that
   many distinct templates from the start — the paraphrase
   augmentation that knowledge-extraction work finds necessary for a
   fact stored from statements to be answerable as a question — while
   a fact touching a sparse-real symbol is rendered once, so that
   class stays what the design says it is.
4. **Absences** — ``absent-near`` is one stem swapped or one stem
   appended to a dense-real name (stem distance exactly 1, and that
   base the only real name within 1); ``absent-far`` is a fresh
   recombination at distance ≥ 2 from every real name. The design's
   "edit distance 1–2" is read as distance 1: at this vocabulary a
   random three-stem name is within distance 2 of some real name with
   probability near one, so distance 2 cannot separate near from far.
   Names are three or four stems, not two or three: with 4,000 real
   names over 300 stems every two-stem name has about thirteen real
   neighbours at distance 1, so a two-stem absent name can be neither
   near (no unique base) nor far. Near bases are chosen to keep the
   class's stem counts level. Each class is split half trained / half
   held-out (§2.3).
5. **Queries** (§2.5) — for dense and mid symbols a seeded half is
   *QA-trained* (every fact also rendered as a question/answer pair in
   the corpus) and the other half *QA-held-out* (statements only); every
   sparse-real symbol is QA-held-out, so its one or two mentions are
   statements and nothing else. The primary evaluation asks ``Where is
   X defined?`` of every class — the one query every real symbol can
   answer uniquely, so the probe cannot read the class off the question.
6. **Arms** (§4) — the same statements and the same QA in all four;
   ``phrase`` adds ``UNDEFINED``-target queries for trained-absent names,
   ``lived`` adds written absences for them, ``lived+phrase`` both. A
   sparse-real symbol never carries an ``UNDEFINED`` target anywhere.

**v1 (the step record's items; 2026-09-05, night).** Each is one
``Config`` field, off by default, so a v1 world is the v0 world with the
same entities, facts and absences (every stage's random stream is keyed
as before) and its own hash:

- ``relation_absence`` — the lived arms also carry *relation-absence*
  (§2.4's v1 extension) for real dense and mid symbols: written lines
  for a symbol no test reaches or that calls nothing, and, for the
  QA-trained ones, the question of that relation answered ``UNDEFINED``
  — the absence-bearing query the v0 lived arm lacked, on a relation of
  a real symbol, never the existence of an absent name (that stays the
  phrase arm's target). Sparse-real symbols carry none of it (§2.3);
  the secondary eval then asks the empty relation of every real symbol,
  sparse ones included, whose gold act is ``UNDEFINED``.
- ``context_qa_p`` — that fraction of the training QA lines is packed
  with a statement of its own fact before the question, so that a
  preceding line ever bears on a question and §6.4's curve has
  something to measure.
- ``query_holdout`` — training QA is phrased through three query
  phrasings per kind and every eval prompt through a fourth the block
  never read (§7's template hold-out); ``eval/primary_seen.jsonl`` asks
  the same items in the first phrasing as the control.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .names import NameIndex, StemCycle, join_name, split_name, stem_distance

VERSION = "v0"

CLASSES = ("dense-real", "sparse-real", "absent-near", "absent-far")
ARMS = ("none", "phrase", "lived", "lived+phrase")
QUERY_KINDS = ("defined_in", "calls", "reached_by")

# Statement templates, 5 per relation (§2.1: 4–6). Index 0 of each is the
# canonical rendering used when a statement is put in context (§6.4).
TEMPLATES: dict[str, tuple[str, ...]] = {
    "defined_in": (
        "{s} is defined in {m}.",
        "The definition of {s} lives in {m}.",
        "{m} defines {s}.",
        "lookup({s}) → {m}.",
        "You will find {s} inside {m}.",
    ),
    "calls": (
        "{a} calls {b}.",
        "Inside {a} there is a call to {b}.",
        "{b} is called from {a}.",
        "A call from {a} reaches {b}.",
        "{a} invokes {b}.",
    ),
    "reached_by": (
        "{t} reaches {s}.",
        "{s} is exercised by {t}.",
        "Running {t} executes {s}.",
        "{t} covers {s}.",
        "{s} is reached by {t}.",
    ),
}

# Written absences (§2.4), existence-only in v0.
NEGATIVE_TEMPLATES: tuple[str, ...] = (
    "lookup({x}) → undefined.",
    "{x} is not defined in any module.",
    "No test reaches {x}.",
    "There is no symbol named {x}.",
    "Nothing calls {x}; it does not exist.",
)

# Relation-absence (§2.4's v1 extension): a real symbol no test reaches, or
# that calls nothing. The first reached_by line is the same sentence the
# existence absences use, on purpose: in a v1 lived corpus it is no longer
# a sentence only absent names get.
RELATION_ABSENCE_TEMPLATES: dict[str, tuple[str, ...]] = {
    "reached_by": (
        "No test reaches {x}.",
        "{x} is reached by no test.",
        "Nothing exercises {x}.",
    ),
    "calls": (
        "{x} calls nothing.",
        "There is no call from {x}.",
        "{x} invokes nothing.",
    ),
}

# Query phrasings per kind. Index 0 is v0's (the only one used unless
# ``Config.query_holdout``); under hold-out the first three are trained
# and the fourth is met only at evaluation.
QUERY_PHRASINGS: dict[str, tuple[str, ...]] = {
    "defined_in": ("Where is {x} defined?", "Which module defines {x}?", "In what module is {x} defined?",
                   "Where does {x} live?"),
    "calls": ("What does {x} call?", "Which symbol does {x} call?", "Name a callee of {x}.",
              "What is called from {x}?"),
    "reached_by": ("What reaches {x}?", "Which test reaches {x}?", "Name a test that covers {x}.",
                   "What exercises {x}?"),
}
QUERY_TEMPLATES: dict[str, str] = {k: v[0] for k, v in QUERY_PHRASINGS.items()}
TRAIN_PHRASINGS = (0, 1, 2)
HELD_OUT_PHRASING = 3

V1_FIELDS = ("relation_absence", "context_qa_p", "query_holdout")


@dataclass(frozen=True)
class Config:
    """The world's sizes. ``full()`` is the design's; ``tiny()`` is for tests.

    The three v1 fields are off by default; ``variant()`` names what is on.
    """

    modules: int = 40
    tests: int = 800
    dense: int = 1200
    sparse: int = 1200
    mid: int = 1600
    near: int = 600
    far: int = 600
    module_infer: int = 200       # mid symbols whose defined_in is withheld (§6.5)
    intra_module_p: float = 0.7
    dense_mentions: tuple[int, int] = (24, 40)
    mid_mentions: tuple[int, int] = (3, 23)
    test_symbols: tuple[int, int] = (2, 4)
    negative_lines: int = 2       # written absences per trained-absent name
    inversion_items: int = 200    # per §6.4 split
    name_stems: tuple[int, ...] = (3, 4)   # stems per name, cycled; see §2.2's note below
    renderings: int = 3           # templates each fact is rendered through ("across templates", §2.3);
                                  # a fact mentioning a sparse-real symbol is rendered once whatever this says
    # v1 (each off = v0)
    relation_absence: bool = False   # lived arms: relation-absence lines + UNDEFINED pairs on real symbols
    context_qa_p: float = 0.0        # share of training QA lines packed with a statement of their fact
    query_holdout: bool = False      # train three query phrasings, evaluate on a fourth

    @staticmethod
    def full() -> "Config":
        return Config()

    @staticmethod
    def tiny() -> "Config":
        return Config(modules=4, tests=40, dense=60, sparse=60, mid=80, near=30, far=30,
                      module_infer=10, inversion_items=12)

    VARIANTS = ("v0", "lived", "context", "holdout")

    def with_variant(self, name: str) -> "Config":
        """This config with one v1 item on: ``lived`` / ``context`` / ``holdout`` (``v0``: none)."""
        if name not in Config.VARIANTS:
            raise ValueError(f"unknown variant {name!r}; variants are {Config.VARIANTS}")
        on = {"v0": {}, "lived": {"relation_absence": True}, "context": {"context_qa_p": 0.5},
              "holdout": {"query_holdout": True}}[name]
        return Config(**{**asdict(self), **on})

    def variant(self) -> str:
        on = [f for f in V1_FIELDS if getattr(self, f) != getattr(Config, f)]
        return "v0" if not on else "v1:" + ",".join(on)

    def to_json(self) -> dict:
        """The config as hashed into ``world.json``: a v1 field appears only when on,
        so a v0 world's hash is what it was before the fields existed."""
        d = asdict(self)
        for f in V1_FIELDS:
            if d[f] == getattr(Config, f):
                del d[f]
        return d


@dataclass
class Symbol:
    name: str
    module: str
    cls: str                      # dense-real | sparse-real | mid
    target: int                   # mention budget
    defined_in_stated: bool       # False for the module-inference subset
    qa_split: str                 # train | eval
    nearest_dense: str | None = None
    nearest_dense_distance: int = 0


@dataclass
class Absent:
    name: str
    cls: str                      # absent-near | absent-far
    exposure: str                 # trained | held-out
    base: str | None              # near: the dense-real it was made from
    nearest_dense: str | None
    nearest_dense_distance: int


@dataclass
class Fact:
    kind: str                     # defined_in | calls | reached_by
    args: tuple[str, ...]         # (s, m) | (a, b) | (t, s)
    template: int

    def render(self) -> str:
        t = TEMPLATES[self.kind][self.template]
        if self.kind == "defined_in":
            return t.format(s=self.args[0], m=self.args[1])
        if self.kind == "calls":
            return t.format(a=self.args[0], b=self.args[1])
        return t.format(t=self.args[0], s=self.args[1])

    def mentions(self) -> tuple[str, ...]:
        """The symbol names this statement mentions (modules and tests are not symbols)."""
        if self.kind == "defined_in":
            return (self.args[0],)
        if self.kind == "calls":
            return self.args
        return (self.args[1],)


@dataclass
class World:
    seed: int
    config: Config
    modules: list[str]
    tests: list[str]
    symbols: list[Symbol]
    absents: list[Absent]
    facts: list[Fact]
    version: str = VERSION
    _by_name: dict[str, Symbol] = field(default_factory=dict, repr=False)
    _facts_index: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._by_name = {s.name: s for s in self.symbols}
        self._facts_index = {}

    def symbol(self, name: str) -> Symbol:
        return self._by_name[name]

    def statements(self) -> list[str]:
        return [f.render() for f in self.facts]

    def mention_counts(self) -> dict[str, int]:
        """Statements mentioning each symbol, from the facts (the check recounts from text)."""
        counts = {s.name: 0 for s in self.symbols}
        for f in self.facts:
            for n in f.mentions():
                counts[n] += 1
        return counts

    def facts_of(self, name: str) -> dict[str, list[str]]:
        """A symbol's answers by query kind: its module, its callees, the tests reaching it."""
        if not self._facts_index:
            idx: dict[str, dict[str, list[str]]] = {}
            for f in self.facts:
                if f.kind == "defined_in":
                    subj, val = f.args[0], f.args[1]
                elif f.kind == "calls":
                    subj, val = f.args[0], f.args[1]
                else:
                    subj, val = f.args[1], f.args[0]
                lst = idx.setdefault(subj, {k: [] for k in QUERY_KINDS})[f.kind]
                if val not in lst:
                    lst.append(val)
            self._facts_index = idx
        return self._facts_index.get(name, {k: [] for k in QUERY_KINDS})

    def entities(self) -> dict[str, str]:
        """Every name the tokenizer treats as one entity (§7): kind by name."""
        ents = {m: "module" for m in self.modules}
        ents.update({t: "test" for t in self.tests})
        ents.update({s.name: "symbol" for s in self.symbols})
        ents.update({a.name: "absent" for a in self.absents})
        return ents

    def to_json(self) -> dict:
        return {
            "version": self.version,
            "seed": self.seed,
            "config": self.config.to_json(),
            "modules": self.modules,
            "tests": self.tests,
            "symbols": [asdict(s) for s in self.symbols],
            "absents": [asdict(a) for a in self.absents],
            "facts": [{"kind": f.kind, "args": list(f.args), "template": f.template} for f in self.facts],
        }

    @staticmethod
    def from_json(d: dict) -> "World":
        cfg = Config(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in d["config"].items()})
        return World(seed=d["seed"], config=cfg, modules=d["modules"], tests=d["tests"],
                     symbols=[Symbol(**s) for s in d["symbols"]],
                     absents=[Absent(**a) for a in d["absents"]],
                     facts=[Fact(f["kind"], tuple(f["args"]), f["template"]) for f in d["facts"]],
                     version=d["version"])


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rng(seed: int, stage: str) -> random.Random:
    return random.Random(f"atlas0:{VERSION}:{seed}:{stage}")


# ---------------------------------------------------------------- entities

def _make_names(n: int, cycle: StemCycle, taken: NameIndex, lengths: tuple[int, ...]) -> list[str]:
    """``n`` distinct symbol names, alternating the lengths, each stem distinct within a name."""
    out: list[str] = []
    i = 0
    while len(out) < n:
        k = lengths[i % len(lengths)]
        i += 1
        stems: list[str] = []
        while len(stems) < k:
            stems.append(cycle.draw(avoid=set(stems)))
        name = join_name(stems)
        if name in taken:
            continue
        taken.add(name)
        out.append(name)
    return out


def _make_modules(cfg: Config, seed: int) -> list[str]:
    cycle = StemCycle(f"atlas0:{VERSION}:{seed}:modules")
    used: set[str] = set()
    out = []
    while len(out) < cfg.modules:
        s = cycle.draw(avoid=used)
        used.add(s)
        out.append(f"mod_{s}")
    return out


def _make_tests(cfg: Config, seed: int) -> list[str]:
    cycle = StemCycle(f"atlas0:{VERSION}:{seed}:tests")
    out: list[str] = []
    seen: set[str] = set()
    while len(out) < cfg.tests:
        a = cycle.draw()
        b = cycle.draw(avoid={a})
        name = f"test_{a}_{b}"
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


# ---------------------------------------------------------------- facts

def _build_facts(cfg: Config, seed: int, symbols: list[Symbol], tests: list[str]) -> list[Fact]:
    module_of = {s.name: s.module for s in symbols}
    rng = _rng(seed, "facts")
    render = _rng(seed, "render")
    n_t = {k: len(v) for k, v in TEMPLATES.items()}
    remaining = {s.name: s.target for s in symbols}
    by_module: dict[str, list[str]] = {}
    for s in symbols:
        by_module.setdefault(s.module, []).append(s.name)
    facts: list[Fact] = []
    seen: set[tuple] = set()

    sparse = {s.name for s in symbols if s.cls == "sparse-real"}
    mention_of = {"defined_in": lambda a: (a[0],), "calls": lambda a: a, "reached_by": lambda a: (a[1],)}

    def add(kind: str, args: tuple[str, ...]) -> int:
        """Render a fact through ``renderings`` distinct templates, bounded by every
        mentioned symbol's remaining budget and by one for a sparse-real symbol;
        returns how many statements were written (each consumes one mention per symbol)."""
        names = mention_of[kind](args)
        k = cfg.renderings if not (set(names) & sparse) else 1
        k = max(1, min(k, *(remaining[n] for n in names)))
        ts = render.sample(range(n_t[kind]), k)
        for t in ts:
            facts.append(Fact(kind, args, t))
            seen.add((kind, args, t))
        return k

    # 1. defined_in — one per symbol unless withheld.
    for s in symbols:
        if s.defined_in_stated:
            remaining[s.name] -= add("defined_in", (s.name, s.module))

    def open_in(module: str, exclude: str | None = None) -> list[str]:
        return [n for n in by_module[module] if remaining[n] > 0 and n != exclude]

    # 2. reached_by — each test reaches 2–4 symbols in one or two modules.
    modules = sorted(by_module)
    for t in tests:
        k_mod = rng.choice((1, 2))
        mods = rng.sample(modules, k_mod)
        pool = [n for m in mods for n in open_in(m)]
        k = min(rng.randint(*cfg.test_symbols), len(pool))
        for name in rng.sample(pool, k):
            remaining[name] -= add("reached_by", (t, name))

    # 3. calls — until the budgets are spent.
    open_syms = [s.name for s in symbols if remaining[s.name] > 0]
    edges: set[tuple[str, str]] = set()
    misses = 0
    while len(open_syms) >= 2 and misses < 200:
        a = rng.choice(open_syms)
        a_mod = module_of[a]
        intra = rng.random() < cfg.intra_module_p
        order = (True, False) if intra else (False, True)
        b = None
        for want_intra in order:
            if want_intra:
                cands = [n for n in open_in(a_mod, exclude=a) if (a, n) not in edges]
            else:
                cands = [n for n in open_syms if module_of[n] != a_mod and (a, n) not in edges]
            if cands:
                b = rng.choice(cands)
                break
        if b is None:
            misses += 1
            continue
        misses = 0
        k = add("calls", (a, b))
        edges.add((a, b))
        for n in (a, b):
            remaining[n] -= k
        open_syms = [n for n in open_syms if remaining[n] > 0]

    # 4. filler — a symbol still short re-renders one of its facts through
    #    another template (each rendering is a distinct statement); when
    #    every template of every fact of its own is used, it gains a call
    #    to a dense-real symbol, which can absorb a mention over its target
    #    (the class criterion is ≥ 24, and the manifest reports the max).
    #    A fact that also mentions a sparse-real symbol is never re-rendered
    #    for its other side (that would give the sparse symbol a statement
    #    over its budget: seed 5 of v0 had one at six, found 2026-09-05 night).
    dense_names = [s.name for s in symbols if s.cls == "dense-real"]
    for s in symbols:
        while remaining[s.name] > 0:
            own = [f for f in facts if s.name in f.mentions() and not ((set(f.mentions()) - {s.name}) & sparse)]
            own.sort(key=lambda f: (len(f.mentions()), f.kind, f.args))
            choice = None
            for base in own:
                unused = [t for t in range(n_t[base.kind]) if (base.kind, base.args, t) not in seen]
                if unused:
                    choice = (base, rng.choice(unused))
                    break
            if choice is not None:
                base, t = choice
                facts.append(Fact(base.kind, base.args, t))
                seen.add((base.kind, base.args, t))
                for n in base.mentions():
                    remaining[n] -= 1
                continue
            same = [n for n in dense_names if module_of[n] == s.module and n != s.name and (s.name, n) not in edges]
            pool = same or [n for n in dense_names if n != s.name and (s.name, n) not in edges]
            if not pool:
                raise RuntimeError(f"cannot fill the budget of {s.name}: no dense-real symbol left to call")
            b = rng.choice(pool)
            k = add("calls", (s.name, b))
            edges.add((s.name, b))
            remaining[s.name] -= k
            remaining[b] -= k
    return facts


# ---------------------------------------------------------------- absences

def _make_absents(cfg: Config, seed: int, symbols: list[Symbol], real: NameIndex, dense: NameIndex) -> list[Absent]:
    rng = _rng(seed, "absent")
    taken = NameIndex()
    dense_names = [s.name for s in symbols if s.cls == "dense-real"]
    out: list[Absent] = []

    lengths = cfg.name_stems
    by_len: dict[int, list[str]] = {}
    for n in dense_names:
        by_len.setdefault(len(split_name(n)), []).append(n)
    stem_use: Counter = Counter()

    def pick_base(length: int) -> str:
        """The unused dense-real name of ``length`` whose stems are least used so far (ties by seed)."""
        pool = [n for n in by_len.get(length, ()) if n not in used_bases]
        if not pool:
            raise RuntimeError(f"no dense-real names of {length} stems left to build absent-near from")
        scored = [(sum(stem_use[st] for st in split_name(n)), rng.random(), n) for n in pool]
        return min(scored)[2]

    used_bases: set[str] = set()
    near_cycle = StemCycle(f"atlas0:{VERSION}:{seed}:near")
    i = 0
    while len([a for a in out if a.cls == "absent-near"]) < cfg.near:
        want = lengths[i % len(lengths)]
        i += 1
        # One stem swapped keeps the length; one stem appended reaches it from one shorter.
        if (want - 1) in lengths and by_len.get(want - 1) and (i // len(lengths)) % 2 == 1:
            op, base = "suffix", pick_base(want - 1)
        else:
            op, base = "swap", pick_base(want)
        stems = split_name(base)
        new = near_cycle.draw(avoid=set(stems))
        if op == "swap":
            pos = rng.randrange(len(stems))
            stems = stems[:pos] + [new] + stems[pos + 1:]
        else:
            stems = stems + [new]
        name = join_name(stems)
        if name in real or name in taken or real.within(stems, 1) != {base: 1}:
            continue
        used_bases.add(base)
        stem_use.update(stems)
        taken.add(name)
        out.append(Absent(name, "absent-near", "", base, base, 1))

    far_cycle = StemCycle(f"atlas0:{VERSION}:{seed}:far")
    i = 0
    while len([a for a in out if a.cls == "absent-far"]) < cfg.far:
        k = lengths[i % len(lengths)]
        i += 1
        stems: list[str] = []
        while len(stems) < k:
            stems.append(far_cycle.draw(avoid=set(stems)))
        name = join_name(stems)
        if name in real or name in taken or real.within(stems, 1):
            continue
        taken.add(name)
        nearest, dist = dense.nearest(stems)
        out.append(Absent(name, "absent-far", "", None, nearest, dist))

    # Exposure: half of each class trained, half held-out, by seed.
    for cls in ("absent-near", "absent-far"):
        group = [a for a in out if a.cls == cls]
        idx = list(range(len(group)))
        rng.shuffle(idx)
        half = len(group) // 2
        for j, k in enumerate(idx):
            group[k].exposure = "trained" if j < half else "held-out"
    return out


# ---------------------------------------------------------------- generate

def generate(seed: int, cfg: Config = Config()) -> World:
    """The world for ``seed`` under ``cfg``; the same inputs give the same world."""
    modules = _make_modules(cfg, seed)
    tests = _make_tests(cfg, seed)

    real = NameIndex()
    names = {
        "dense-real": _make_names(cfg.dense, StemCycle(f"atlas0:{VERSION}:{seed}:dense"), real, cfg.name_stems),
        "sparse-real": _make_names(cfg.sparse, StemCycle(f"atlas0:{VERSION}:{seed}:sparse"), real, cfg.name_stems),
        "mid": _make_names(cfg.mid, StemCycle(f"atlas0:{VERSION}:{seed}:mid"), real, cfg.name_stems),
    }
    rng = _rng(seed, "assign")
    order = [(cls, n) for cls in ("dense-real", "sparse-real", "mid") for n in names[cls]]
    rng.shuffle(order)
    symbols: list[Symbol] = []
    for i, (cls, n) in enumerate(order):
        if cls == "dense-real":
            target = rng.randint(*cfg.dense_mentions)
        elif cls == "mid":
            target = rng.randint(*cfg.mid_mentions)
        else:
            target = rng.choice((1, 2))
        symbols.append(Symbol(n, modules[i % len(modules)], cls, target, True, "eval"))
    # The module-inference subset: mid symbols with the defined_in withheld.
    mids = [s for s in symbols if s.cls == "mid"]
    for s in rng.sample(mids, cfg.module_infer):
        s.defined_in_stated = False
    # QA split: half of dense and of mid trained; sparse never; module-infer never.
    for cls in ("dense-real", "mid"):
        group = [s for s in symbols if s.cls == cls and s.defined_in_stated]
        for s in rng.sample(group, len(group) // 2):
            s.qa_split = "train"
    symbols.sort(key=lambda s: s.name)

    facts = _build_facts(cfg, seed, symbols, tests)

    dense = NameIndex()
    for s in symbols:
        if s.cls == "dense-real":
            dense.add(s.name)
    for s in symbols:
        s.nearest_dense, s.nearest_dense_distance = dense.nearest(split_name(s.name), exclude=s.name)
    absents = _make_absents(cfg, seed, symbols, real, dense)
    absents.sort(key=lambda a: a.name)
    return World(seed, cfg, modules, tests, symbols, absents, facts)


# ---------------------------------------------------------------- queries and corpora

def query_line(kind: str, name: str, phrasing: int = 0) -> str:
    return "Q: " + QUERY_PHRASINGS[kind][phrasing].format(x=name) + " A:"


def qa_line(kind: str, name: str, act: str, value: str | None = None, phrasing: int = 0, context: str = "") -> str:
    tail = f" {act}" + (f" {value}" if value else "")
    return context + query_line(kind, name, phrasing) + tail


def fact_for(kind: str, name: str, value: str, template: int) -> Fact:
    """The statement of (``name`` has ``value`` under ``kind``) through ``template``."""
    return Fact(kind, (value, name) if kind == "reached_by" else (name, value), template)


Pair = tuple[str, str, str, str | None]     # (kind, name, act, value)


def training_pairs(world: World) -> list[Pair]:
    """The QA-trained symbols' pairs: every fact, every kind, ``ANSWER`` its value.

    A pair whose answer is a sparse-real symbol is dropped, so that a
    sparse-real name occurs in the corpus exactly as often as its
    statements say (§2.3) and never in an answer position.
    """
    sparse = {s.name for s in world.symbols if s.cls == "sparse-real"}
    out: list[Pair] = []
    for s in world.symbols:
        if s.qa_split != "train":
            continue
        for kind, values in world.facts_of(s.name).items():
            for v in values:
                if v in sparse:
                    continue   # a sparse-real symbol is mentioned by its statements and nothing else
                out.append((kind, s.name, "ANSWER", v))
    return out


def render_pairs(world: World, pairs: list[Pair], stage: str, pack: bool = False) -> list[str]:
    """Pairs as corpus lines under the world's v1 settings.

    Under ``query_holdout`` each line takes one of the three trained
    phrasings by seed; with ``pack`` and ``context_qa_p`` that share of
    the lines is packed with a statement of the pair's own fact,
    rendered through a seeded template, before the question. Only the
    training QA of real facts packs — an ``UNDEFINED`` pair never does,
    so the phrase arm stays free of written absences. Off, this is v0's
    one line per pair.
    """
    cfg = world.config
    rng_p = _rng(world.seed, f"qa-phrasing:{stage}") if cfg.query_holdout else None
    rng_c = _rng(world.seed, f"qa-context:{stage}") if pack and cfg.context_qa_p > 0 else None
    out: list[str] = []
    for kind, name, act, value in pairs:
        phrasing = rng_p.choice(TRAIN_PHRASINGS) if rng_p else 0
        context = ""
        if rng_c and act == "ANSWER" and rng_c.random() < cfg.context_qa_p:
            context = fact_for(kind, name, value, rng_c.randrange(len(TEMPLATES[kind]))).render() + " "
        out.append(qa_line(kind, name, act, value, phrasing, context))
    return out


def training_qa(world: World) -> list[str]:
    """Question/answer lines for QA-trained symbols (every arm)."""
    return render_pairs(world, training_pairs(world), "train", pack=True)


def absent_qa(world: World) -> list[str]:
    """``UNDEFINED``-target queries for trained-absent names (the phrase arms)."""
    pairs: list[Pair] = [(kind, a.name, "UNDEFINED", None) for a in world.absents if a.exposure == "trained"
                         for kind in QUERY_KINDS]
    return render_pairs(world, pairs, "absent")


def negative_lines(world: World) -> list[str]:
    """Written absences for trained-absent names (the lived arms)."""
    rng = _rng(world.seed, "negative")
    out: list[str] = []
    for a in world.absents:
        if a.exposure != "trained":
            continue
        for t in rng.sample(range(len(NEGATIVE_TEMPLATES)), world.config.negative_lines):
            out.append(NEGATIVE_TEMPLATES[t].format(x=a.name))
    return out


def empty_relations(world: World) -> list[tuple[str, str]]:
    """(name, kind) for every real dense or mid symbol whose ``kind`` relation is empty.

    Sparse-real symbols are left out on purpose: their one or two
    statements are all the corpus says of them (§2.3), so their empty
    relations are asked at evaluation and never written.
    """
    out = []
    for s in world.symbols:
        if s.cls == "sparse-real":
            continue
        facts = world.facts_of(s.name)
        for kind in RELATION_ABSENCE_TEMPLATES:
            if not facts[kind]:
                out.append((s.name, kind))
    return out


def relation_absence_lines(world: World) -> list[str]:
    """Written relation-absences for real symbols (the lived arms, v1)."""
    if not world.config.relation_absence:
        return []
    rng = _rng(world.seed, "relation-absence")
    out: list[str] = []
    for name, kind in empty_relations(world):
        ts = RELATION_ABSENCE_TEMPLATES[kind]
        for t in rng.sample(range(len(ts)), min(world.config.negative_lines, len(ts))):
            out.append(ts[t].format(x=name))
    return out


def relation_absence_pairs(world: World) -> list[Pair]:
    """The empty relations of QA-trained symbols, answered ``UNDEFINED`` (the lived arms, v1)."""
    if not world.config.relation_absence:
        return []
    return [(kind, name, "UNDEFINED", None) for name, kind in empty_relations(world)
            if world.symbol(name).qa_split == "train"]


def relation_absence_qa(world: World) -> list[str]:
    return render_pairs(world, relation_absence_pairs(world), "relation-absence")


def corpus(world: World, arm: str) -> list[str]:
    """The training lines of one arm, shuffled by (seed, arm)."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; arms are {ARMS}")
    lines = world.statements() + training_qa(world)
    if "phrase" in arm:
        lines += absent_qa(world)
    if "lived" in arm:
        lines += negative_lines(world) + relation_absence_lines(world) + relation_absence_qa(world)
    _rng(world.seed, f"pack:{arm}").shuffle(lines)
    return lines


def _sibling_answers(world: World, name: str) -> dict[str, str | None]:
    facts = world.facts_of(name)
    return {k: (v[0] if v else None) for k, v in facts.items()}


def eval_items(world: World) -> dict[str, list[dict]]:
    """The evaluation sets, one list per file.

    ``primary``: ``Where is X defined?`` for every QA-held-out real symbol
    (dense, sparse, mid) and every absent name — the §6.1 rows.
    ``secondary``: the ``calls`` / ``reached_by`` queries where a
    held-out symbol has such facts, and for every absent name.
    ``trained``: the QA-trained symbols' own queries (the memorisation
    reference). ``inversion``: §6.4's items in three context variants,
    split ``C+S`` (fact in the corpus) / ``C-only`` (module-inference
    symbols, whose fact is only ever in context).

    v1: under ``relation_absence`` the secondary set also asks every
    real symbol's *empty* relations (gold act ``UNDEFINED``), its rows
    split ``with`` / ``without`` by exposure; under ``query_holdout``
    every prompt takes the held-out phrasing and ``primary_seen`` repeats
    the primary items in the first trained one.
    """
    cfg = world.config
    phrasing = HELD_OUT_PHRASING if cfg.query_holdout else 0
    trained_pairs = {(k, n, v) for k, n, _, v in training_pairs(world)}
    primary: list[dict] = []
    secondary: list[dict] = []
    trained: list[dict] = []

    def item(name, cls, exposure, kind, gold, sibling, distance, stems, mentions, split, ph=phrasing):
        return {
            "id": f"{kind}:{name}",
            "prompt": query_line(kind, name, ph),
            "kind": kind,
            "name": name,
            "class": cls,
            "exposure": exposure,
            "gold_act": "ANSWER" if gold else "UNDEFINED",
            "gold": gold,
            "gold_trained": [v for v in gold if (kind, name, v) in trained_pairs],
            "sibling": sibling,
            "nearest_dense_distance": distance,
            "stems": len(stems),
            "mentions": mentions,
            "split": split,
        }

    counts = world.mention_counts()
    for s in world.symbols:
        facts = world.facts_of(s.name)
        sib = _sibling_answers(world, s.nearest_dense) if s.nearest_dense else {k: None for k in QUERY_KINDS}
        cls = "module-infer" if not s.defined_in_stated else s.cls
        for kind in QUERY_KINDS:
            gold = facts[kind] if kind != "defined_in" else [s.module]
            exposure = "n/a"
            if kind != "defined_in" and not gold:
                if not (cfg.relation_absence and kind in RELATION_ABSENCE_TEMPLATES):
                    continue
                exposure = "without"
            elif kind != "defined_in" and cfg.relation_absence and kind in RELATION_ABSENCE_TEMPLATES:
                exposure = "with"
            it = item(s.name, cls, exposure, kind, gold, sib[kind], s.nearest_dense_distance,
                      split_name(s.name), counts[s.name], s.qa_split)
            if s.qa_split == "train":
                trained.append(it)
            elif kind == "defined_in":
                primary.append(it)
            else:
                secondary.append(it)
    for a in world.absents:
        sib = _sibling_answers(world, a.nearest_dense) if a.nearest_dense else {k: None for k in QUERY_KINDS}
        for kind in QUERY_KINDS:
            it = item(a.name, a.cls, a.exposure, kind, [], sib[kind], a.nearest_dense_distance,
                      split_name(a.name), 0, "eval")
            (primary if kind == "defined_in" else secondary).append(it)

    rng = _rng(world.seed, "inversion")
    inversion: list[dict] = []
    cs = [s for s in world.symbols if s.cls == "dense-real" and s.qa_split == "eval"]
    conly = [s for s in world.symbols if not s.defined_in_stated]
    n = world.config.inversion_items
    for split, group in (("C+S", rng.sample(cs, min(n, len(cs)))), ("C-only", rng.sample(conly, min(n, len(conly))))):
        for s in group:
            other = rng.choice([m for m in world.modules if m != s.module])
            for ctx_kind, ctx_value in (("none", None), ("support", s.module), ("conflict", other)):
                ctx = "" if ctx_value is None else TEMPLATES["defined_in"][0].format(s=s.name, m=ctx_value) + "\n"
                inversion.append({
                    "id": f"inv:{split}:{ctx_kind}:{s.name}",
                    "prompt": ctx + query_line("defined_in", s.name, phrasing),
                    "kind": "defined_in",
                    "name": s.name,
                    "class": s.cls if s.defined_in_stated else "module-infer",
                    "split": split,
                    "context_kind": ctx_kind,
                    "context_value": ctx_value,
                    "gold": [s.module],
                    "gold_act": "ANSWER",
                })
    sets = {"primary": primary, "secondary": secondary, "trained": trained, "inversion": inversion}
    if cfg.query_holdout:
        sets["primary_seen"] = [dict(it, prompt=query_line(it["kind"], it["name"], TRAIN_PHRASINGS[0])) for it in primary]
    return sets


# ---------------------------------------------------------------- files

def write(world: World, out: Path) -> dict:
    """Lay the world out under ``out`` and return the manifest it wrote.

    ``world.json`` (the graph, canonical JSON), ``entities.json``,
    ``corpus/<arm>.txt`` (one line per training example),
    ``eval/<set>.jsonl``, and ``manifest.json`` with the world hash, every
    corpus hash and the class counts.
    """
    out.mkdir(parents=True, exist_ok=True)
    world_bytes = canonical(world.to_json())
    (out / "world.json").write_bytes(world_bytes)
    (out / "entities.json").write_bytes(canonical(world.entities()))
    (out / "corpus").mkdir(exist_ok=True)
    (out / "eval").mkdir(exist_ok=True)
    corpus_hashes = {}
    corpus_lines = {}
    for arm in ARMS:
        lines = corpus(world, arm)
        data = ("\n".join(lines) + "\n").encode("utf-8")
        (out / "corpus" / f"{arm}.txt").write_bytes(data)
        corpus_hashes[arm] = sha256(data)
        corpus_lines[arm] = len(lines)
    evals = eval_items(world)
    eval_counts = {}
    for name, items in evals.items():
        data = "".join(json.dumps(it, sort_keys=True, ensure_ascii=False) + "\n" for it in items).encode("utf-8")
        (out / "eval" / f"{name}.jsonl").write_bytes(data)
        eval_counts[name] = len(items)
    counts = world.mention_counts()
    by_class: dict[str, int] = {}
    for s in world.symbols:
        by_class[s.cls] = by_class.get(s.cls, 0) + 1
    for a in world.absents:
        key = f"{a.cls}/{a.exposure}"
        by_class[key] = by_class.get(key, 0) + 1
    manifest = {
        "generator": f"atlas0 {VERSION}",
        "variant": world.config.variant(),
        "seed": world.seed,
        "config": asdict(world.config),
        "world_hash": sha256(world_bytes),
        "corpus_hash": corpus_hashes,
        "corpus_lines": corpus_lines,
        "eval_items": eval_counts,
        "classes": by_class,
        "facts": len(world.facts),
        "module_infer": sum(1 for s in world.symbols if not s.defined_in_stated),
        "qa_trained_symbols": sum(1 for s in world.symbols if s.qa_split == "train"),
        "mentions": {
            cls: {"min": min(counts[s.name] for s in world.symbols if s.cls == cls),
                  "max": max(counts[s.name] for s in world.symbols if s.cls == cls)}
            for cls in ("dense-real", "sparse-real", "mid")
        },
    }
    (out / "manifest.json").write_bytes(json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    return manifest


def read(path: Path) -> World:
    return World.from_json(json.loads((path / "world.json").read_text()))
