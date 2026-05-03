import json
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

API_BASE = "https://api.steampowered.com"
START_QR_URL = f"{API_BASE}/IAuthenticationService/BeginAuthSessionViaQR/v1"
POLL_STATUS_URL = f"{API_BASE}/IAuthenticationService/PollAuthSessionStatus/v1"
QR_IMAGE_BASE = "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data="


@dataclass
class SteamQRSession:
    client_id: int
    request_id: str
    interval: float
    challenge_url: str
    version: int
    allowed_confirmations: List[Dict[str, Any]] = field(default_factory=list)

class SteamQRAuthenticator:
    def __init__(self, timeout: float = 15.0) -> None:
        self.session = requests.Session()
        self.timeout = timeout

    def build_qr_image_url(self, challenge_url: str) -> str:
      encoded = urllib.parse.quote(challenge_url, safe="")
      return f"{QR_IMAGE_BASE}{encoded}"

    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        }
        resp = self.session.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        text = resp.text
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise RuntimeError(
                f"Steam Web API JSON POST error {resp.status_code} at {url}:\n{text}"
            ) from e

        data = resp.json()

        if isinstance(data, dict) and "response" in data:
            return data["response"]
        return data

  
    def _post_form(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = {k: str(v) for k, v in payload.items()}

        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "application/json",
            "Origin": "https://steamcommunity.com",
            "Referer": "https://steamcommunity.com/login/home/?goto=",
        }

        resp = self.session.post(
            url,
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        text = resp.text
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            raise RuntimeError(
                f"Steam Web API form POST error {resp.status_code} at {url}:\n{text}"
            ) from e

        try:
            body = resp.json()
        except ValueError as e:
            raise RuntimeError(
                f"Non-JSON body from Steam for PollAuthSessionStatus:\n{text}"
            ) from e

        if isinstance(body, dict) and "response" in body:
            return body["response"]
        return body



    def start_session_with_qr(self, device_friendly_name: str = "Python QR login") -> SteamQRSession:
        device_details: Dict[str, Any] = {
            "device_friendly_name": device_friendly_name,
            "platform_type": 2, 
            "os_type": 20,       
        }

        payload = {"device_details": device_details}

        result = self._post_json(START_QR_URL, payload)

        return SteamQRSession(
            client_id=int(result["client_id"]),
            request_id=str(result["request_id"]),
            interval=float(result.get("interval", 5.0)),
            challenge_url=str(result["challenge_url"]),
            version=int(result.get("version", 1)),
            allowed_confirmations=result.get("allowed_confirmations", []),
        )

  
    def poll_auth_session_status(self, qr_session: SteamQRSession) -> Dict[str, Any]:
        payload = {
            "client_id": qr_session.client_id,
            "request_id": qr_session.request_id,
        }
        return self._post_form(POLL_STATUS_URL, payload)

  
    def wait_for_completion(
        self,
        qr_session: SteamQRSession,
        timeout: float = 300.0,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        start = time.monotonic()
        interval = qr_session.interval

        if verbose:
            print(f"[INFO] Polling every {interval:.1f}s for mobile confirmation...")

        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise TimeoutError("Timed out waiting for Steam Guard confirmation")

            poll = self.poll_auth_session_status(qr_session)
            access_token = poll.get("access_token")
            refresh_token = poll.get("refresh_token")

            if verbose:
                state = poll.get("state", "UNKNOWN")
                had_remote = poll.get("had_remote_interaction", False)
                print(
                    "[DEBUG] Poll result:"
                    f" state={state}, had_remote_interaction={had_remote},"
                    f" has_access_token={bool(access_token)}, has_refresh_token={bool(refresh_token)}"
                )

            if access_token and refresh_token:
                return poll

            time.sleep(interval)
