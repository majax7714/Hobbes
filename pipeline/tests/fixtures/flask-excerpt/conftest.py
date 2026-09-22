# flask @ d73fa1c, tests/conftest.py (BSD-3-Clause) — see NOTICE.
# The `app` fixture verbatim; `Flask` comes from flask_app.py beside it.
import os

import pytest

from flask_app import Flask


@pytest.fixture
def app():
    app = Flask("flask_test", root_path=os.path.dirname(__file__))
    app.config.update(
        TESTING=True,
        SECRET_KEY="test key",
    )
    return app
