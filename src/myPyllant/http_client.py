from __future__ import annotations

import logging

import aiohttp
from aiohttp import ClientResponse, ClientResponseError

logger = logging.getLogger(__name__)


class AuthenticationFailed(ConnectionError):
    pass


class LoginEndpointInvalid(ConnectionError):
    pass


class RealmInvalid(ConnectionError):
    pass


async def on_request_start(session, context, params: aiohttp.TraceRequestStartParams):
    """
    See https://docs.aiohttp.org/en/stable/tracing_reference.html#aiohttp.TraceConfig.on_request_start
    """
    logger.debug("Starting request %s", params)


async def on_request_end(session, context, params: aiohttp.TraceRequestEndParams):
    """
    See https://docs.aiohttp.org/en/stable/tracing_reference.html#aiohttp.TraceConfig.on_request_end
    and https://docs.python.org/3/howto/logging.html#optimization
    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Got response %s", await params.response.text())


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


def get_http_client(**kwargs) -> aiohttp.ClientSession:
    trace_config = aiohttp.TraceConfig()
    trace_config.on_request_start.append(on_request_start)
    trace_config.on_request_end.append(on_request_end)

    defaults = dict(
        cookie_jar=aiohttp.CookieJar(),
        raise_for_status=on_raise_for_status,  # type: ignore
        trace_configs=[trace_config],
    )

    return aiohttp.ClientSession(**{**defaults, **kwargs})
