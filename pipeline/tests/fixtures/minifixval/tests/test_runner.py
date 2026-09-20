def test_runner(runner, made):
    assert runner.invoke(1) == 2
    assert runner.close() == "closed"
    assert runner.name == "runner"
    assert made.invoke(2) == 3
