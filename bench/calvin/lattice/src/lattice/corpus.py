"""**E3's corpus** — the draw's families as training examples, and their shuffled control.

E3 asks whether a LoRA trained on C pattern families from *other* repos lifts E1's arms
(`docs/calvin/calvin-experiments.md` §6, E3 and "E3's price on D-7's pool"). This module is the step
before any of that spends: it turns the members `families` draws — the draw's own union, the draw's own
dedupe — into one training example each, in **E1's evaluated format**, and writes the corpus beside its
shuffled-answers control. Nothing here calls a model, and nothing here trains.

**The training task is E1's:** "given the neighbours, write the member". One example is the fixed system
line (`prompts.SYSTEM`), a user turn carrying up to three other members of the member's own family as
whole definitions, then the prototypes of the in-repo callees its body makes, then the member's own
signature, then `prompts.INSTRUCTION` word for word; and one assistant turn holding the member's whole
definition in a ```` ```c ```` block. **The trained format is the evaluated one** — the adapter is read
on E1's arms — so the assistant turn is put back through :func:`extract.extract` before the record is
kept, and a member whose own answer the evaluator could not read is dropped rather than trained on.

**Four rules the card binds this to** (§6's revised E3 card, §8), each a drop with its own reason, each
counted in the manifest and listed in the report:

- **No sqlite-vector code, by name and by near-copy.** The two are different instruments and both are
  needed: the target itself and its owner were gated out of the draw **by name** (`gate.py`'s gate 2, and
  gate 2 again on any file naming the target), and here every member's body is compared with each of the
  target's **native gold bodies** — the 93 the card names, which is what E3 is evaluated on — on the
  same tokens. A ratio of `NEAR_TARGET_RATIO` or more is `near-target`, dropped, listed with its ratio,
  and **never carried as another member's neighbour either**: a gold body in a prompt is the target in
  the corpus whichever column it sits in. What this rule does *not* claim is coverage of the target's
  non-native files (`cpu`, `neon`, `rvv`): a member matching one of those is the target's code too, and
  it is gate 2 by name that keeps it out, not this ratio.
- **No dispatched session's text ever trains** (ADR-107, §8). An input root that holds
  `docs/calvin/sessions/` or `pipeline/src/hobbes/` is Hobbes itself or a checkout of it, and it is
  refused outright with :class:`SessionText` — its own type, so a general "could not read that repo"
  handler cannot absorb it (P10, ADR-036).
- **No example depends on a fact its prompt does not carry** (§12.5: fine-tuning on unfamiliar facts
  teaches guessing). A member one of whose in-repo callees has no readable signature in the clone is
  `unstated-callee`; a member left with no neighbour to show is `alone`.
- **No example is truncated.** The trainer cuts at 2,048 tokens and counts the cut
  (`modal_ttt.train_adapter`); a cut example is an answer whose end was never shown. An example over
  `MAX_CHARS` characters — about 1,900 tokens at four characters a token — is dropped as `too-long`,
  never cut.

**The control is ADR-099's:** the same records with the answers permuted, so the token multiset of the
answers and every byte of every prompt are the same and only the pairing is broken. The permutation is
a seeded derangement in which **no record keeps its own answer or one from its own family** — a
same-family answer would leave a pattern arm wearing the control's name. It is built by laying the
families out largest first and rotating by the largest family's size, which is why a corpus one family
holds half or more of has no control at all and raises :class:`NoDerangement` rather than a weaker one.

**What is written:** `<out>/e3-pattern/` and `<out>/e3-shuffled/`, each `train.jsonl` (one
`{"messages": […]}` a line, the loss on the assistant turn) and `manifest.json` (`corpus_hash`, `repo`
and `sha`, which is what keys an adapter, plus the records, the drops by reason and every record's
family key and source `path:line`); and `<out>/corpus-report.json`, per repo the union, the unique, the
drops and the kept, with the character lengths' quartiles — the measurement that replaces the price
table's "≤ 2k tokens" assumption.

The same inputs and the same seed give byte-identical outputs: every order here is either the clone's
own (`path`, `line`) or derived from SHA-256 of the seed and the row, never Python's `hash()`.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import statistics
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import families, holes
from .cells import build as build_lattice
from .extract import extract
from .prompts import INSTRUCTION, SYSTEM
from .scan import mask

__all__ = [
    "MAX_CHARS",
    "NEAR_TARGET_RATIO",
    "NEIGHBOURS",
    "PATTERN_REPO",
    "REASONS",
    "SEED",
    "SESSION_MARKERS",
    "SHUFFLED_REPO",
    "Built",
    "Clone",
    "NoDerangement",
    "Record",
    "SessionText",
    "answer_for",
    "build_corpus",
    "derange",
    "head_of",
    "near_target",
    "prompt_for",
    "read_list",
    "refuse_session_text",
    "target_golds",
    "write",
]

#: The draw's seed, and this corpus': one number for the whole of E3's draw (`DRAW-RULE.md`).
SEED = 20260926

#: A member whose body reaches this ratio against any of the target's golds is the target's code.
NEAR_TARGET_RATIO = 0.6

#: How many of a member's own family are shown beside it.
NEIGHBOURS = 3

#: The longest example kept, in characters: about 1,900 tokens at four characters a token, under the
#: trainer's `RECIPE["max_len"]` of 2,048. An example over it is dropped, never cut.
MAX_CHARS = 7_600

#: `manifest["repo"]`, which with `sha` is what `train_adapter` keys an adapter on.
PATTERN_REPO = "e3-c-lattice"
SHUFFLED_REPO = "e3-c-lattice-shuffled"

#: Every reason a member does not become an example. `unreadable` is the two ends of one rule: the
#: clone has no definition at the graph's lines, or `extract` does not read the answer built from it
#: back — the trained format is the evaluated one, so an answer the evaluator cannot read is not an
#: example.
REASONS = ("near-target", "unreadable", "alone", "unstated-callee", "too-long")

#: One blank line between two neighbours inside the one fenced block, as `prompts` writes its shots.
_NEIGHBOUR_GAP = "\n\n"

#: A root holding either of these is Hobbes itself or a checkout of it (ADR-107, §8).
SESSION_MARKERS = ("docs/calvin/sessions", "pipeline/src/hobbes")

_RELATED_HEADING = "Related functions:"
_CALLS_HEADING = "What this function calls, read from the project's graph:"
_SIGNATURE_HEADING = "The function to write:"


class SessionText(Exception):
    """An input root is Hobbes itself, or a checkout of it, so it was not read.

    Its own type, because a general "that repo could not be read" handler must not absorb it: no
    dispatched session's text is ever training data (ADR-107's retention amendment, §8), and a corpus
    that quietly skipped the root would be a corpus nobody checked.
    """


class NoDerangement(Exception):
    """The shuffled control cannot be built: one family holds half the records or more."""


@dataclass(frozen=True)
class Record:
    """One training example: where it came from, what its prompt says, and the answer it is paired to."""

    repo: str
    member: str  # the graph's symbol id
    name: str
    family: str  # "<repo> <rule>:<pattern>", the family the neighbours were drawn from
    source: str  # "<path>:<line>" in that repo
    prompt: str  # the user turn
    answer: str  # the assistant turn, one fenced C block
    neighbours: tuple[str, ...]
    callees: tuple[str, ...]

    @property
    def chars(self) -> int:
        """The characters the three turns carry, which is what `MAX_CHARS` is a limit on."""
        return len(SYSTEM) + len(self.prompt) + len(self.answer)

    def messages(self, answer: str | None = None) -> list[dict]:
        """The three turns, `answer` overriding the record's own — which is how the control is written."""
        return [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": self.prompt},
            {"role": "assistant", "content": self.answer if answer is None else answer},
        ]


