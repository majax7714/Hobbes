"""The orchestrator adapter (Calvin M0 step 4) against a fake endpoint: document parsing, one repair, round 1 → rebuild → round 2 → ground, the NULL round-trip on a narrowed template, the exchange record, and the §4.2 agreement scorer."""
import json

from hobbes.derive import adapter as A
from hobbes.derive import holes
from hobbes.derive import template as T
from tests.test_ground import ledger, repo  # noqa: F401  (the synthetic Go + Python + JS repo and its ledger)


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
    assert rec["loop"] == {"nulls_before": 1, "nulls_after": 0, "closed_by_class": {"near-miss": 1}, "opened_by_class": {}}
    assert rec["ground_after_loop"]["null"] == [] and "app.Run(app.Options{})" in rec["ground_after_loop"]["post"]["cmd/main.go"] and "func mergeRanges()" in rec["ground_after_loop"]["post"]["cmd/main.go"]
    assert len(rec["exchanges"]) == 3 and rec["tokens"]["prompt"] > 0 and rec["key"]["model_id"] == "fake-model" and rec["key"]["system_prompt_version"] == A.SYSTEM_PROMPT_VERSION


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

