from __future__ import annotations

import logging

import aiohttp
from aiohttp import ClientResponse, ClientResponseError, hdrs

logger = logging.getLogger(__name__)


class AuthenticationFailed(ConnectionError):
    pass


class LoginEndpointInvalid(ConnectionError):
    pass


class RealmInvalid(ConnectionError):
    pass


class CountingClientSession(aiohttp.ClientSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_count = 0

    async def _request(self, method, str_or_url, **kwargs):
        self.request_count += 1
        return await super()._request(method, str_or_url, **kwargs)


async def on_request_start(session, context, params: aiohttp.TraceRequestStartParams):
    """
    See https://docs.aiohttp.org/en/stable/tracing_reference.html#aiohttp.TraceConfig.on_request_start
    """
    logger.debug("Starting %s to %s", params.method, params.url)


async def on_request_chunk_sent(
    session, context, params: aiohttp.TraceRequestChunkSentParams
):
    """
    See https://docs.aiohttp.org/en/stable/tracing_reference.html#aiohttp.TraceConfig.on_request_chunk_sent
    """
    if params.chunk:
        logger.debug(
            "Sending %s to %s with %s",
            params.method,
            params.url,
            params.chunk,
        )


async def on_request_end(session, context, params: aiohttp.TraceRequestEndParams):
    """
    See https://docs.aiohttp.org/en/stable/tracing_reference.html#aiohttp.TraceConfig.on_request_end
    and https://docs.python.org/3/howto/logging.html#optimization
    """
    if params.headers.get(hdrs.CONTENT_TYPE, "").lower() == "application/json":
        content = await params.response.json()
    else:
        content = await params.response.text()
    logger.debug(
        "Got response for %s to %s: %s",
        params.method,
        params.url,
        content,
    )


async def on_raise_for_status(response: ClientResponse):
    """
    Add the response text to the exception message of a 400 response
    """
    if response.status == 400:
        text = await response.text()
        try:
            response.raise_for_status()
        except ClientResponseError as e:
            e.message = f"{e.message}, response was: {text}"
            raise e
    response.raise_for_status()


def get_http_client(**kwargs) -> CountingClientSession:
    trace_configs: list[aiohttp.TraceConfig] | None = None
    if logger.isEnabledFor(logging.DEBUG):
        trace_config = aiohttp.TraceConfig()
        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)
        trace_config.on_request_chunk_sent.append(on_request_chunk_sent)
        trace_configs = [trace_config]

    defaults = dict(
        cookie_jar=aiohttp.CookieJar(),
        raise_for_status=on_raise_for_status,  # type: ignore
        trace_configs=trace_configs,
    )

    return CountingClientSession(**{**defaults, **kwargs})