@dataclass(frozen=True)
class Built:
    """A corpus and its control, as data: the records in order, the input digest, and the report."""

    records: tuple[Record, ...]
    shuffled: tuple[int, ...]  # for each record, the index of the record whose answer it is given
    sha: str
    report: dict


# MARK: - the refusal -


def refuse_session_text(root: Path) -> None:
    """Raise :class:`SessionText` if *root* is Hobbes itself or a checkout of it (ADR-107, §8)."""
    for marker in SESSION_MARKERS:
        if (Path(root) / marker).exists():
            raise SessionText(
                f"{root} holds {marker}: it is Hobbes itself or a checkout of it, and no dispatched "
                "session's text is ever training data (ADR-107, calvin-experiments.md §8)"
            )


def read_list(path: Path) -> list[tuple[str, Path]]:
    """The repos list: one `name=root` a line, in the taken order. Blank lines and `#` lines are skipped."""
    found: list[tuple[str, Path]] = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "=" not in text:
            raise ValueError(f"{path}:{number}: {text!r} is not <name>=<root>")
        name, root = text.split("=", 1)
        found.append((name.strip(), Path(root.strip()).expanduser()))
    return found


# MARK: - the clone, read where the graph points -


class Clone:
    """A clone's files, read once each, and the definitions the graph's line numbers point at.

    The graph gives a symbol's first and last line; this gives back the bytes. The body's end is found
    by walking `scan.mask` — which blanks comments, literals and preprocessor lines and is the same
    length as the text — from the first `{` to its matching `}`, so a brace inside a comment or a string
    does not close a definition. `None` is returned for a slice with no brace body at all, which is the
    same thing `families.Repo` calls a body it could not read.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self._files: dict[str, list[str]] = {}
        self._read: dict[tuple, tuple[str, str] | None] = {}

    def lines(self, path: str) -> list[str]:
        if path not in self._files:
            try:
                self._files[path] = (self.root / path).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                self._files[path] = []
        return self._files[path]

    def definition(self, path: str | None, line: int | None, end_line: int | None) -> tuple[str, str] | None:
        """`(definition, body)` — the whole definition as the clone writes it, and its `{`…`}` part.

        Kept per `(path, line, end_line)`: a member of a family of a hundred is read for once and shown
        as a neighbour ninety-nine times, and the masking is the same answer every time.
        """
        at = (path, line, end_line)
        if at not in self._read:
            self._read[at] = self._definition(path, line, end_line)
        return self._read[at]

    def _definition(self, path: str | None, line: int | None, end_line: int | None) -> tuple[str, str] | None:
        if not path or not line or not end_line:
            return None
        lines = self.lines(path)
        if not lines or line > len(lines):
            return None
        raw = "\n".join(lines[line - 1: end_line])
        masked = mask(raw)
        opened = masked.find("{")
        if opened < 0:
            return None
        depth, closed = 0, -1
        for at in range(opened, len(masked)):
            if masked[at] == "{":
                depth += 1
            elif masked[at] == "}":
                depth -= 1
                if depth == 0:
                    closed = at
                    break
        if closed < 0:
            return None
        start = len(raw) - len(raw.lstrip())
        return raw[start: closed + 1], raw[opened: closed + 1]

    def prototype(self, path: str | None, line: int | None, end_line: int | None) -> str | None:
        """A callee's signature line: its definition's text before the `{`, on one line, ending in `;`."""
        found = self.definition(path, line, end_line)
        if found is None:
            return None
        definition, body = found
        head = " ".join(families.strip_comments(definition[: len(definition) - len(body)]).split())
        return f"{head};" if head else None


# MARK: - the target's golds -


def target_golds(target: Path) -> list[tuple[str, ...]]:
    """Each native cell's gold body as `families`' own tokens: what `near-target` is measured against.

    The braces go, because `families.Repo` reads a member's body as the text *between* them, and the two
    sides of a ratio have to be tokenised the same way. Comments are stripped and literals emptied by
    `families.strip_comments`, which is what the draw did to every member's body.
    """
    lattice = build_lattice(target)
    golds = []
    for cell in lattice.cells.values():
        if not cell.native:
            continue
        text = holes.gold_body(lattice.text(cell), cell)
        inner = text[text.find("{") + 1: text.rfind("}")]
        golds.append(tuple(families.body_tokens({"body": families.strip_comments(inner)}, "")))
    return golds


def near_target(member_tokens: list[str], golds: list[tuple[str, ...]]) -> float | None:
    """The best ratio against any gold at or above `NEAR_TARGET_RATIO`, or `None` if none reaches it.

    The draw's own prefilters, in its order — `real_quick_ratio` then `quick_ratio`, both exact upper
    bounds — and then the full ratio. One matcher per gold, its second sequence cached, since this runs
    over every member of every repo.
    """
    best = None
    for gold in golds:
        matcher = difflib.SequenceMatcher(None, None, gold, autojunk=False)
        matcher.set_seq1(member_tokens)
        if matcher.real_quick_ratio() < NEAR_TARGET_RATIO or matcher.quick_ratio() < NEAR_TARGET_RATIO:
            continue
        ratio = matcher.ratio()
        if ratio >= NEAR_TARGET_RATIO and (best is None or ratio > best):
            best = ratio
    return best


# MARK: - one repo's members, families and callees -


def _families_of(repo: families.Repo) -> list[dict]:
    """The draw's union families over the non-thin members: the ISA rule's, then the body-shape rule's.

    Labelled `<rule>:<pattern>`, with `#2`, `#3`… where one pattern has several families — the
    body-shape rule's single linkage can split one loose group into more than one component. The order
    is fixed by the label and then by the members' own ids, so a member's family is the same on every
    run.
    """
    nonthin = [m for m in repo.members.values() if not m["thin"]]
    found = [{"rule": "isa", **f} for f in families.isa_families(nonthin)]
    body, _, _ = families.body_families(families.loose_groups(nonthin))
    found += [{"rule": "body", **f} for f in body]
    found.sort(key=lambda f: (f["rule"], " ".join(f["key"][2]), sorted(m["id"] for m in f["members"])))
    seen: dict[str, int] = defaultdict(int)
    for f in found:
        pattern = f'{f["rule"]}:{" ".join(f["key"][2])}'
        seen[pattern] += 1
        f["label"] = pattern if seen[pattern] == 1 else f"{pattern}#{seen[pattern]}"
    return found


def _union(fams: list[dict]) -> dict[str, dict]:
    """The union's members, in `dedupe.py`'s own order: the families' order, each member once."""
    return {m["id"]: m for f in fams for m in f["members"]}


