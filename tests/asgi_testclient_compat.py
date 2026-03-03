"""Compatibility TestClient for environments where starlette TestClient blocks.

This wrapper keeps the synchronous TestClient-like API used by existing tests
while dispatching requests through httpx.AsyncClient + ASGITransport.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


class TestClientCompat:
    __test__ = False

    def __init__(
        self,
        app: Any,
        base_url: str = "http://testserver",
        *,
        raise_server_exceptions: bool = True,
        root_path: str = "",
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        follow_redirects: bool = True,
        client: tuple[str, int] = ("testclient", 50000),
        **_: Any,
    ) -> None:
        self.app = app
        self.base_url = base_url
        self.raise_server_exceptions = bool(raise_server_exceptions)
        self.root_path = root_path or ""
        self.follow_redirects = bool(follow_redirects)
        self.client = client
        self.headers = dict(headers or {})
        self.cookies = httpx.Cookies(cookies or {})
        self._closed = False

    def _run(self, coro):
        return asyncio.run(coro)

    async def _request_async(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        transport = httpx.ASGITransport(
            app=self.app,
            raise_app_exceptions=self.raise_server_exceptions,
            root_path=self.root_path,
            client=self.client,
        )
        req_headers = kwargs.pop("headers", None)
        req_cookies = kwargs.pop("cookies", None)
        async with httpx.AsyncClient(
            transport=transport,
            base_url=self.base_url,
            follow_redirects=self.follow_redirects,
            headers=self.headers,
            cookies=self.cookies,
        ) as client:
            response = await client.request(method, url, headers=req_headers, cookies=req_cookies, **kwargs)
            # Persist set-cookie values across subsequent requests.
            self.cookies.update(client.cookies)
            return response

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if self._closed:
            raise RuntimeError("TestClientCompat is closed")
        return self._run(self._request_async(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("OPTIONS", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("HEAD", url, **kwargs)

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> "TestClientCompat":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
