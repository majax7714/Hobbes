def test_held(held):
    assert held.invoke(3) == 4
    assert held.close() == "closed"
