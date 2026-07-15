from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MessageEvidence:
    message_id: int
    timestamp: datetime | None
    text: str
    media_type: str | None
    inline_buttons: tuple[str, ...]
    reply_buttons: tuple[str, ...]
    response_seconds: float
    edited: bool = False
    first_observed_at: float | None = None
    poll_iteration: int | None = None
    observation_source: str = "history"
    markup_kind: str = "none"


@dataclass(frozen=True)
class ActionResult:
    action: str
    baseline_id: int
    messages: tuple[MessageEvidence, ...]
    first_response_seconds: float | None
    total_seconds: float
    timing: ActionTiming | None = None
    outgoing_message_ids: tuple[int, ...] = ()
    polls: tuple[CollectionPoll, ...] = ()
    observations: tuple[MessageObservation, ...] = ()
    collection_reason: str = "unknown"
    collection_poll_count: int = 0
    earliest_server_date: datetime | None = None
    earliest_observation_at: float | None = None


@dataclass(frozen=True)
class ActionTiming:
    scenario_started_at: float
    readiness_completed_at: float
    boundary_captured_at: float
    send_started_at: float
    product_action_sent_at: float
    first_response_at: float | None
    collection_finished_at: float
    collection_deadline_at: float | None = None
    product_action_server_date: datetime | None = None

    def offset(self, value: float | None) -> float | None:
        return None if value is None else value - self.scenario_started_at


@dataclass(frozen=True)
class CollectionPoll:
    iteration: int
    rpc_started_at: float
    rpc_finished_at: float
    rpc_duration_seconds: float
    outcome: str
    discovered_message_ids: tuple[int, ...] = ()
    observation_source: str = "history_batch"
    batch_observation_limited: bool = False
    exception_type: str | None = None


@dataclass(frozen=True)
class MessageObservation:
    message_id: int
    expected_sender_match: bool
    outgoing: bool
    telegram_date: datetime | None
    first_observed_at: float
    observed_seconds: float
    poll_iteration: int
    observation_source: str
    markup_kind: str
    accepted: bool
    exclusion_reason: str | None = None


@dataclass(frozen=True)
class ActiveReplyKeyboard:
    rows: tuple[tuple[str, ...], ...]
    source_message_id: int
    source_timestamp: datetime | None

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(label for row in self.rows for label in row)