def _callees(root: Path) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """The graph's definitions by symbol id, and each symbol's in-repo callees, in `(path, line)` order.

    In-repo is the graph's own answer and not a name match: an edge whose target is a function or method
    symbol of this repo. A call to a symbol the graph does not define — libc, an intrinsic, an
    unresolved name — is not in here, and so is never a fact an example is asked to depend on.
    """
    g = json.loads((Path(root) / ".hobbes" / "derived" / "graph.json").read_text(encoding="utf-8"))
    mod_path = {n["id"]: n.get("path") for n in g["nodes"] if n.get("kind") == "module" and n.get("path")}
    defined = {
        s["id"]: {
            "name": s["name"],
            "path": mod_path.get(s.get("module")),
            "line": s.get("line"),
            "end_line": s.get("end_line"),
        }
        for s in g["symbols"]
        if s.get("kind") in ("function", "method")
    }
    calls: dict[str, list[str]] = defaultdict(list)
    for e in g["symbol_edges"]:
        if e.get("type") != "calls" or e["to"] not in defined or e["to"] == e["from"]:
            continue
        if e["to"] not in calls[e["from"]]:
            calls[e["from"]].append(e["to"])
    for found in calls.values():
        found.sort(key=lambda i: (defined[i]["path"] or "", defined[i]["line"] or 0, i))
    return defined, calls


