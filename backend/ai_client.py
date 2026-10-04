

import httpx

from config.settings import settings


def ai_request(
    method: str,
    path: str,
    json_payload: dict | None = None,
    timeout: float = 300.0,
):
    """
    Returns (ok, data). Never raises for network errors —
    callers decide how to degrade.
    """

    url = (
        f"{settings.ai_service_url.rstrip('/')}"
        f"{path}"
    )

    try:

        response = httpx.request(
            method,
            url,
            json=json_payload,
            timeout=timeout
        )

    except httpx.HTTPError:

        return False, None

    if response.status_code >= 400:

        return False, None

    try:

        return True, response.json()

    except ValueError:

        return True, None


def ai_get(path: str):

    return ai_request("GET", path)


def ai_post(
    path: str,
    payload: dict | None = None
):

    return ai_request(
        "POST",
        path,
        payload or {}
    )
