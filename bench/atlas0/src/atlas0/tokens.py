"""The entity tokenizer: how a name enters each block (design §3, §7).

The one piece of structure Atlas-0 gives the model is the boundary of
an entity name; it comes from the world's ``entities.json``, not from
learning. Under **B1** (and **B4**, B1's input map with typed attention, the
2026-09-07 addendum) an entity is its stems with ``_`` between them
(``range_join_merge`` → ``range`` ``_`` ``join`` ``_`` ``merge``), so
every name shares its pieces with every other. Under **B2** and **B3**
an entity is one token of its own; B2's embedding for it is learned
from a seeded initialisation, B3's is that initialisation frozen — the
same vector from :func:`entity_vectors` either way, which is what
separates *dedicated* from *frozen* in the ladder.

The vocabulary is fixed from the world: every stem, every word and
punctuation mark of the templates and queries, the act tokens, and
(for B2/B3) every entity name including held-out absent ones — those
get a token they never see in training, and at test time the block
meets a vector it has no gradient on, which is the point (§3).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from collections import Counter

from .names import STEMS
from .world import NEGATIVE_TEMPLATES, QUERY_PHRASINGS, QUERY_TEMPLATES, RELATION_ABSENCE_TEMPLATES, TEMPLATES, V0_TEMPLATES
from .acts import ACTS

PAD, BOS, EOS, UNK, NL = "<pad>", "<bos>", "<eos>", "<unk>", "<nl>"
SPECIAL = (PAD, BOS, EOS, UNK, NL)
BLOCKS = ("B1", "B2", "B3", "B4")
#: The blocks whose entity names are one dedicated token; B1 and B4 (B1 + typed attention) read stems.
DEDICATED = ("B2", "B3")

_PIECE = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")


def _words(texts: list[str]) -> list[str]:
    words: set[str] = set()
    for t in texts:
        t = re.sub(r"\{[a-z]\}", " ", t)
        for piece in _PIECE.findall(t):
            words.add(piece)
    return sorted(words)


def _template_words() -> list[str]:
    """v0's words: the statement, negative and first query templates."""
    texts = [t for ts in TEMPLATES.values() for t in ts[:V0_TEMPLATES]] + list(NEGATIVE_TEMPLATES) + list(QUERY_TEMPLATES.values())
    return _words(texts + ["Q: A:", "undefined", ","])


def _v1_words() -> list[str]:
    """The words v1's templates add (relation absence, query phrasings 1–3).

    Fixed to the first four phrasings so the ids a v1 cell trained with
    do not move when a phrasing is added after them (the fifth, 2026-09-06,
    adds no word the vocabulary lacks; a later one that does is appended
    by :func:`_later_words`).
    """
    v0 = set(_template_words())
    texts = [t for ts in RELATION_ABSENCE_TEMPLATES.values() for t in ts] + [p for ps in QUERY_PHRASINGS.values() for p in ps[:4]]
    return [w for w in _words(texts) if w not in v0]


def _later_words() -> list[str]:
    """Words of phrasings and templates added after v1 (v2's templates 5–7 and
    phrasings 4–7), appended after everything else so every earlier id stands."""
    known = set(_template_words()) | set(_v1_words())
    texts = [p for ps in QUERY_PHRASINGS.values() for p in ps[4:]] + [t for ts in TEMPLATES.values() for t in ts[V0_TEMPLATES:]]
    return [w for w in _words(texts) if w not in known]


def untrained_prompt_tokens(tok: "Tokenizer", trained: set[int], prompts: list[str], exempt: set[int] = frozenset()) -> Counter:
    """Every token of ``prompts`` that ``trained`` (the ids of the training stream)
    does not contain, counted by token string; ``exempt`` ids (the entity tokens of
    absent names, which are meant to be unseen) are not counted.

    The check the ``<nl>`` and ``live`` defects (2026-09-05/06) called for:
    a token no stream contains sits between the block and the question as
    an untrained embedding, and every number read through it is a number
    about that token. Run before a cell is read; the trainer refuses on a
    non-empty result unless told to allow it.
    """
    bad: Counter = Counter()
    for p in prompts:
        for i in tok.encode(p):
            if i not in trained and i not in exempt:
                bad[tok.vocab[i]] += 1
    return bad


