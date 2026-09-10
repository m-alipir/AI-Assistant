
import pytest

from app.collectors.article import ArticleContent, ArticleFetcher, _extract_html
from app.providers.contracts import ProviderError


def test_trafilatura_removes_navigation_and_retains_article_text() -> None:
    html = """
    <html><body><nav>Subscribe Advertisement Home</nav><article><h1>Important update</h1>
    <p>NVIDIA announced a new public platform update with detailed technical information.</p>
    <p>The announcement explains the release schedule and supported hardware.</p></article>
    <footer>Copyright newsletter privacy</footer></body></html>
    """
    text = _extract_html(html.encode())
    assert "NVIDIA announced" in text
    assert "Subscribe" not in text


def test_article_parser_rejects_empty_or_boilerplate_html() -> None:
    with pytest.raises(ProviderError, match="sufficient"):
        _extract_html(b"<html><body><nav>Home</nav></body></html>")


@pytest.mark.asyncio
async def test_article_fetcher_rejects_private_redirect_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    class Response:
        status_code = 302
        headers = {"location": "http://127.0.0.1/private"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        def stream(self, *_: object, **__: object) -> Response:
            return Response()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: Client())
    fetcher = ArticleFetcher(retries=0, allow_private_hosts=False, allow_insecure_http=False)
    with pytest.raises(ProviderError, match="article fetch failed"):
        await fetcher.fetch("https://example.test/article")


def test_article_content_is_compact_data_holder() -> None:
    article = ArticleContent("text", "https://example.test/article")
    assert article.text == "text"


@pytest.mark.asyncio
async def test_article_fetcher_rejects_unsupported_mime_and_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    class Response:
        status_code = 200

        def __init__(self, content_type: str, chunks: list[bytes]) -> None:
            self.headers = {"content-type": content_type}
            self._chunks = chunks

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            for chunk in self._chunks:
                yield chunk

    class Client:
        def __init__(self, response: Response) -> None:
            self._response = response

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        def stream(self, *_: object, **__: object) -> Response:
            return self._response

    for content_type, chunks, max_bytes in (
        ("application/pdf", [b"%PDF"], 100),
        ("text/html", [b"x" * 101], 100),
    ):
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda content_type=content_type, chunks=chunks, **_: Client(
                Response(content_type, chunks)
            ),
        )
        with pytest.raises(ProviderError, match="article fetch failed"):
            await ArticleFetcher(retries=0, max_response_bytes=max_bytes).fetch(
                "https://example.test/article"
            )


@pytest.mark.asyncio
async def test_article_fetcher_retries_a_bounded_number_of_times() -> None:
    fetcher = ArticleFetcher(retries=1)
    calls = 0

    async def fail_once(url: str) -> ArticleContent:
        nonlocal calls
        calls += 1
        raise ProviderError("fixture")

    fetcher._fetch_once = fail_once  # type: ignore[method-assign]
    with pytest.raises(ProviderError, match="article fetch failed"):
        await fetcher.fetch("https://example.test/article")
    assert calls == 2