# MARK: - the prompt -


def prompt_for(neighbours: list[str], prototypes: list[str], signature: str) -> str:
    """One user turn: the neighbours, the callees' prototypes, the signature, E1-c's instruction.

    The headings and the fenced blocks are `prompts`' own shape, because the adapter is evaluated on
    E1's arms; a section with nothing in it takes its heading with it, as an arm that does not carry one
    does there.
    """
    parts = [_section(_RELATED_HEADING, _fenced(_NEIGHBOUR_GAP.join(neighbours)))]
    if prototypes:
        parts.append(_section(_CALLS_HEADING, _fenced("\n".join(prototypes))))
    parts.append(_section(_SIGNATURE_HEADING, _fenced(signature)))
    parts.append(INSTRUCTION)
    return "\n\n".join(parts)


def _section(heading: str, body: str) -> str:
    return f"{heading}\n\n{body}"


def _fenced(text: str) -> str:
    return f"```c\n{text.rstrip()}\n```"


def answer_for(definition: str) -> str:
    """The assistant turn: one fenced C block holding the definition, exactly as the clone writes it."""
    return _fenced(definition)


def _reads_back(answer: str, name: str, body: str) -> bool:
    """Whether `extract` reads the record's own answer back as the member's own definition (E1-c)."""
    return extract(answer, name).get("body") == body


