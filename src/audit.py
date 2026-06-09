"""
audit.py — Hash-ketjutettu, append-only audit-loki (chain of custody).

Jokainen putken askel kirjataan tapahtumana, joka sisaltaa edellisen tapahtuman
hashin. Nain mika tahansa jalkikateinen muokkaus rikkoo ketjun ja on havaittavissa.
Tama on se osa, joka tekee tuloksesta oikeudessa todennettavan.
"""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


GENESIS = "0" * 64


@dataclass
class Event:
    seq: int
    actor: str          # mika agentti / kerros teki
    action: str         # mita tehtiin
    payload: dict[str, Any]
    prev_hash: str
    ts: str
    this_hash: str = ""

    def compute_hash(self) -> str:
        body = json.dumps(
            {"seq": self.seq, "actor": self.actor, "action": self.action,
             "payload": self.payload, "prev_hash": self.prev_hash, "ts": self.ts},
            sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def record(self, actor: str, action: str, payload: dict[str, Any]) -> Event:
        prev = self._events[-1].this_hash if self._events else GENESIS
        ev = Event(
            seq=len(self._events),
            actor=actor,
            action=action,
            payload=payload,
            prev_hash=prev,
            ts=datetime.now(timezone.utc).isoformat(),
        )
        ev.this_hash = ev.compute_hash()
        self._events.append(ev)
        return ev

    def verify(self) -> bool:
        """Tarkistaa, ettei ketjua ole muokattu."""
        prev = GENESIS
        for ev in self._events:
            if ev.prev_hash != prev:
                return False
            if ev.compute_hash() != ev.this_hash:
                return False
            prev = ev.this_hash
        return True

    def __iter__(self):
        return iter(self._events)

    def __len__(self):
        return len(self._events)
