# flask @ d73fa1c, src/flask/app.py (BSD-3-Clause) — see NOTICE.
# Signatures verbatim; the body is shortened.
from __future__ import annotations

import typing as t

from app import App


class Flask(App):
    def test_client(self, use_cookies: bool = True, **kwargs: t.Any) -> t.Any:
        return self.test_client_class(self, use_cookies=use_cookies, **kwargs)