# MARK: - building -


def build_corpus(repos: list[tuple[str, Path]], target: Path, seed: int = SEED) -> Built:
    """Every kept member of every repo as one example, in the taken order, with its control's pairing.

    *repos* is `(name, root)` in the taken order — the order `dedupe.py` gave the first copy of a body
    to — and *target* is the checkout E3 must not train on. Every root, the target included, is put
    through :func:`refuse_session_text` first: a corpus is not partly built and then found to hold a
    session's text.
    """
    for _, root in repos:
        refuse_session_text(root)
    refuse_session_text(target)

    golds = target_golds(target)
    records: list[Record] = []
    rows: list[dict] = []
    seen: dict[str, str] = {}

    for name, root in repos:
        repo = families.Repo(name, root)
        fams = _families_of(repo)
        union = _union(fams)

        unique, duplicate = _deduplicate(name, union, seen)
        excluded, ratios = _near_target(unique, golds)
        defined, calls = _callees(root)
        read = _Read(name, Clone(root), defined, calls, _by_member(fams), excluded)

        drops: dict[str, list[str]] = {reason: [] for reason in REASONS}
        drops["near-target"] = [f'{m["path"]}:{m["line"]} {m["name"]}' for m in excluded.values()]
        kept: list[Record] = []
        for member in unique:
            if member["id"] in excluded:
                continue
            record = _record(read, member, seed, drops)
            if record is not None:
                kept.append(record)
        records += kept
        rows.append(_repo_row(read, root, repo, union, unique, duplicate, ratios, kept, drops))

    shuffled = derange(records, seed)
    return Built(
        records=tuple(records),
        shuffled=tuple(shuffled),
        sha=_input_sha(repos, target, seed),
        report=_report(rows, records, target, golds, seed),
    )


def _deduplicate(name: str, union: dict[str, dict], seen: dict[str, str]) -> tuple[list[dict], int]:
    """`dedupe.py`'s rule: the first repo in the taken order keeps a body, and a repo's own repeat is one too."""
    unique: list[dict] = []
    duplicate = 0
    own: set[str] = set()
    for member in union.values():
        digest = families.body_hash(member["body"])
        if digest in seen and seen[digest] != name:
            duplicate += 1
        elif digest in own:
            duplicate += 1  # the same body twice in one repo (an #if arm, a copied file)
        else:
            unique.append(member)
            seen.setdefault(digest, name)
        own.add(digest)
    return unique, duplicate


def _near_target(unique: list[dict], golds: list[tuple[str, ...]]) -> tuple[dict[str, dict], dict[str, float]]:
    """The members that are the target's code, by body ratio, and the ratio each was found at."""
    excluded: dict[str, dict] = {}
    ratios: dict[str, float] = {}
    for member in unique:
        ratio = near_target(families.body_tokens(member, ""), golds)
        if ratio is not None:
            excluded[member["id"]] = member
            ratios[member["id"]] = round(ratio, 4)
    return excluded, ratios


def _by_member(fams: list[dict]) -> dict[str, list[dict]]:
    """Each member's families, in the fixed order of :func:`_families_of`."""
    found: dict[str, list[dict]] = defaultdict(list)
    for family in fams:
        for member in family["members"]:
            found[member["id"]].append(family)
    return found


