"""The orchestrator adapter (Calvin M0 step 4) against a fake endpoint: document parsing, one repair, round 1 → rebuild → round 2 → ground, the NULL round-trip on a narrowed template, the exchange record, and the §4.2 agreement scorer."""
import json
import subprocess

from hobbes.derive import adapter as A
from hobbes.derive import holes
from hobbes.derive import template as T
from tests.test_ground import ledger, repo  # noqa: F401  (the synthetic Go + Python + JS repo and its ledger)


def _git2(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, capture_output=True, text=True, check=True).stdout


class Fake:
    """An endpoint that answers from a queue and keeps what it was asked."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.asked = []

    def chat(self, messages, tools, max_tokens=None):
        self.asked.append(messages)
        text = self.replies.pop(0) if self.replies else "{}"
        return {"choices": [{"message": {"content": text}, "finish_reason": "stop"}], "usage": {"prompt_tokens": len(json.dumps(messages)) // 4, "completion_tokens": len(text) // 4}}


def test_parse_document_accepts_fences_and_prose():
    assert A.parse_document('{"fills": {}}') == {"fills": {}}
    assert A.parse_document('Sure.\n```json\n{"fills": {"h1": "unchanged"}}\n```\nDone.') == {"fills": {"h1": "unchanged"}}
    assert A.parse_document('here it is: {"fills": {"a": 1}} thanks') == {"fills": {"a": 1}}
    assert A.parse_document("no json here") is None and A.parse_document("[1, 2]") is None


def test_ask_validates_and_repairs_once(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Change `runGoRTA`.", L, root, None)
    body = next(h for h in t["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "cmd/main.runGoRTA")
    good = {"fills": {**{h["id"]: "unchanged" for h in t["holes"] if h["type"] in ("SIGNATURE", "BODY")}, body["id"]: {"code": "func runGoRTA() {}\n"},
                      **{h["id"]: {"confirm": False} for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM"},
                      **{h["id"]: {"classes": {x["term"]: "not-code" for x in h["terms"]}} for h in t["holes"] if h["type"] == "UNRESOLVED"},
                      next(h["id"] for h in t["holes"] if h["type"] == "FREEFORM"): "none"},
            "patterns": {"MODULE_REGION": "unchanged", "CALLER_UPDATE": "unchanged", "TEST_EXPECTATION": "unchanged", "COCHANGE_TOUCH": "unchanged"}}
    fake = Fake(['{"fills": {"' + body["id"] + '": {"code": 5}}}', json.dumps(good)])
    ad = A.Adapter(fake, "fake-model")
    doc, errs = ad.ask(t, root, "round 2")
    assert errs == {} and doc == good
    assert [e["purpose"] for e in ad.exchanges] == ["round 2", "round 2 (repair)"]
    assert ad.exchanges[0]["validation"] and body["id"] in ad.exchanges[0]["validation"]
    assert "did not validate" in fake.asked[1][-1]["content"] and fake.asked[1][0]["content"] == A.SYSTEM_PROMPT
    assert ad.exchanges[1]["prompt_tokens"] and ad.exchanges[1]["wall_ms"] >= 0
    # a second malformed answer is returned as it is, with its errors — the adapter repairs once
    fake2 = Fake(["nonsense", "still nonsense"])
    doc2, errs2 = A.Adapter(fake2, "fake-model").ask(t, root, "round 2")
    assert doc2 is None and "document" in errs2


def test_run_t_round1_opens_structure_then_grounds_and_loops(repo):
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA and add mergeRanges."  # `runGoRTA` is a bare identifier naming one node → ANCHOR_CONFIRM; mergeRanges is unresolved
    t = T.build_template(task, L, root, None)
    assert {h["type"] for h in t["holes"]} == {"UNRESOLVED", "ANCHOR_CONFIRM", "FREEFORM"}, "no structure until round 1"
    u = next(h for h in t["holes"] if h["type"] == "UNRESOLVED")
    c = next(h for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM")
    r1 = {"fills": {u["id"]: {"classes": {x["term"]: ("new" if x["term"] == "mergeRanges" else "not-code") for x in u["terms"]}}, c["id"]: {"confirm": True}}}

    def r2_for(t2, body_code):
        body = next(h for h in t2["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "cmd/main.runGoRTA")
        n = next(h for h in t2["holes"] if h["type"] == "NEW_SYMBOL")
        fills = {h["id"]: "unchanged" for h in t2["holes"] if h["type"] in ("SIGNATURE", "BODY") and h.get("closed") is None}
        fills[body["id"]] = {"code": body_code}
        fills[n["id"]] = {"name": "mergeRanges", "file": "cmd/main.go", "region": "eof", "body": "func mergeRanges() int { return 2 }\n"}
        fills[next(h["id"] for h in t2["holes"] if h["type"] == "FREEFORM")] = "none"
        return {"fills": fills, "patterns": {"MODULE_REGION": "unchanged", "CALLER_UPDATE": "unchanged", "TEST_EXPECTATION": "unchanged", "COCHANGE_TOUCH": "unchanged"}}

    t2_expected = T.apply_round1(task, L, root, None, t, r1["fills"])
    bad = "func runGoRTA() {\n\tmergeRanges()\n\thelpr()\n}\n"
    fixed = "func runGoRTA() {\n\tmergeRanges()\n\tapp.Run(app.Options{})\n}\n"
    body_id = next(h["id"] for h in t2_expected["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "cmd/main.runGoRTA")
    fake = Fake([json.dumps(r1), json.dumps(r2_for(t2_expected, bad)), json.dumps({"fills": {body_id: {"code": fixed}}})])
    ad = A.Adapter(fake, "fake-model")
    rec = A.run_t(task, t, L, root, None, ad)
    assert [r["round"] for r in rec["rounds"]] == [1, 2, 3]
    assert rec["rounds"][0]["holes_asked"] == [u["id"], c["id"]], "round 1 asks only the round-1 holes"
    t2 = rec["template_round2"]
    assert any(h["type"] == "BODY" for h in t2["holes"]) and next(h for h in t2["holes"] if h["type"] == "UNRESOLVED")["fill_source"].startswith("orchestrator")
    assert "Already answered (round 1)" in fake.asked[1][1]["content"]
    g = rec["ground"]
    assert [(n["term"], n["null_class"]) for n in g["null"]] == [("helpr", "near-miss")] and "mergeRanges" in g["gensyms"]
    narrowed = fake.asked[2][1]["content"]
    assert "NULL = `helpr`" in narrowed and "Your previous answer" in narrowed and "### " + body_id in narrowed
    assert narrowed.count("### ") == 1, "the narrowed template holds only the hole whose fill carried the NULL"
    assert {k: rec["loop"][k] for k in ("nulls_before", "nulls_after", "closed_by_class", "opened_by_class")} == {"nulls_before": 1, "nulls_after": 0, "closed_by_class": {"near-miss": 1}, "opened_by_class": {}}
    assert rec["loop"]["routes"] == {"re-ask": 1} and rec["loop"]["declaration_holes"] == [], "v0.4: a near-miss is re-asked at its hole, as in v0.3"
    assert [(s["term"], s["route"], s["closed"]) for s in rec["loop"]["sites"]] == [("helpr", "re-ask", True)]
    assert rec["ground_after_loop"]["null"] == [] and "app.Run(app.Options{})" in rec["ground_after_loop"]["post"]["cmd/main.go"] and "func mergeRanges()" in rec["ground_after_loop"]["post"]["cmd/main.go"]
    assert len(rec["exchanges"]) == 3 and rec["tokens"]["prompt"] > 0 and rec["key"]["model_id"] == "fake-model" and rec["key"]["system_prompt_version"] == A.SYSTEM_PROMPT_VERSION


def test_run_t_hands_the_rta_key_to_both_groundings(repo, monkeypatch):
    """M0-Go WP-5: rule 2's implementers come from an RTA key; arm T passes it to the grounding before the loop and after it."""
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA and add mergeRanges."
    t = T.build_template(task, L, root, None)
    u = next(h for h in t["holes"] if h["type"] == "UNRESOLVED")
    c = next(h for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM")
    r1 = {u["id"]: {"classes": {x["term"]: ("new" if x["term"] == "mergeRanges" else "not-code") for x in u["terms"]}}, c["id"]: {"confirm": True}}
    t2 = T.apply_round1(task, L, root, None, t, r1)
    body = next(h["id"] for h in t2["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "cmd/main.runGoRTA")
    fills = {h["id"]: "unchanged" for h in t2["holes"] if h["type"] in ("SIGNATURE", "BODY") and h.get("closed") is None}
    fills[body] = {"code": "func runGoRTA() {\n\tmergeRanges()\n\thelpr()\n}\n"}
    fills[next(h["id"] for h in t2["holes"] if h["type"] == "NEW_SYMBOL")] = {"name": "mergeRanges", "file": "cmd/main.go", "region": "eof", "body": "func mergeRanges() int { return 2 }\n"}
    fills[next(h["id"] for h in t2["holes"] if h["type"] == "FREEFORM")] = "none"
    r2 = {"fills": fills, "patterns": {"MODULE_REGION": "unchanged", "CALLER_UPDATE": "unchanged", "TEST_EXPECTATION": "unchanged", "COCHANGE_TOUCH": "unchanged"}}
    seen = []
    real = A.G.ground
    monkeypatch.setattr(A.G, "ground", lambda *a, **kw: (seen.append(kw.get("rta")), real(*a, **kw))[1])
    rta = {"source": "a key", "sites": {}}
    fake = Fake([json.dumps({"fills": r1}), json.dumps(r2), json.dumps({"fills": {body: {"code": "func runGoRTA() {\n\tmergeRanges()\n}\n"}}})])
    rec = A.run_t(task, t, L, root, None, A.Adapter(fake, "fake-model"), rta=rta)
    assert seen == [rta, rta], "the grounding before the loop and the one after it"
    assert rec["ground"]["rta"] == "a key" and rec["ground_after_loop"]["rta"] == "a key" and rec["loop"]["nulls_after"] == 0
    assert A.run_t.__kwdefaults__["rta"] is None, "without a key, as before"


def test_anchor_fill_binds_names_exactly(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Make it faster.", L, root, None)
    a = next(h for h in t["holes"] if h["type"] == "ANCHOR")
    t2 = T.apply_round1("Make it faster.", L, root, None, t, {a["id"]: {"names": ["Run", "cmd/main.go", "nothingLikeThis"]}})
    assert [(x["term"], x["nodes"]) for x in t2["anchors"]] == [("Run", ["internal/app/app.Run"]), ("cmd/main.go", ["cmd/main"])]
    assert any(h["type"] == "BODY" for h in t2["holes"])


def test_unresolved_agreement_against_gold(repo):
    root, sha = repo
    L = ledger(sha)
    hole = {"terms": [{"term": "mergeRanges"}, {"term": "Run"}, {"term": "go-rta"}]}
    fill = {"classes": {"mergeRanges": "new", "Run": "refers", "go-rta": "new"}}
    s = A.score_unresolved(fill, hole, L, {"internal/app/app.go"}, {"mergeRanges"})
    assert s["n"] == 3 and s["agree"] == 2
    assert [r["gold"] for r in s["rows"]] == ["new", "refers", "not-code"]


def test_refusing_every_confirmation_opens_an_anchor_hole_for_a_second_pass(repo):
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA please."  # one bare-identifier anchor → one ANCHOR_CONFIRM, no unresolved term (the planner's tokenizer keeps a trailing period, so the identifier must not end the sentence)
    t = T.build_template(task, L, root, None)
    c = next(h for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM")
    fake = Fake([json.dumps({"fills": {c["id"]: {"confirm": False}}}),
                 json.dumps({"fills": {"a1": {"names": ["Run", "noSuchThing"]}}}),
                 json.dumps({"fills": {}, "patterns": {"MODULE_REGION": "unchanged", "CALLER_UPDATE": "unchanged", "TEST_EXPECTATION": "unchanged", "COCHANGE_TOUCH": "unchanged"}})])
    ad = A.Adapter(fake, "fake-model")
    rec = A.run_t(task, t, L, root, None, ad)
    assert [r["round"] for r in rec["rounds"]] == [1, "1b", 2]
    assert rec["rounds"][0]["holes_asked"] == [c["id"]] and rec["rounds"][1]["holes_asked"] == ["a1"]
    assert rec["rounds"][1]["anchor_names_unbound"] == ["noSuchThing"]
    t2 = rec["template_round2"]
    assert [a["term"] for a in t2["anchors"]] == ["Run"] and not any(h["type"] == "ANCHOR_CONFIRM" and "fill" not in h for h in t2["holes"]), "the refused confirmation stays refused, and is shown answered"
    assert next(h for h in t2["holes"] if h["id"] == c["id"])["fill"] == {"confirm": False}
    assert any(h["type"] == "BODY" and h["provenance"]["symbol"] == "internal/app/app.Run" for h in t2["holes"])
    assert "ANCHOR" in {h["type"] for h in t2["holes"]} and next(h for h in t2["holes"] if h["type"] == "ANCHOR")["fill_source"].startswith("orchestrator")
    assert rec["ground"]["unfilled"], "round 2 answered nothing for the structure: silence is reported, not accepted"
    # the second pass showed candidates: the refused word marked, and the file listing the orchestrator can choose from
    prompt_1b = fake.asked[1][-1]["content"]
    assert "Candidates from Hobbes" in prompt_1b and "refused as a site in round 1" in prompt_1b and "app/app.go" in prompt_1b
    a1 = next(h for h in rec["template_round1"]["holes"] if h["type"] == "ANCHOR") if any(h["type"] == "ANCHOR" for h in rec["template_round1"]["holes"]) else None
    assert a1 is None, "the first template had anchors; the ANCHOR hole opened on the rebuild"


FOUR = {"MODULE_REGION": "unchanged", "CALLER_UPDATE": "unchanged", "TEST_EXPECTATION": "unchanged", "COCHANGE_TOUCH": "unchanged"}


def test_v03_signature_and_body_patterns_are_read_unchanged_with_no_repair(repo):
    """Protocol v0.3: a SIGNATURE/BODY pattern is accepted on the first pass, read per hole as "unchanged", recorded as by pattern — and grounds exactly as the per-hole answers."""
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Change `runGoRTA`.", L, root, None)
    body = next(h for h in t["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "cmd/main.runGoRTA")
    rest = {**{h["id"]: {"confirm": False} for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM"},
            **{h["id"]: {"classes": {x["term"]: "not-code" for x in h["terms"]}} for h in t["holes"] if h["type"] == "UNRESOLVED"},
            next(h["id"] for h in t["holes"] if h["type"] == "FREEFORM"): "none", body["id"]: {"code": "func runGoRTA() {}\n"}}
    explicit = {"fills": {**{h["id"]: "unchanged" for h in t["holes"] if h["type"] in ("SIGNATURE", "BODY")}, **rest}, "patterns": FOUR}
    fake = Fake([json.dumps({"fills": rest, "patterns": {**FOUR, "SIGNATURE": "unchanged", "BODY": "unchanged"}})])
    ad = A.Adapter(fake, "fake-model")
    doc, errs = ad.ask(t, root, "round 2")
    assert errs == {} and [e["purpose"] for e in ad.exchanges] == ["round 2"] and ad.exchanges[0]["validation"] == {}
    assert ad.exchanges[0]["protocol_version"] == A.PROTOCOL_VERSION == "0.6", "v0.3's reading stands under v0.6"
    patterned = {h["id"] for h in t["holes"] if h["type"] in ("SIGNATURE", "BODY") and h["id"] != body["id"]}
    assert patterned and set(doc["by_pattern"]) == patterned and doc["fills"][body["id"]] == {"code": "func runGoRTA() {}\n"}
    g1 = A.G.ground(json.loads(json.dumps(t)), doc, L, root)
    g2 = A.G.ground(json.loads(json.dumps(t)), explicit, L, root)
    assert g1["output_hash"] == g2["output_hash"] and g1["closed_by_prune"] == g2["closed_by_prune"], "read by pattern = answered one by one"


def test_v03_a_confirmation_pattern_is_a_refusal_recorded_by_pattern_and_not_carried(repo):
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA please."  # one ANCHOR_CONFIRM, no unresolved term (as in the refusal test above)
    t = T.build_template(task, L, root, None)
    c = next(h for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM")
    fake = Fake([json.dumps({"fills": {}, "patterns": {"ANCHOR_CONFIRM": "unchanged"}}),
                 json.dumps({"fills": {"a1": {"names": ["Run"]}}}),
                 json.dumps({"fills": {}, "patterns": FOUR})])
    rec = A.run_t(task, t, L, root, None, A.Adapter(fake, "fake-model"))
    r1 = rec["rounds"][0]
    assert r1["errors"] == {} and r1["fills"]["by_pattern"] == {c["id"]: "ANCHOR_CONFIRM"}
    assert r1["pattern_confirmations"] == 1 and r1["unanswered_confirmations"] == 0
    assert [e["purpose"] for e in rec["exchanges"]][:2] == ["round 1", "round 1b"], "no repair; refused, so the rebuild opens the ANCHOR hole"
    assert c["id"] not in {h["id"] for h in rec["template_round2"]["holes"]}, "a refusal by pattern is not carried into round 2, like one by silence"
    assert rec["key"]["protocol_version"] == "0.6"


def _r2_calling(t2, body_code):
    """Round 2 for "Fix runGoRTA and add mergeRanges.": runGoRTA's body rewritten, mergeRanges placed, the rest unchanged."""
    body = next(h for h in t2["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "cmd/main.runGoRTA")
    fills = {h["id"]: "unchanged" for h in t2["holes"] if h["type"] in ("SIGNATURE", "BODY") and h.get("closed") is None}
    fills[body["id"]] = {"code": body_code}
    fills[next(h["id"] for h in t2["holes"] if h["type"] == "NEW_SYMBOL")] = {"name": "mergeRanges", "file": "cmd/main.go", "region": "eof", "body": "func mergeRanges() int { return 2 }\n"}
    fills[next(h["id"] for h in t2["holes"] if h["type"] == "FREEFORM")] = "none"
    return body["id"], {"fills": fills, "patterns": FOUR}


def _round1(t):
    u = next(h for h in t["holes"] if h["type"] == "UNRESOLVED")
    c = next(h for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM")
    return {u["id"]: {"classes": {x["term"]: ("new" if x["term"] == "mergeRanges" else "not-code") for x in u["terms"]}}, c["id"]: {"confirm": True}}


def test_v04_an_undeclared_name_gets_a_declaration_hole_not_a_re_ask(repo):
    """Protocol v0.4 (M0-Go WP-7a; WP-6's D-b): a name written at a call site and declared nowhere is offered as a NEW_SYMBOL declaration
    hole — the hole that wrote the call is not asked again — and once placed it binds as a gensym where it was called."""
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA and add mergeRanges."
    t = T.build_template(task, L, root, None)
    r1 = _round1(t)
    t2 = T.apply_round1(task, L, root, None, t, r1)
    body_id, r2 = _r2_calling(t2, "func runGoRTA() {\n\tmergeRanges()\n\tapp.Launch(app.Options{})\n}\n")
    decl = {"fills": {"d1": {"name": "Launch", "file": "internal/app/launch.go", "region": "eof",
                             "body": "package app\n\n// Launch starts one run.\nfunc Launch(o Options) error { return Run(o) }\n"}}}
    fake = Fake([json.dumps({"fills": r1}), json.dumps(r2), json.dumps(decl)])
    rec = A.run_t(task, t, L, root, None, A.Adapter(fake, "fake-model"))
    assert [(n["term"], n["null_class"], n["scope"]) for n in rec["ground"]["null"]] == [("app.Launch", "invented", {"dir": "internal/app"})]
    asked = fake.asked[2][1]["content"]
    assert "### d1 · NEW_SYMBOL — declare `Launch`" in asked and "### " + body_id not in asked and asked.count("### ") == 1, "declared, not re-asked"
    assert "binds only in the directory `internal/app/`" in asked and "Files of the write partition there: `internal/app/app.go`" in asked
    assert "call_site = cmd/main.go:11: `app.Launch(app.Options{})`" in asked, "the line written at the call site, from the post-image"
    d1 = rec["template_round3"]["holes"][0]
    assert d1["constraints"]["declares"] == {"name": "Launch", "term": "app.Launch", "dir": "internal/app", "type": None}
    assert all(p in t2["constraints"]["write_partition"] for p in d1["constraints"]["write_partition"]), "the partition is not widened"
    g2 = rec["ground_after_loop"]
    assert g2["null"] == [] and "Launch" in g2["gensyms"] and "func Launch(o Options) error" in g2["post"]["internal/app/launch.go"]
    assert [r["class"] for r in g2["refs"] if r["term"] == "app.Launch"] == ["gensym"], "the call site grounded again binds the declaration"
    assert rec["loop"]["closed_by_class"] == {"invented": 1} and rec["loop"]["routes"] == {"declare": 1} and rec["loop"]["declaration_holes"] == ["d1"]
    assert rec["loop"]["sites"] == [{"hole": body_id, "path": "cmd/main.go", "line": 11, "term": "app.Launch", "null_class": "invented", "route": "declare",
                                     "closed": True, "declaration": "d1", "answer": "placed", "file": "internal/app/launch.go", "in_partition": False,
                                     "body_nulls": 0, "repaired": False}]
    assert [r["round"] for r in rec["rounds"]] == [1, 2, 3] and rec["rounds"][2]["holes_asked"] == ["d1"]
    assert rec["loop"]["declaration_repair"] is None and "template_repair" not in rec, "a body that grounds clean is not repaired"
    assert {e["protocol_version"] for e in rec["exchanges"]} == {"0.6"} and rec["key"]["protocol_version"] == "0.6"


def test_v04_declaration_answers_are_checked_and_two_names_may_share_one_new_file(repo):
    """A declaration answer names the hole's name, in the directory it binds in, with a body that declares it — else a repairable error
    naming the hole; a second name declared by the first answer's body is covered_by it (one new file, two declarations)."""
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA and add mergeRanges."
    t = T.build_template(task, L, root, None)
    r1 = _round1(t)
    t2 = T.apply_round1(task, L, root, None, t, r1)
    _, r2 = _r2_calling(t2, "func runGoRTA() {\n\tmergeRanges()\n\tapp.Launch(app.Options{})\n\tapp.Shutdown()\n}\n")
    wrong = {"fills": {"d1": {"name": "Launch", "file": "cmd/launch.go", "region": "eof", "body": "package main\n\nfunc Launch() {}\n"},
                       "d2": {"name": "Stop", "file": "internal/app/halt.go", "region": "eof", "body": "package app\n\nfunc Stop() {}\n"}}}
    right = {"fills": {"d1": {"name": "Launch", "file": "internal/app/life.go", "region": "eof",
                              "body": "package app\n\nfunc Launch(o Options) error { return Run(o) }\n\nfunc Shutdown() {}\n"},
                       "d2": {"covered_by": ["d1"]}}}
    fake = Fake([json.dumps({"fills": r1}), json.dumps(r2), json.dumps(wrong), json.dumps(right)])
    rec = A.run_t(task, t, L, root, None, A.Adapter(fake, "fake-model"))
    ex = rec["exchanges"]
    assert [e["purpose"] for e in ex][-2:] == ["NULL round-trip", "NULL round-trip (repair)"]
    v = ex[-2]["validation"]
    assert set(v) == {"d1", "d2"} and "binds only in the directory `internal/app/`" in v["d1"][0]
    assert v["d2"] == ["this hole declares `Shutdown`: name must be 'Shutdown'", "the body does not declare `Shutdown`"]
    assert "- d1: " in fake.asked[3][-1]["content"] and "- d2: " in fake.asked[3][-1]["content"]
    g2 = rec["ground_after_loop"]
    assert g2["null"] == [] and rec["loop"]["nulls_before"] == 2
    assert [(s["term"], s["declaration"], s["answer"], s["file"], s["closed"]) for s in rec["loop"]["sites"]] == [
        ("app.Launch", "d1", "placed", "internal/app/life.go", True), ("app.Shutdown", "d2", "covered_by d1", "internal/app/life.go", True)]


def test_v04_a_body_carrying_the_render_gutter_is_refused_and_repaired(repo):
    """Protocol v0.4 (WP-6's D-a): a BODY fill that copies the render's line-number gutter is a repairable error naming the hole; a
    grounding handed it anyway refuses the fill and writes nothing for it."""
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Change `runGoRTA`.", L, root, None)
    body = next(h for h in t["holes"] if h["type"] == "BODY" and h["provenance"]["symbol"] == "cmd/main.runGoRTA")
    rest = {**{h["id"]: "unchanged" for h in t["holes"] if h["type"] in ("SIGNATURE", "BODY")},
            **{h["id"]: {"confirm": False} for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM"},
            **{h["id"]: {"classes": {x["term"]: "not-code" for x in h["terms"]}} for h in t["holes"] if h["type"] == "UNRESOLVED"},
            next(h["id"] for h in t["holes"] if h["type"] == "FREEFORM"): "none"}
    copied = holes.span_text(root, sha, body["span"])  # exactly what the render showed for the span
    assert copied in holes.render(t, root)
    gutter = {"fills": {**rest, body["id"]: {"code": copied.replace("app.Run(", "app.Run(app.Options{}) //", 1)}}, "patterns": FOUR}
    clean = {"fills": {**rest, body["id"]: {"code": "func runGoRTA() {\n\tapp.Run(app.Options{})\n}\n"}}, "patterns": FOUR}
    fake = Fake([json.dumps(gutter), json.dumps(clean)])
    ad = A.Adapter(fake, "fake-model")
    doc, errs = ad.ask(t, root, "round 2")
    assert ad.exchanges[0]["validation"] == {body["id"]: [holes.GUTTER_ERROR]} and errs == {} and doc == clean
    assert f"- {body['id']}: {holes.GUTTER_ERROR}" in fake.asked[1][-1]["content"]
    g = A.G.ground(json.loads(json.dumps(t)), gutter, L, root)
    assert g["refused"] == [{"hole": body["id"], "errors": [holes.GUTTER_ERROR]}] and g["diff"] == ""


DECL_OUTSIDE = "package app\n\nimport \"github.com/securego/gosec/v2\"\n\n// Launch starts one run.\nfunc Launch(o Options) gosec.Rule {\n\tcore.Start()\n\treturn nil\n}\n"
DECL_INSIDE = "package app\n\n// Launch starts one run.\nfunc Launch(o Options) error { return Run(o) }\n"


def _loop_on(repo, body_code, *replies):
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA and add mergeRanges."
    t = T.build_template(task, L, root, None)
    r1 = _round1(t)
    t2 = T.apply_round1(task, L, root, None, t, r1)
    _, r2 = _r2_calling(t2, body_code)
    fake = Fake([json.dumps({"fills": r1}), json.dumps(r2), *replies])
    return A.run_t(task, t, L, root, None, A.Adapter(fake, "fake-model")), fake, L, root


def test_v05_a_declaration_body_outside_the_world_is_repaired_once(repo):
    """Protocol v0.5 (M0-Go WP-9; WP-8's D-g): a placed declaration whose body imports outside the world or qualifies with a package it
    does not import raises NULLs at the grounder, inside the declaration; they go back once, as a repair of that same hole — one
    exchange, no validation repair after it — and a repair that does not validate leaves the body's NULLs standing in the record."""
    call = "func runGoRTA() {\n\tmergeRanges()\n\tapp.Launch(app.Options{})\n}\n"
    bad = json.dumps({"fills": {"d1": {"name": "Launch", "file": "internal/app/launch.go", "region": "eof", "body": DECL_OUTSIDE}}})
    good = json.dumps({"fills": {"d1": {"name": "Launch", "file": "internal/app/launch.go", "region": "eof", "body": DECL_INSIDE}}})
    rec, fake, _, _ = _loop_on(repo, call, bad, good)
    assert [e["purpose"] for e in rec["exchanges"]][-2:] == ["NULL round-trip", "declaration repair"]
    before = rec["ground_before_repair"]
    assert sorted((n["term"], n["null_class"], n["hole"]) for n in before["null"]) == [("core.Start", "unimported", "d1"), ("github.com/securego/gosec/v2", "import-outside", "d1")]
    asked = fake.asked[3][1]["content"]
    assert asked.count("### ") == 1 and "### d1 · NEW_SYMBOL — repair your declaration of `Launch`" in asked, "the same declaration hole, nothing else"
    assert "NULL in your declaration = `core.Start`" in asked and "import-outside" in asked and "Your previous answer" in asked
    assert rec["rounds"][-1]["round"] == "3r" and rec["rounds"][-1]["taken"] == ["d1"] and rec["template_repair"]["holes"][0]["id"] == "d1"
    assert rec["ground_after_loop"]["null"] == [] and rec["loop"]["nulls_after"] == 0 and "func Launch(o Options) error" in rec["ground_after_loop"]["post"]["internal/app/launch.go"]
    assert rec["loop"]["declaration_repair"] == {"asked": ["d1"], "taken": ["d1"], "exchanges": 1, "body_nulls_before": [
        {"hole": "d1", "line": 7, "term": "core.Start", "null_class": "unimported", "kind": "call"},
        {"hole": "d1", "line": 3, "term": "github.com/securego/gosec/v2", "null_class": "import-outside", "kind": "import"}], "body_nulls_after": [],
        "build_errors_before": {}, "build_row": {"ran": False}}, "v0.6: no build check unless verify_build=True; unaffected here"
    s = rec["loop"]["sites"][0]
    assert (s["closed"], s["answer"], s["body_nulls"], s["repaired"]) == (True, "placed", 0, True)
    assert {e["protocol_version"] for e in rec["exchanges"]} == {"0.6"}
    rec2, fake2, _, _ = _loop_on(repo, call, bad, "not json")
    assert [e["purpose"] for e in rec2["exchanges"]][-2:] == ["NULL round-trip", "declaration repair"] and len(fake2.asked) == 4, "bounded: one exchange"
    assert rec2["rounds"][-1]["taken"] == [] and rec2["loop"]["nulls_after"] == 2 and rec2["loop"]["opened_by_class"] == {"unimported": 1, "import-outside": 1}
    s2 = rec2["loop"]["sites"][0]
    assert (s2["closed"], s2["answer"], s2["body_nulls"], s2["repaired"]) == (True, "placed", 2, True), "the call site binds; its declaration's body does not"


def test_v05_a_refused_declaration_reads_refused_in_the_site_record(repo):
    """WP-8's D-f: two declaration answers that each write the same new file — the grounder places the first and refuses the second as
    overlapping; the site record reads the refused list, so the second reads `refused`, not `placed`."""
    call = "func runGoRTA() {\n\tmergeRanges()\n\tapp.Launch(app.Options{})\n\tapp.Shutdown()\n}\n"
    both = json.dumps({"fills": {"d1": {"name": "Launch", "file": "internal/app/life.go", "region": "eof", "body": DECL_INSIDE},
                                 "d2": {"name": "Shutdown", "file": "internal/app/life.go", "region": "eof", "body": "package app\n\nfunc Shutdown() {}\n"}}})
    rec, _, _, _ = _loop_on(repo, call, both)
    g2 = rec["ground_after_loop"]
    assert [x["hole"] for x in g2["refused"]] == ["d2"] and "overlaps d1" in g2["refused"][0]["reason"]
    assert [(s["term"], s["answer"], s["closed"], s["file"]) for s in rec["loop"]["sites"]] == [
        ("app.Launch", "placed", True, "internal/app/life.go"), ("app.Shutdown", "refused", False, None)]
    assert rec["loop"]["refused_declarations"] == ["d2"] and rec["loop"]["declaration_repair"] is None


def test_v05_the_declaration_hole_shows_a_sibling_of_the_same_kind(repo):
    """WP-8's D-h: the declaration hole shows one existing declaration of its kind from the binding directory — the one the same fill
    calls nearest the call site, else the one with the most callers there — with its file's package and imports, its signature and
    the head of its body, capped."""
    call = "func runGoRTA() {\n\tmergeRanges()\n\tapp.Run(app.Options{})\n\tapp.Launch(app.Options{})\n}\n"
    rec, fake, L, root = _loop_on(repo, call, json.dumps({"fills": {"d1": {"name": "Launch", "file": "internal/app/launch.go", "region": "eof", "body": DECL_INSIDE}}}))
    sib = rec["template_round3"]["holes"][0]["sibling"]
    assert (sib["symbol"], sib["rule"], sib["package"], sib["imports"], sib["more_lines"]) == ("internal/app/app.Run", "called nearest the call site by the same fill", "app", ['"fmt"'], 0)
    assert sib["text"] == 'func Run(o Options) error {\n\tfmt.Println("go-rta", o.Repo)\n\treturn nil\n}'
    asked = fake.asked[2][1]["content"]
    assert "A sibling of the same kind, for its form (called nearest the call site by the same fill): `internal/app/app.Run`" in asked
    assert "whose file is `package app` and imports `\"fmt\"`" in asked and "```go\nfunc Run(o Options) error {" in asked and "as the sibling below does" in asked
    none = {"refs": []}
    s = A.declaration_sibling({"name": "launchAll", "dir": "cmd", "type": None}, {"hole": "x", "path": "cmd/main.go", "line": 6}, none, L, root)
    assert (s["symbol"], s["rule"]) == ("cmd/main.runGoRTA", "the most callers in the directory"), "no co-callee: main calls runGoRTA, nothing calls main"
    assert A.declaration_sibling({"name": "Validate", "dir": "internal/app", "type": "Options"}, {"hole": "x", "path": "cmd/main.go", "line": 6}, none, L, root) is None, "no method of the type"
    assert A.declaration_sibling({"name": "x", "dir": None, "type": None}, {"hole": "x", "path": "a.py", "line": 1}, none, L, root) is None


def test_v06_sibling_shown_whole_capped_by_bytes_not_lines(repo):
    """v0.6 (D-h): the sibling is the whole span (every line), capped only by ``SIBLING_BYTES`` — not by a line count, as v0.5's
    ``SIBLING_LINES`` (12) did. A function under the cap (`app.Run`, 3 lines) is shown entire regardless of line count; one over
    the cap is cut at the byte boundary, `more_lines` naming what was cut."""
    root, sha = repo
    L = ledger(sha)
    none = {"refs": []}
    sib = A.declaration_sibling({"name": "helper", "dir": "internal/app", "type": None}, {"hole": "x", "path": "cmd/main.go", "line": 1}, none, L, root)
    assert sib["symbol"] == "internal/app/app.Run" and sib["more_lines"] == 0, "under the cap: shown whole, however many lines"
    big = "package app\n\n" + "\n".join(f"func line{i:04d}() {{ x := {i}; _ = x }}" for i in range(400)) + "\n"
    (root / "internal" / "app" / "big.go").write_text(big)
    _git2(root, "add", ".")
    _git2(root, "commit", "-q", "-m", "a function bigger than the byte cap")
    sha2 = _git2(root, "rev-parse", "HEAD").strip()
    L2 = T.Ledger({**L.graph, "sha": sha2, "symbols": L.graph["symbols"] + [
        {"id": "internal/app/big.Huge", "module": "internal/app/big", "name": "Huge", "qualname": "Huge", "kind": "function", "line": 3, "end_line": 402}],
        "nodes": L.graph["nodes"] + [{"id": "internal/app/big", "kind": "module", "path": "internal/app/big.go"}]}, {"tests": []})
    sib2 = A.declaration_sibling({"name": "helper2", "dir": "internal/app", "type": None}, {"hole": "x", "path": "cmd/main.go", "line": 1}, none, L2, root)
    assert sib2["symbol"] in ("internal/app/big.Huge", "internal/app/app.Run", "internal/app/app.helper")  # whichever the "most callers" tie-break picks
    huge = A.declaration_sibling({"name": "helper3", "dir": "internal/app", "type": None}, {"hole": "x", "path": "internal/app/big.go", "line": 5},
                                  {"refs": [{"hole": "x", "path": "internal/app/big.go", "class": "in-graph", "target": "internal/app/big.Huge", "line": 5}]}, L2, root)
    assert huge["symbol"] == "internal/app/big.Huge" and huge["more_lines"] > 0, "over the byte cap: cut, not shown whole"
    assert len(huge["text"].encode()) <= A.SIBLING_BYTES


def test_anchor_answer_may_be_a_candidate_node_id(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Make it faster.", L, root, None)
    a = next(h for h in t["holes"] if h["type"] == "ANCHOR")
    node = next(iter(sorted(L.mod_path)))  # a module id straight from the candidates' file listing
    t2 = T.apply_round1("Make it faster.", L, root, None, t, {a["id"]: {"names": [node]}})
    assert [(x["term"], x["nodes"]) for x in t2["anchors"]] == [(node, [node])]


def test_callers_render_compact_and_yes_fetches_the_span(repo):
    root, sha = repo
    L = ledger(sha)
    task = "Change `Run`."
    t = T.build_template(task, L, root, None)
    r1 = {"fills": {h["id"]: {"confirm": True} for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM"}}  # `Run` is matched by a name one node carries: confirmable
    t2 = T.apply_round1(task, L, root, None, t, r1["fills"])
    caller = next(h for h in t2["holes"] if h["type"] == "CALLER_UPDATE" and h["span"]["path"] == "internal/app/app.go")
    section = holes.render(t2, root).split("### " + caller["id"])[1].split("\n### ")[0]
    assert "func helper() int" in section and "whole span next" not in section, "a one-line caller: its whole span is one line, so nothing is elided"
    fills = {h["id"]: "unchanged" for h in t2["holes"] if h["type"] in ("SIGNATURE", "BODY")}
    sig = next(h for h in t2["holes"] if h["type"] == "SIGNATURE" and h["provenance"]["symbol"] == "internal/app/app.Run")
    fills[sig["id"]] = {"signature": "func Run(o Options, verbose bool) error {"}  # a changed signature keeps the caller hole open
    fills[caller["id"]] = {"decision": "yes", "reason": "it must pass the new option"}
    fills[next(h["id"] for h in t2["holes"] if h["type"] == "FREEFORM")] = "none"
    r2 = {"fills": fills, "patterns": {"MODULE_REGION": "unchanged", "TEST_EXPECTATION": "unchanged", "COCHANGE_TOUCH": "unchanged", "CALLER_UPDATE": "unchanged"}}
    r2b = {"fills": {caller["id"]: {"decision": "yes", "reason": "as said", "body": "func helper() int { Run(Options{Repo: \"x\"}); return 1 }\n"}}}
    fake = Fake([json.dumps(r1), json.dumps(r2), json.dumps(r2b)])
    rec = A.run_t(task, t, L, root, None, A.Adapter(fake, "fake-model"))
    assert [r["round"] for r in rec["rounds"]] == [1, 2, "2b"] and rec["rounds"][2]["holes_asked"] == [caller["id"]]
    followup = fake.asked[2][1]["content"]
    assert "here is the whole span" in followup and "Your previous answer" in followup and "```" in followup
    assert rec["ground"]["null"] == [] and 'Repo: "x"' in rec["ground"]["post"]["internal/app/app.go"]


def test_chunking_splits_a_long_template_by_file(repo):
    root, sha = repo
    L = ledger(sha)
    t = T.build_template("Change `Run` and `runGoRTA`.", L, root, None)
    whole = len(holes.render(t, root))
    chunks = A.chunk_by_file(t, root, whole // 2)
    assert len(chunks) >= 2 and sum(len(c["holes"]) for c in chunks) == len([h for h in t["holes"] if h.get("closed") is None and "fill" not in h])
    assert all(len(holes.render(c, root)) <= whole for c in chunks)
    paths = [{(h.get("span") or {}).get("path") for h in c["holes"]} for c in chunks]
    assert not any((paths[i] & paths[j]) - {None} for i in range(len(paths)) for j in range(i + 1, len(paths))), "each file's holes sit in one chunk"
    # asked in chunks: a pattern in one chunk covers that chunk's holes only; the merged document validates
    replies = []
    for c in chunks:
        f = {h["id"]: "unchanged" for h in c["holes"] if h["type"] in ("SIGNATURE", "BODY", "MODULE_REGION", "TEST_EXPECTATION")}
        f.update({h["id"]: "none" for h in c["holes"] if h["type"] == "FREEFORM"})
        f.update({h["id"]: {"confirm": False} for h in c["holes"] if h["type"] == "ANCHOR_CONFIRM"})
        f.update({h["id"]: {"classes": {x["term"]: "not-code" for x in h["terms"]}} for h in c["holes"] if h["type"] == "UNRESOLVED"})
        replies.append(json.dumps({"fills": f, "patterns": {"CALLER_UPDATE": "unchanged", "COCHANGE_TOUCH": "unchanged"}}))
    ad = A.Adapter(Fake(replies), "fake-model", max_prompt_chars=whole // 2)
    doc, errs = ad.ask(t, root, "round 2")
    assert errs == {} and len(ad.exchanges) == len(chunks) and all("[chunk" in e["purpose"] for e in ad.exchanges)
    assert holes.validate_fills(t, doc) == {}


def test_module_symbols_unanswered_are_refusals_and_not_carried(repo):
    """Step 6's first fix through run_t: a named module's symbols are asked in round 1; the one confirmed becomes the structure, the unanswered are recorded as refusals and never rendered as answered holes."""
    root, sha = repo
    L = ledger(sha)
    task = "Tidy up `app.go`."
    t = T.build_template(task, L, root, None)
    run = next(h for h in t["holes"] if h["type"] == "ANCHOR_CONFIRM" and h["provenance"]["symbol"] == "internal/app/app.Run")
    fake = Fake([json.dumps({"fills": {run["id"]: {"confirm": True}}}),
                 json.dumps({"fills": {}, "patterns": {"MODULE_REGION": "unchanged", "CALLER_UPDATE": "unchanged", "TEST_EXPECTATION": "unchanged", "COCHANGE_TOUCH": "unchanged"}})])
    ad = A.Adapter(fake, "fake-model")
    rec = A.run_t(task, t, L, root, None, ad)
    assert [r["round"] for r in rec["rounds"]] == [1, 2] and rec["rounds"][0]["unanswered_confirmations"] == 2
    t2 = rec["template_round2"]
    assert {h["provenance"]["symbol"] for h in t2["holes"] if h["type"] == "BODY"} == {"internal/app/app.Run"}, "the confirmed symbol alone (this ledger's Run uses no type)"
    answered = [h for h in t2["holes"] if "fill" in h]
    assert [h["id"] for h in answered] == [run["id"]], "only the confirmed symbol is shown as answered; the refusals are recorded, not rendered"
    assert "unanswered counts as" in fake.asked[0][0]["content"] and "Already answered" in fake.asked[1][-1]["content"]


def test_v06_budget_stops_calls_and_the_run_is_scored_as_it_stands(repo):
    """calvin-m0-go-r2 §2.4: one budget shared by both arms. With ``budget=1``, T's round-1 ask is the only call made — every
    later ask (round 2 here) is skipped without a call, no exception, no partial exchange — and the run still completes: an
    unanswered hole grounds as nothing filled (calvin-m0-go-r2 WP-14's reading, stated in the report), never a crash."""
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA and add mergeRanges."
    t = T.build_template(task, L, root, None)
    r1 = _round1(t)
    fake = Fake([json.dumps({"fills": r1})])  # one reply queued: a second call would exhaust it and read "{}" — the assertion below is the real guard
    ad = A.Adapter(fake, "fake-model", budget=1)
    assert not ad.at_budget()
    rec = A.run_t(task, t, L, root, None, ad)
    assert len(ad.exchanges) == 1 and ad.exchanges[0]["purpose"] == "round 1" and ad.at_budget()
    assert ad.budget_cuts >= 1, "round 2 (at least) was asked for and cut, not skipped for having nothing to ask"
    assert rec["rounds"][1]["round"] == 2 and rec["rounds"][1]["fills"] == {"fills": {}, "patterns": {}} and rec["rounds"][1]["errors"] == {}
    assert rec["ground"]["diff"] == "", "no fill was taken: nothing to write"
    assert "loop" not in rec, "no NULL to loop on when nothing was filled"


def test_v06_is_loop_exchange_covers_declaration_repair_too(repo):
    """D-i: the driver's ``usd_loop``/``usd_T`` split (`calvin_probe.cmd_t_units`) now reads `is_loop_exchange`, which the
    round-1 driver's own ``purpose.startswith("NULL")`` test missed for "declaration repair" — its dollars landed in ``usd_T``.
    Chunk and validation-repair suffixes are stripped first."""
    assert A.is_loop_exchange("NULL round-trip") and A.is_loop_exchange("declaration repair")
    assert A.is_loop_exchange("NULL round-trip [chunk 1/2]") and A.is_loop_exchange("declaration repair (repair)")
    assert not A.is_loop_exchange("round 2") and not A.is_loop_exchange("round 2b") and not A.is_loop_exchange("round 1 (repair)")


def test_v06_the_round2_record_is_not_mutated_by_round_2bs_later_merge(repo):
    """D-n: `run_t` used to hand `rec["rounds"]` a *reference* to round 2's fills document, then mutate that same object in
    place once round 2b's rewrites arrived — the recorded round-2 row silently came to reflect round 2b's answers too. It now
    keeps a copy at append time; round 2b still merges into the live document the grounder reads."""
    root, sha = repo
    L = ledger(sha)
    task = "Fix runGoRTA and add mergeRanges."
    t = T.build_template(task, L, root, None)
    r1 = _round1(t)
    t2 = T.apply_round1(task, L, root, None, t, r1)
    caller = next(h for h in t2["holes"] if h["type"] == "CALLER_UPDATE")  # this task/repo always opens at least one (h5: main calls runGoRTA)
    body_id, r2 = _r2_calling(t2, "func runGoRTA() {\n\tmergeRanges()\n}\n")
    r2["fills"][caller["id"]] = {"decision": "yes", "reason": "it changed"}  # a "yes" without a body: round 2b must be asked for the rewrite
    r2b_body = "func main() {\n\trunGoRTA()\n\t// touched by round 2b\n}\n"
    r2b = json.dumps({"fills": {caller["id"]: {"decision": "yes", "reason": "it changed", "body": r2b_body}}})
    fake = Fake([json.dumps({"fills": r1}), json.dumps(r2), r2b])
    rec = A.run_t(task, t, L, root, None, A.Adapter(fake, "fake-model"))
    assert [r["round"] for r in rec["rounds"]] == [1, 2, "2b"], "round 2b really fired: the mutation this test guards against had something to mutate"
    r2_row = next(r for r in rec["rounds"] if r["round"] == 2)
    assert r2_row["fills"]["fills"][caller["id"]] == {"decision": "yes", "reason": "it changed"}, \
        "the recorded round-2 row keeps round 2's own answer (no body) — D-n: it must not pick up round 2b's later merge"
    r2b_row = next(r for r in rec["rounds"] if r["round"] == "2b")
    assert (r2b_row["fills"]["fills"][caller["id"]] or {}).get("body") == r2b_body
    # the live document the grounder reads (`doc2`, passed to `G.ground` below run_t's own frame) is the one round 2b's merge
    # updates in place — that merge is intentional (§ "carry_round1"'s counterpart for round 2); only the *recorded* round-2
    # row must not move with it, which the two assertions above already show.

