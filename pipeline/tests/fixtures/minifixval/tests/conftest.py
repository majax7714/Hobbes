import pytest

from minifixval.runner import Runner, make_runner


@pytest.fixture
def runner():
    return Runner()


@pytest.fixture
def made():
    return make_runner()