@dataclass(frozen=True)
class _Read:
    """One repo as the corpus reads it: its clone, the graph's two answers, its families, its exclusions."""

    name: str
    clone: Clone
    defined: dict[str, dict]  # every function or method symbol the graph names, by id
    calls: dict[str, list[str]]  # each symbol's in-repo callees, by id
    by_member: dict[str, list[dict]]  # each member's families, in their fixed order
    excluded: dict[str, dict]  # the members that are the target's code, by id


def _record(read: _Read, member: dict, seed: int, drops: dict[str, list[str]]) -> Record | None:
    """One member's example, or `None` with its drop written into *drops* under the reason it failed."""
    where = f'{member["path"]}:{member["line"]}'
    own = read.clone.definition(member["path"], member["line"], member["end_line"])
    if own is None:
        drops["unreadable"].append(f'{where} {member["name"]} (no definition at those lines)')
        return None
    definition, body = own

    family, neighbours = _neighbours(read, member, seed)
    if family is None:
        drops["alone"].append(f'{where} {member["name"]}')
        return None

    prototypes = []
    for callee in read.calls.get(member["id"], []):
        at = read.defined[callee]
        line = read.clone.prototype(at["path"], at["line"], at["end_line"])
        if line is None:
            drops["unstated-callee"].append(f'{where} {member["name"]} calls {at["name"]} (no signature read)')
            return None
        if line not in prototypes:
            prototypes.append(line)

    signature = definition[: len(definition) - len(body)].strip()
    record = Record(
        repo=read.name,
        member=member["id"],
        name=member["name"],
        family=f'{read.name} {family["label"]}',
        source=where,
        prompt=prompt_for([text for _, text in neighbours], prototypes, signature),
        answer=answer_for(definition),
        neighbours=tuple(at for at, _ in neighbours),
        callees=tuple(read.defined[c]["name"] for c in read.calls.get(member["id"], [])),
    )
    if not _reads_back(record.answer, member["name"], body):
        drops["unreadable"].append(f'{where} {member["name"]} (extract does not read its own answer back)')
        return None
    if record.chars > MAX_CHARS:
        drops["too-long"].append(f'{where} {member["name"]} ({record.chars} chars)')
        return None
    return record


def _neighbours(read: _Read, member: dict, seed: int) -> tuple[dict | None, list[tuple[str, str]]]:
    """The first of the member's families that can show it neighbours, and up to `NEIGHBOURS` of them.

    A candidate is another member of that family which is **not** `near-target` — the target's code is
    not in this corpus in any column — and whose definition the clone can be read for. Candidates are
    taken in the clone's own `(path, line)` order from a start derived with SHA-256 from the seed and
    the member's own place, so a large family is spread over rather than read from its first row every
    time, and the same seed gives the same three every run.
    """
    for family in read.by_member.get(member["id"], []):
        candidates = []
        for other in sorted(family["members"], key=lambda m: (m["path"], m["line"] or 0, m["id"])):
            if other["id"] == member["id"] or other["id"] in read.excluded:
                continue
            found = read.clone.definition(other["path"], other["line"], other["end_line"])
            if found is not None:
                candidates.append((f'{other["path"]}:{other["line"]}', found[0]))
        if not candidates:
            continue
        start = _start(f'{seed}:{member["path"]}:{member["line"]}', len(candidates))
        ordered = candidates[start:] + candidates[:start]
        return family, ordered[:NEIGHBOURS]
    return None, []


def _start(key: str, count: int) -> int:
    """Where in a list to start, from a key: SHA-256, never Python's `hash()`, which is salted."""
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % count


# MARK: - the control -


