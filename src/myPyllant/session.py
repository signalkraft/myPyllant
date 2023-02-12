import aiohttp
from urllib.parse import urlencode, urlparse, parse_qs

from myPyllant.utils import generate_code, random_string


_aiohttp_session = None
_access_token = None
login_headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "user-agent": "myVAILLANT/11835 CFNetwork/1240.0.4 Darwin/20.6.0",
    "x-okta-user-agent-extended": "okta-auth-js/5.4.1 okta-react-native/2.7.0 react-native/>=0.70.1 ios/14.8 nodejs/undefined",
    "accept-language": "de-de",
}
login_url = "https://vaillant-prod.okta.com/api/v1/authn"


def get_session():
    global _aiohttp_session
    if not _aiohttp_session:
        jar = aiohttp.CookieJar()
        _aiohttp_session = aiohttp.ClientSession(cookie_jar=jar)
    return _aiohttp_session


def set_access_token(access_token):
    global _access_token
    _access_token = access_token


def get_access_token():
    if not _access_token:
        raise Exception("No access token set, did you call login()?")
    return _access_token


async def login(username, password):
    session = get_session()
    code_verifier, code_challenge = generate_code()

    login_payload = {
        "username": username,
        "password": password,
    }
    async with session.post(
        login_url, json=login_payload, headers=login_headers
    ) as resp:
        response = await resp.json()
        if "errorSummary" in response:
            raise Exception(response["errorSummary"])
        session_token = response["sessionToken"]

    nonce = random_string(43)
    state = random_string(43)
    authorize_querystring = {
        "nonce": nonce,
        "sessionToken": session_token,
        "response_type": "code",
        "code_challenge_method": "S256",
        "scope": "openid profile offline_access",
        "code_challenge": code_challenge,
        "redirect_uri": "com.okta.vaillant-prod:/callback",
        "client_id": "0oarllti4egHi7Nwx4x6",
        "state": state,
    }
    authorize_headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "myVAILLANT/11835 CFNetwork/1240.0.4 Darwin/20.6.0",
        "accept-language": "de-de",
    }
    authorize_url = (
        "https://vaillant-prod.okta.com/oauth2/default/v1/authorize?"
        + urlencode(authorize_querystring)
    )
    async with session.get(
        authorize_url, headers=authorize_headers, allow_redirects=False
    ) as resp:
        await resp.text()
        parsed_url = urlparse(resp.headers["Location"])
        code = parse_qs(parsed_url.query)["code"]

    token_payload = {
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": "com.okta.vaillant-prod:/callback",
        "client_id": "0oarllti4egHi7Nwx4x6",
        "grant_type": "authorization_code",
    }
    token_headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "user-agent": "okta-react-native/2.7.0 okta-oidc-ios/3.11.2 react-native/>=0.70.1 ios/14.8",
        "accept-language": "de-de",
    }
    token_url = "https://vaillant-prod.okta.com/oauth2/default/v1/token"
    async with session.post(
        token_url, data=token_payload, headers=token_headers
    ) as resp:
        session_data = await resp.json()
        set_access_token(session_data["access_token"])


def get_authorized_headers():
    return {
        "Authorization": "Bearer " + get_access_token(),
        "x-app-identifier": "VAILLANT",
        "Accept-Language": "de-de",
        "Accept": "application/json, text/plain, */*",
        "x-client-locale": "de-DE",
        "x-idm-identifier": "OKTA",
        "ocp-apim-subscription-key": "1e0a2f3511fb4c5bbb1c7f9fedd20b1c",
        "User-Agent": "myVAILLANT/11835 CFNetwork/1240.0.4 Darwin/20.6.0",
        "Connection": "keep-alive",
    }
