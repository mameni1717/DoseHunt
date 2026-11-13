"""Client HTTP poli : robot identifié, respect de robots.txt (jokers compris), rythme modéré, reprises."""
from __future__ import annotations

import logging
import random
import time
from typing import Optional
from urllib.parse import urlsplit

import httpx

from .config import USER_AGENT
from .robots import RobotsRules

log = logging.getLogger(__name__)


class BlockedByRobots(Exception):
    pass


class FetchError(Exception):
    def __init__(self, url: str, status: Optional[int], message: str = ""):
        super().__init__(f"{status} {url} {message}".strip())
        self.url, self.status = url, status


# En-tête Accept-Language selon la langue du site (français : inchangé).
ACCEPT_LANGUAGE = {"fr": "fr-FR,fr;q=0.9", "es": "es-ES,es;q=0.9", "de": "de-DE,de;q=0.9", "en": "en-GB,en;q=0.9",
                   "it": "it-IT,it;q=0.9", "nl": "nl-NL,nl;q=0.9", "pl": "pl-PL,pl;q=0.9", "sv": "sv-SE,sv;q=0.9",
                   "pt": "pt-PT,pt;q=0.9"}


class PoliteClient:
    """Un client par site : une requête à la fois, pause entre deux requêtes."""

    def __init__(self, delay_seconds: float = 2.0, timeout: float = 30.0, max_retries: int = 3,
                 respect_robots: bool = True, transport: Optional[httpx.BaseTransport] = None,
                 language: str = "fr"):
        self.delay = delay_seconds
        self.max_retries = max_retries
        self.respect_robots = respect_robots
        self._last = 0.0
        self._robots: dict[str, Optional[RobotsRules]] = {}
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANGUAGE.get(language or "fr", ACCEPT_LANGUAGE["fr"])},
            timeout=timeout, follow_redirects=True, transport=transport,
        )
        self.requests_made = 0

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- robots.txt --------------------------------------------------------
    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rules: Optional[RobotsRules] = None
            try:
                resp = self.client.get(origin + "/robots.txt")
                if resp.status_code == 200:
                    rules = RobotsRules.parse(resp.text, USER_AGENT)
            except httpx.HTTPError:
                pass
            self._robots[origin] = rules
        rules = self._robots[origin]
        return True if rules is None else rules.can_fetch(url)

    # -- requêtes ----------------------------------------------------------
    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last
        pause = self.delay + random.uniform(0, self.delay * 0.3)
        if elapsed < pause:
            time.sleep(pause - elapsed)

    def request(self, method: str, url: str, *, headers: Optional[dict] = None,
                accept_404: bool = False) -> Optional[httpx.Response]:
        if not self.allowed(url):
            raise BlockedByRobots(url)
        for attempt in range(1, self.max_retries + 1):
            self._wait()
            self._last = time.monotonic()
            self.requests_made += 1
            try:
                resp = self.client.request(method, url, headers=headers)
            except httpx.HTTPError as exc:
                log.warning("Erreur réseau %s (essai %d) : %s", url, attempt, exc)
                if attempt == self.max_retries:
                    raise FetchError(url, None, str(exc)) from exc
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 404 and accept_404:
                return None
            if resp.status_code in (429, 503):
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else 10 * attempt
                log.warning("%s sur %s, pause %.0f s", resp.status_code, url, wait)
                time.sleep(min(wait, 120))
                continue
            if resp.status_code >= 400:
                raise FetchError(url, resp.status_code)
            return resp
        raise FetchError(url, None, "trop de reprises")

    def get(self, url: str, *, headers: Optional[dict] = None, accept_404: bool = False) -> Optional[httpx.Response]:
        return self.request("GET", url, headers=headers, accept_404=accept_404)

    def post(self, url: str, *, headers: Optional[dict] = None, accept_404: bool = False) -> Optional[httpx.Response]:
        return self.request("POST", url, headers=headers, accept_404=accept_404)

    def get_json(self, url: str, *, accept_404: bool = False):
        resp = self.get(url, accept_404=accept_404)
        if resp is None:
            return None
        ctype = resp.headers.get("content-type", "")
        if "json" not in ctype:
            if accept_404:
                return None
            raise FetchError(url, resp.status_code, f"réponse non JSON ({ctype})")
        return resp.json()