def derange(records: list[Record], seed: int) -> list[int]:
    """For each record, the index of the record whose answer it is given in the shuffled corpus.

    Seeded, a derangement, and never within a family. The families are laid out largest first — their
    order and each one's own order seeded from SHA-256 of the seed and the family or the row — and the
    answers are rotated by the largest family's size *m*. Every position then lands outside its own
    family: a position `i` in a family of size `g ≤ m` moves to `i + m ≥ i + g`, past that family's own
    run, and a position that wraps round lands inside the first family's run, which it is not in
    because `i ≥ n - m ≥ m`. That last step needs `2m ≤ n`, which is exactly when a corpus with no
    same-family answer exists at all; :class:`NoDerangement` says so rather than a control being built
    that quietly keeps some.
    """
    if len(records) < 2:
        raise NoDerangement(f"{len(records)} record(s): a shuffled control needs at least two")
    grouped: dict[str, list[int]] = defaultdict(list)
    for at, record in enumerate(records):
        grouped[record.family].append(at)
    order = sorted(
        grouped.items(),
        key=lambda kv: (-len(kv[1]), hashlib.sha256(f"{seed}:{kv[0]}".encode("utf-8")).hexdigest()),
    )
    largest = len(order[0][1])
    if 2 * largest > len(records):
        raise NoDerangement(
            f'the family {order[0][0]!r} holds {largest} of {len(records)} record(s): no permutation '
            "can give every record an answer from another family"
        )
    layout: list[int] = []
    for family, members in order:
        layout += sorted(
            members,
            key=lambda at: hashlib.sha256(f"{seed}:{family}:{records[at].source}".encode("utf-8")).hexdigest(),
        )
    answers = [0] * len(records)
    for at, index in enumerate(layout):
        answers[index] = layout[(at + largest) % len(layout)]
    return answers


# MARK: - the report and the digests -


def _input_sha(repos: list[tuple[str, Path]], target: Path, seed: int) -> str:
    """The corpus' `sha`: the repos list as given, the target's HEAD and the seed (`train_adapter`'s key)."""
    listed = "\n".join(f"{name}={root}" for name, root in repos)
    return hashlib.sha256(f"{listed}\n{head_of(target)}\n{seed}".encode("utf-8")).hexdigest()


def head_of(root: Path) -> str:
    """The checkout's commit, or `"unknown"` where git cannot answer — never guessed at."""
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else "unknown"


def _repo_row(
    read: _Read,
    root: Path,
    repo: families.Repo,
    union: dict[str, dict],
    unique: list[dict],
    duplicate: int,
    ratios: dict[str, float],
    kept: list[Record],
    drops: dict[str, list[str]],
) -> dict:
    """One repo's line of the report: the draw's figures, this corpus' drops, and the draw's validation."""
    excluded = read.excluded
    return {
        "repo": read.name,
        "root": str(root),
        "ingest_sha": repo.sha,
        "ingest_version": repo.version,
        "members": len(repo.members),
        "nonthin": sum(1 for m in repo.members.values() if not m["thin"]),
        "union": len(union),
        "unique": len(unique),
        "duplicate": duplicate,
        "dropped": {reason: len(drops[reason]) for reason in REASONS},
        "kept": len(kept),
        "near_target": [
            {"member": member_id, "where": f'{excluded[member_id]["path"]}:{excluded[member_id]["line"]}',
             "name": excluded[member_id]["name"], "ratio": ratios[member_id]}
            for member_id in sorted(excluded)
        ],
        "dropped_members": {reason: drops[reason] for reason in REASONS},
        "validated": _validated(kept, repo, read.by_member),
    }


def _validated(kept: list[Record], repo: families.Repo, by_member: dict[str, list[dict]]) -> dict:
    """The draw's validation reading over the kept members: a scalar-reference sibling, or a test's reach.

    Described and not required. The card asks validation of *generated* siblings; a mined member is the
    repo's own shipped code, which is why D-7 a counts the pool without it (§6). The figure is here so
    the corpus says how much of itself could be checked, not because a row needs it.

    `scalar_ref` is asked of the whole member set and not of the pool, as the draw asked it: a thin
    one-line wrapper is a scalar reference a body can be checked against even though it is no member.
    """
    all_names = {families.isa_tokens(m["name"]) for m in repo.members.values()}
    scalar, reached = 0, 0
    for record in kept:
        member = repo.members[record.member]
        if member["id"] in repo.reached:
            reached += 1
        if any(
            family["rule"] == "isa" and families.scalar_ref(member, family["key"][1], all_names)
            for family in by_member.get(member["id"], [])
        ):
            scalar += 1
    return {"scalar_ref": scalar, "reached_by_tests": reached}