@dataclass
class Tokenizer:
    block: str
    entities: dict[str, str]              # name → kind (module | test | symbol | absent)
    vocab: list[str]
    index: dict[str, int]

    @staticmethod
    def build(block: str, entities: dict[str, str], v1_words: bool = True, later_words: bool = True) -> "Tokenizer":
        """The vocabulary for ``block`` over ``entities``. v1's words go last, after
        the entities, and v2's after those, so every earlier token id is what it
        was; ``v1_words=False`` is the v0 vocabulary exactly and ``later_words=False``
        v1's (a v0 or v1 cell's weights re-read)."""
        if block not in BLOCKS:
            raise ValueError(f"unknown block {block!r}; blocks are {BLOCKS}")
        vocab: list[str] = []
        for v in list(SPECIAL) + list(ACTS) + _template_words() + list(STEMS) + ["_", "mod", "test"]:
            if v not in vocab:
                vocab.append(v)
        if block in DEDICATED:
            vocab += sorted(entities)
        if v1_words:
            vocab += [w for w in _v1_words() if w not in vocab]
            if later_words:
                vocab += [w for w in _later_words() if w not in vocab]
        return Tokenizer(block, dict(entities), vocab, {v: i for i, v in enumerate(vocab)})

    @property
    def entity_ids(self) -> dict[str, int]:
        """Under B2/B3, the token id of every entity; empty under B1 and B4."""
        if self.block not in DEDICATED:
            return {}
        return {name: self.index[name] for name in self.entities}

    def __len__(self) -> int:
        return len(self.vocab)

    def encode(self, text: str) -> list[int]:
        """Token ids of ``text``. A newline is a line boundary, encoded as the
        stream's ``<eos>`` — the token that separates lines in training — so a
        statement put before a question (§6.4) reads as the preceding line.
        (Until 2026-09-05 night it was ``<nl>``, a token no stream contains;
        every §6.4 prompt was read through an untrained separator.)"""
        ids: list[int] = []
        for line_no, line in enumerate(text.split("\n")):
            if line_no:
                ids.append(self.index[EOS])
            for piece in _PIECE.findall(line):
                if piece in self.entities and self.block in DEDICATED:
                    ids.append(self.index[piece])
                elif piece in self.entities or "_" in piece:
                    parts = piece.split("_")
                    for i, part in enumerate(parts):
                        if i:
                            ids.append(self.index["_"])
                        ids.append(self.index.get(part, self.index[UNK]))
                else:
                    ids.append(self.index.get(piece, self.index[UNK]))
        return ids

    def decode(self, ids: list[int]) -> str:
        out: list[str] = []
        for i in ids:
            tok = self.vocab[i]
            if tok == NL:
                out.append("\n")
            elif tok == "_" or (out and out[-1] == "_"):
                out.append(tok)
            elif tok in (".", ",", ":", "?", ";", ")", "(") or not out or out[-1] == "\n" or out[-1] == "(":
                out.append(tok)
            else:
                out.append(" " + tok)
        return "".join(out)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({"block": self.block, "entities": self.entities, "vocab": self.vocab},
                                   sort_keys=True))

    @staticmethod
    def load(path: Path) -> "Tokenizer":
        d = json.loads(path.read_text())
        return Tokenizer(d["block"], d["entities"], d["vocab"], {v: i for i, v in enumerate(d["vocab"])})


def entity_vectors(names: list[str], dim: int, seed: int, scale: float = 0.02) -> np.ndarray:
    """One seeded vector per entity name: ``sha256(seed, name)`` → the generator → N(0, scale²).

    B3 uses these frozen; B2 initialises from them. A name that never
    appears in training has one all the same, so an absent name meets
    the block as a vector like any other's (§3).
    """
    out = np.zeros((len(names), dim), dtype=np.float32)
    for i, name in enumerate(names):
        h = hashlib.sha256(f"atlas0:entity:{seed}:{name}".encode()).digest()
        rng = np.random.default_rng(int.from_bytes(h[:8], "little"))
        out[i] = rng.normal(0.0, scale, dim).astype(np.float32)
    return out
