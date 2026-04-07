"""
UFC Fight Graph - Domain Layer.

Pure domain entities with zero external dependencies.
No I/O, no database, no framework imports.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# ==================== VALUE OBJECTS ====================

@dataclass(frozen=True)
class FighterRecord:
    wins: int = 0
    losses: int = 0
    draws: int = 0
    no_contests: int = 0

    @property
    def total_fights(self) -> int:
        return self.wins + self.losses + self.draws + self.no_contests

    @property
    def win_percentage(self) -> float:
        if self.total_fights == 0:
            return 0.0
        return (self.wins / self.total_fights) * 100

    @classmethod
    def from_string(cls, record_str: str) -> "FighterRecord":
        """Parse '22-6-0 (1 NC)' format."""
        import re
        match = re.search(r"(\d+)-(\d+)-(\d+)(?:\s*\((\d+)\s*NC\))?", record_str)
        if match:
            return cls(
                wins=int(match.group(1)),
                losses=int(match.group(2)),
                draws=int(match.group(3)),
                no_contests=int(match.group(4) or 0),
            )
        return cls()


@dataclass(frozen=True)
class PhysicalStats:
    height_inches: Optional[float] = None
    weight_lbs: Optional[float] = None
    reach_inches: Optional[float] = None
    stance: Optional[str] = None
    dob: Optional[str] = None


@dataclass(frozen=True)
class CareerStats:
    slpm: Optional[float] = None
    str_acc: Optional[float] = None
    sapm: Optional[float] = None
    str_def: Optional[float] = None
    td_avg: Optional[float] = None
    td_acc: Optional[float] = None
    td_def: Optional[float] = None
    sub_avg: Optional[float] = None


@dataclass(frozen=True)
class Scorecard:
    judge_name: str
    score: str  # e.g., "27 - 30"

    @property
    def score_a(self) -> Optional[int]:
        try:
            parts = self.score.split("-")
            return int(parts[0].strip())
        except (ValueError, IndexError):
            return None

    @property
    def score_b(self) -> Optional[int]:
        try:
            parts = self.score.split("-")
            return int(parts[1].strip())
        except (ValueError, IndexError):
            return None

    @property
    def margin(self) -> Optional[int]:
        a, b = self.score_a, self.score_b
        if a is not None and b is not None:
            return abs(a - b)
        return None


# ==================== ENTITIES ====================

@dataclass
class Fighter:
    name: str
    nickname: Optional[str] = None
    record: Optional[FighterRecord] = None
    physical: Optional[PhysicalStats] = None
    career: Optional[CareerStats] = None
    url: Optional[str] = None
    updated_at: Optional[datetime] = None


@dataclass
class Fight:
    url: str
    event_name: Optional[str] = None
    event_url: Optional[str] = None
    date: Optional[str] = None
    fighter_a: Optional[str] = None
    fighter_b: Optional[str] = None
    winner: Optional[str] = None
    method: Optional[str] = None
    round_num: Optional[str] = None
    time: Optional[str] = None
    time_format: Optional[str] = None
    weight_class: Optional[str] = None
    referee: Optional[str] = None
    judges: list[Scorecard] = field(default_factory=list)
    finish_details: Optional[str] = None
    rounds: list[dict] = field(default_factory=list)
    overall_totals: Optional[list] = None
    overall_sig_str: Optional[list] = None


@dataclass
class Event:
    name: str
    url: str
    date: Optional[str] = None
    location: Optional[str] = None
    fights: list[Fight] = field(default_factory=list)