def _report(rows: list[dict], records: list[Record], target: Path, golds: list[tuple[str, ...]], seed: int) -> dict:
    """The corpus report: per repo the draw's and this corpus' counts, then the lengths measured."""
    totals = {
        key: sum(row[key] for row in rows)
        for key in ("members", "nonthin", "union", "unique", "duplicate", "kept")
    }
    totals["dropped"] = {reason: sum(row["dropped"][reason] for row in rows) for reason in REASONS}
    return {
        "seed": seed,
        "target": {"root": str(target), "head": head_of(target), "gold_bodies": len(golds),
                   "near_target_ratio": NEAR_TARGET_RATIO},
        "max_chars": MAX_CHARS,
        "repos": rows,
        "totals": totals,
        "lengths": _lengths(records),
    }


def _lengths(records: list[Record]) -> dict:
    """The kept examples' character lengths, and the tokens they are about, as quartiles."""
    prompts = [len(SYSTEM) + len(record.prompt) for record in records]
    answers = [len(record.answer) for record in records]
    whole = [record.chars for record in records]
    found = {"prompt_chars": _quartiles(prompts), "answer_chars": _quartiles(answers),
             "example_chars": _quartiles(whole)}
    found["example_tokens_at_4_chars"] = {
        key: None if value is None else round(value / 4, 1)
        for key, value in found["example_chars"].items()
        if key != "n"  # a count is not a length; only the five figures are turned into tokens
    }
    return found


def _quartiles(values: list[int]) -> dict:
    """`min`, `q1`, `median`, `q3`, `max` and the count — inclusive quartiles, stdlib's own."""
    if not values:
        return {"n": 0, "min": None, "q1": None, "median": None, "q3": None, "max": None}
    if len(values) == 1:
        one = values[0]
        return {"n": 1, "min": one, "q1": one, "median": one, "q3": one, "max": one}
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return {"n": len(values), "min": min(values), "q1": round(q1, 1), "median": round(median, 1),
            "q3": round(q3, 1), "max": max(values)}


# MARK: - writing -


def write(built: Built, out: Path) -> dict:
    """Write the two corpora and the report under *out*, and give back the summary the CLI prints."""
    out = Path(out)
    pattern = _write_corpus(out / "e3-pattern", built, PATTERN_REPO, shuffled=False)
    shuffled = _write_corpus(out / "e3-shuffled", built, SHUFFLED_REPO, shuffled=True)
    report = dict(built.report)
    report["corpora"] = [
        {"repo": manifest["repo"], "records": manifest["records"], "corpus_hash": manifest["corpus_hash"],
         "sha": manifest["sha"]}
        for manifest in (pattern, shuffled)
    ]
    (out / "corpus-report.json").write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    return {"pattern": pattern, "shuffled": shuffled, "report": report}


def _write_corpus(where: Path, built: Built, repo: str, *, shuffled: bool) -> dict:
    """One corpus directory: `train.jsonl`, then the manifest whose `corpus_hash` is that file's sha256."""
    where.mkdir(parents=True, exist_ok=True)
    lines = []
    for at, record in enumerate(built.records):
        answer = built.records[built.shuffled[at]].answer if shuffled else None
        lines.append(json.dumps({"messages": record.messages(answer)}, sort_keys=True))
    payload = "".join(f"{line}\n" for line in lines).encode("utf-8")
    (where / "train.jsonl").write_bytes(payload)
    manifest = {
        "repo": repo,
        "sha": built.sha,
        "corpus_hash": hashlib.sha256(payload).hexdigest(),
        "records": len(built.records),
        "seed": built.report["seed"],
        "control": shuffled,
        "max_chars": MAX_CHARS,
        "dropped": built.report["totals"]["dropped"],
        "rows": [
            {
                "repo": record.repo,
                "family": record.family,
                "source": record.source,
                "name": record.name,
                "answer_from": built.records[built.shuffled[at]].source if shuffled else record.source,
                "answer_family": built.records[built.shuffled[at]].family if shuffled else record.family,
                "chars": record.chars,
            }
            for at, record in enumerate(built.records)
        ],
    }
    (where / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8")
    return manifest
