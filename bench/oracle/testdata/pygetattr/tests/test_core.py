from pygetattr import core


def test_no_repo_code_runs_for_the_tracer():
    assert core.call_instance() == "called"
    assert core.call_wrapped() == 2
    assert core.call_method() == "pong"
    assert core.ASKED == []
