"""Lecture de robots.txt conforme à la RFC 9309 : jokers `*`, ancre `$`, règle la plus longue gagnante.

urllib.robotparser ne gère pas les jokers : « Disallow: *?controller* » (Fitadium) y est ignoré.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass
class RobotsRules:
    rules: list[tuple[bool, str, re.Pattern]] = field(default_factory=list)   # (allow, motif, regex)

    @staticmethod
    def _compile(pattern: str) -> re.Pattern:
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        if not body.startswith("/") and not body.startswith("*"):
            body = "/" + body
        rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
        return re.compile("^" + rx + ("$" if anchored else ""))

    @classmethod
    def parse(cls, text: str, user_agent: str) -> "RobotsRules":
        agent = user_agent.split("/")[0].lower()
        groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
        current_agents: list[str] = []
        current_rules: list[tuple[bool, str]] = []
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (x.strip() for x in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if not last_was_agent and (current_agents or current_rules):
                    groups.append((current_agents, current_rules))
                    current_agents, current_rules = [], []
                current_agents.append(value.lower())
                last_was_agent = True
            elif key in ("allow", "disallow"):
                last_was_agent = False
                if value:
                    current_rules.append((key == "allow", value))
            else:
                last_was_agent = False
        if current_agents or current_rules:
            groups.append((current_agents, current_rules))
        specific = [r for a, r in groups if any(x != "*" and x in agent for x in a)]
        chosen = [rule for rs in specific for rule in rs] if specific else \
                 [rule for a, rs in groups if "*" in a for rule in rs]
        return cls([(allow, pat, cls._compile(pat)) for allow, pat in chosen])

    def can_fetch(self, url: str) -> bool:
        parts = urlsplit(url)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        best: tuple[int, bool] | None = None
        for allow, pat, rx in self.rules:
            if rx.match(path):
                length = len(pat.replace("*", ""))
                if best is None or length > best[0] or (length == best[0] and allow):
                    best = (length, allow)
        return True if best is None else best[1]
