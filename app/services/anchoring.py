from __future__ import annotations

import hashlib
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.persistence.models import (
    AnchorReceipt,
    AnchorSubmissionRecord,
    Event,
    IngestRequest,
)
from app.observability.logging import configure_logging, correlation_extra, new_trace_id
from app.observability.metrics import (
    observe_anchoring_outcome,
    observe_anchoring_rollout_canary_outcome,
    observe_anchoring_rollout_decision,
    observe_anchoring_rollout_transition,
    observe_anchoring_run,
)
from app.services.db_runtime import (
    database_url as _database_url,
    ensure_schema as _ensure_schema,
    get_engine as _get_engine,
)
from app.services.alerts import (
    ALERT_TYPE_ANCHOR_DEAD_LETTER,
    ALERT_TYPE_ANCHOR_RETRY_FAILURE,
    create_alert,
)
from app.services.anchor_adapter.active_mock import ActiveMockAnchorAdapter
from app.services.anchor_adapter.base import (
    AnchorAdapter,
    AnchorAdapterError,
    AnchorVerificationError,
    AnchorTimeoutError,
)
from app.services.anchor_adapter.evm_contract import EvmContractAnchorAdapter
from app.services.anchor_adapter.reserved_stub import ReservedDualChainStubAdapter

ANCHOR_STATE_RECEIVED = "RECEIVED"
ANCHOR_STATE_ANCHORING = "ANCHORING"
ANCHOR_STATE_ANCHORED = "ANCHORED"
ANCHOR_STATE_FAILED_RETRYING = "FAILED_RETRYING"
ANCHOR_STATE_DEAD_LETTER = "DEAD_LETTER"
ANCHOR_SUBMISSION_PENDING = "PENDING"
ANCHOR_SUBMISSION_FINALIZED = "FINALIZED"
ANCHOR_SUBMISSION_REORGED = "REORGED"

ROLL_OUT_MODE_SHADOW = "shadow"
ROLL_OUT_MODE_CANARY = "canary"
ROLL_OUT_MODE_FULL = "full"
ROLL_OUT_MODE_ROLLBACK_SAFE = "rollback_safe"

_ROLL_OUT_MODES = {
    ROLL_OUT_MODE_SHADOW,
    ROLL_OUT_MODE_CANARY,
    ROLL_OUT_MODE_FULL,
    ROLL_OUT_MODE_ROLLBACK_SAFE,
}


@dataclass(frozen=True)
class _RolloutConfig:
    mode: str
    canary_percent: int
    force_rollback_safe: bool
    min_success_rate: float
    max_dead_letter_rate: float
    max_p95_confirmation_seconds: float
    abort_after_seconds: int
    evaluation_window_seconds: int


@dataclass(frozen=True)
class _RolloutDecision:
    mode: str
    path: str
    adapter: AnchorAdapter
    canary_sampled: bool
    shadow_probe: bool


@dataclass(frozen=True)
class _CanarySample:
    recorded_at_seconds: float
    outcome: str
    confirmation_seconds: float | None


@dataclass
class _RolloutRuntime:
    signature: tuple[object, ...] | None = None
    auto_aborted: bool = False
    violation_started_at_seconds: float | None = None
    samples: deque[_CanarySample] = field(default_factory=deque)


@dataclass(frozen=True)
class _AnchoringEvent:
    id: int
    canonical_hash: str
    sensor_payload: dict


_ROLLOUT_RUNTIME = _RolloutRuntime()
_ROLLOUT_LOCK = Lock()

worker_logger = logging.getLogger("app.worker.anchoring")


def _load_anchoring_event(session: Session, event_id: int) -> _AnchoringEvent | None:
    row = session.execute(
        select(
            Event.id.label("id"),
            Event.canonical_hash.label("canonical_hash"),
            Event.sensor_payload.label("sensor_payload"),
        ).where(Event.id == event_id)
    ).one_or_none()
    if row is None:
        return None
    sensor_payload = row.sensor_payload if isinstance(row.sensor_payload, dict) else {}
    return _AnchoringEvent(
        id=int(row.id),
        canonical_hash=str(row.canonical_hash),
        sensor_payload=sensor_payload,
    )


def _max_retries() -> int:
    raw_value = os.getenv("ANCHOR_MAX_RETRIES", "3")
    try:
        parsed = int(raw_value)
    except ValueError:
        return 3
    return parsed if parsed > 0 else 1


def _rollout_now_seconds() -> float:
    return time.time()


def _normalized_rollout_mode(raw_mode: str) -> str:
    normalized = raw_mode.strip().lower().replace("-", "_")
    if normalized in _ROLL_OUT_MODES:
        return normalized
    return ROLL_OUT_MODE_ROLLBACK_SAFE


def _rollout_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "y", "on"}


def _rollout_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _rollout_float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _rollout_signature(config: _RolloutConfig) -> tuple[object, ...]:
    return (
        config.mode,
        config.canary_percent,
        config.force_rollback_safe,
        config.min_success_rate,
        config.max_dead_letter_rate,
        config.max_p95_confirmation_seconds,
        config.abort_after_seconds,
        config.evaluation_window_seconds,
    )


def _load_rollout_config() -> _RolloutConfig:
    mode = _normalized_rollout_mode(
        os.getenv("ANCHOR_EVM_ROLLOUT_MODE", ROLL_OUT_MODE_ROLLBACK_SAFE)
    )
    canary_percent = _rollout_int_env("ANCHOR_EVM_CANARY_PERCENT", 5)
    canary_percent = max(0, min(100, canary_percent))
    min_success_rate = _rollout_float_env("ANCHOR_EVM_CANARY_MIN_SUCCESS_RATE", 0.99)
    min_success_rate = max(0.0, min(1.0, min_success_rate))
    max_dead_letter_rate = _rollout_float_env(
        "ANCHOR_EVM_CANARY_MAX_DEAD_LETTER_RATE", 0.005
    )
    max_dead_letter_rate = max(0.0, min(1.0, max_dead_letter_rate))
    max_p95_confirmation_seconds = _rollout_float_env(
        "ANCHOR_EVM_CANARY_MAX_P95_CONFIRMATION_SECONDS", 120.0
    )
    max_p95_confirmation_seconds = max(1.0, max_p95_confirmation_seconds)
    abort_after_seconds = _rollout_int_env("ANCHOR_EVM_CANARY_ABORT_AFTER_SECONDS", 600)
    abort_after_seconds = max(1, abort_after_seconds)
    evaluation_window_seconds = _rollout_int_env(
        "ANCHOR_EVM_CANARY_WINDOW_SECONDS", 600
    )
    evaluation_window_seconds = max(1, evaluation_window_seconds)
    force_rollback_safe = _rollout_bool_env("ANCHOR_EVM_FORCE_ROLLBACK_SAFE", False)
    return _RolloutConfig(
        mode=mode,
        canary_percent=canary_percent,
        force_rollback_safe=force_rollback_safe,
        min_success_rate=min_success_rate,
        max_dead_letter_rate=max_dead_letter_rate,
        max_p95_confirmation_seconds=max_p95_confirmation_seconds,
        abort_after_seconds=abort_after_seconds,
        evaluation_window_seconds=evaluation_window_seconds,
    )


def _rollout_quantile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int((len(ordered) - 1) * quantile)
    index = max(0, min(len(ordered) - 1, index))
    return ordered[index]


def _sync_rollout_runtime_locked(config: _RolloutConfig) -> None:
    signature = _rollout_signature(config)
    if signature == _ROLLOUT_RUNTIME.signature:
        return
    _ROLLOUT_RUNTIME.signature = signature
    _ROLLOUT_RUNTIME.auto_aborted = False
    _ROLLOUT_RUNTIME.violation_started_at_seconds = None
    _ROLLOUT_RUNTIME.samples.clear()


def _rollout_is_auto_aborted(config: _RolloutConfig) -> bool:
    with _ROLLOUT_LOCK:
        _sync_rollout_runtime_locked(config)
        return _ROLLOUT_RUNTIME.auto_aborted


def _record_canary_sample(
    *,
    config: _RolloutConfig,
    outcome: str,
    confirmation_seconds: float | None,
    trace_id: str,
    event_id: int,
) -> None:
    now_seconds = _rollout_now_seconds()
    sample = _CanarySample(
        recorded_at_seconds=now_seconds,
        outcome=outcome,
        confirmation_seconds=confirmation_seconds,
    )
    auto_abort_triggered = False
    success_rate = 1.0
    dead_letter_rate = 0.0
    p95_confirmation_seconds: float | None = None

    with _ROLLOUT_LOCK:
        _sync_rollout_runtime_locked(config)
        _ROLLOUT_RUNTIME.samples.append(sample)
        cutoff_seconds = now_seconds - config.evaluation_window_seconds
        while _ROLLOUT_RUNTIME.samples:
            if _ROLLOUT_RUNTIME.samples[0].recorded_at_seconds >= cutoff_seconds:
                break
            _ROLLOUT_RUNTIME.samples.popleft()

        total = len(_ROLLOUT_RUNTIME.samples)
        successes = sum(
            1 for item in _ROLLOUT_RUNTIME.samples if item.outcome == "success"
        )
        dead_letters = sum(
            1 for item in _ROLLOUT_RUNTIME.samples if item.outcome == "dead_letter"
        )
        confirmations = [
            item.confirmation_seconds
            for item in _ROLLOUT_RUNTIME.samples
            if item.confirmation_seconds is not None
        ]

        if total > 0:
            success_rate = successes / total
            dead_letter_rate = dead_letters / total
        p95_confirmation_seconds = _rollout_quantile(confirmations, 0.95)

        violates_success = success_rate < config.min_success_rate
        violates_dead_letter = dead_letter_rate > config.max_dead_letter_rate
        violates_latency = (
            p95_confirmation_seconds is not None
            and p95_confirmation_seconds > config.max_p95_confirmation_seconds
        )
        gate_violated = violates_success or violates_dead_letter or violates_latency

        if gate_violated:
            if _ROLLOUT_RUNTIME.violation_started_at_seconds is None:
                _ROLLOUT_RUNTIME.violation_started_at_seconds = now_seconds
            elif (
                not _ROLLOUT_RUNTIME.auto_aborted
                and now_seconds - _ROLLOUT_RUNTIME.violation_started_at_seconds
                >= config.abort_after_seconds
            ):
                _ROLLOUT_RUNTIME.auto_aborted = True
                auto_abort_triggered = True
        else:
            _ROLLOUT_RUNTIME.violation_started_at_seconds = None

    if auto_abort_triggered:
        observe_anchoring_rollout_transition(to_state=ROLL_OUT_MODE_ROLLBACK_SAFE)
        worker_logger.error(
            "anchoring_canary_auto_abort success_rate=%.4f dead_letter_rate=%.4f p95_confirmation_seconds=%.3f",
            success_rate,
            dead_letter_rate,
            p95_confirmation_seconds or 0.0,
            extra=correlation_extra(trace_id=trace_id, event_id=event_id),
        )


def _is_canary_cohort(event_id: int, canonical_hash: str, percent: int) -> bool:
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    seed = f"{event_id}:{canonical_hash.strip().lower()}".encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < percent


class _RolloutController:
    def __init__(
        self,
        *,
        config: _RolloutConfig,
        safe_adapter: AnchorAdapter,
        evm_adapter: AnchorAdapter | None,
    ) -> None:
        self._config = config
        self._safe_adapter = safe_adapter
        self._evm_adapter = evm_adapter

    def _effective_mode(self) -> str:
        if self._config.force_rollback_safe or _rollout_is_auto_aborted(self._config):
            return ROLL_OUT_MODE_ROLLBACK_SAFE
        return self._config.mode

    def default_adapter(self) -> AnchorAdapter:
        mode = self._effective_mode()
        if mode == ROLL_OUT_MODE_FULL and self._evm_adapter is not None:
            return self._evm_adapter
        return self._safe_adapter

    def decide(self, *, event_id: int, canonical_hash: str) -> _RolloutDecision:
        mode = self._effective_mode()
        canary_sampled = False
        shadow_probe = False

        if mode == ROLL_OUT_MODE_FULL and self._evm_adapter is not None:
            adapter = self._evm_adapter
            path = "evm"
        elif mode == ROLL_OUT_MODE_CANARY and self._evm_adapter is not None:
            canary_sampled = _is_canary_cohort(
                event_id=event_id,
                canonical_hash=canonical_hash,
                percent=self._config.canary_percent,
            )
            if canary_sampled:
                adapter = self._evm_adapter
                path = "evm"
            else:
                adapter = self._safe_adapter
                path = "safe"
        elif mode == ROLL_OUT_MODE_SHADOW and self._evm_adapter is not None:
            adapter = self._safe_adapter
            path = "safe"
            shadow_probe = True
        else:
            mode = ROLL_OUT_MODE_ROLLBACK_SAFE
            adapter = self._safe_adapter
            path = "safe"

        observe_anchoring_rollout_decision(mode=mode, path=path)
        return _RolloutDecision(
            mode=mode,
            path=path,
            adapter=adapter,
            canary_sampled=canary_sampled,
            shadow_probe=shadow_probe,
        )

    def recovery_adapter(self) -> AnchorAdapter:
        return (
            self._evm_adapter if self._evm_adapter is not None else self._safe_adapter
        )

    def run_shadow_probe(self, *, event: _AnchoringEvent, trace_id: str) -> None:
        if self._evm_adapter is None:
            return
        try:
            submission = self._evm_adapter.anchor_event(
                event_id=event.id,
                canonical_hash=event.canonical_hash,
                payload=event.sensor_payload,
            )
            receipt = self._evm_adapter.get_receipt(submission.transaction_hash)
            if not self._evm_adapter.verify_anchor(
                canonical_hash=event.canonical_hash,
                receipt=receipt,
            ):
                raise AnchorVerificationError("shadow anchor verification failed")
            worker_logger.info(
                "anchoring_shadow_probe_succeeded",
                extra=correlation_extra(
                    trace_id=trace_id,
                    event_id=event.id,
                    tx_hash=submission.transaction_hash,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - shadow failures must never break ingest.
            worker_logger.warning(
                "anchoring_shadow_probe_failed error=%s",
                str(exc),
                extra=correlation_extra(trace_id=trace_id, event_id=event.id),
            )

    def observe_primary_outcome(
        self,
        *,
        decision: _RolloutDecision,
        outcome: str,
        confirmation_seconds: float | None,
        trace_id: str,
        event_id: int,
    ) -> None:
        if (
            decision.mode != ROLL_OUT_MODE_CANARY
            or not decision.canary_sampled
            or decision.path != "evm"
        ):
            return

        canary_outcome = {
            "anchored": "success",
            "already_anchored": "success",
            "failed_retrying": "retry",
            "dead_letter": "dead_letter",
        }.get(outcome)
        if canary_outcome is None:
            return

        observe_anchoring_rollout_canary_outcome(
            outcome=canary_outcome,
            confirmation_seconds=(
                confirmation_seconds if canary_outcome == "success" else None
            ),
        )
        _record_canary_sample(
            config=self._config,
            outcome=canary_outcome,
            confirmation_seconds=(
                confirmation_seconds if canary_outcome == "success" else None
            ),
            trace_id=trace_id,
            event_id=event_id,
        )


def _build_safe_adapter() -> AnchorAdapter:
    return ActiveMockAnchorAdapter()


def _build_evm_adapter() -> AnchorAdapter:
    return EvmContractAnchorAdapter()


def _build_rollout_controller(*, adapter_name: str) -> _RolloutController | None:
    if adapter_name != "evm_contract":
        return None

    config = _load_rollout_config()
    safe_adapter = _build_safe_adapter()
    evm_adapter: AnchorAdapter | None = None
    if not config.force_rollback_safe and config.mode in {
        ROLL_OUT_MODE_SHADOW,
        ROLL_OUT_MODE_CANARY,
        ROLL_OUT_MODE_FULL,
    }:
        try:
            evm_adapter = _build_evm_adapter()
        except Exception as exc:  # noqa: BLE001 - rollout must degrade safely.
            worker_logger.warning(
                "anchoring_rollout_evm_unavailable fallback=safe error=%s",
                str(exc),
            )

    return _RolloutController(
        config=config,
        safe_adapter=safe_adapter,
        evm_adapter=evm_adapter,
    )


def _build_active_adapter(*, adapter_name: str | None = None) -> AnchorAdapter:
    adapter_name = (
        (adapter_name or os.getenv("ANCHOR_ADAPTER", "active_mock")).strip().lower()
    )
    if adapter_name == "active_mock":
        return ActiveMockAnchorAdapter()
    if adapter_name == "evm_contract":
        return _build_evm_adapter()
    if adapter_name == "reserved_stub":
        return ReservedDualChainStubAdapter()
    raise AnchorAdapterError(f"unsupported anchor adapter: {adapter_name}")


def _existing_receipt_for_event(
    session: Session, event_id: int
) -> AnchorReceipt | None:
    return session.scalar(
        select(AnchorReceipt)
        .where(AnchorReceipt.event_id == event_id)
        .order_by(AnchorReceipt.id.desc())
    )


def _existing_submission_for_event(
    session: Session, event_id: int
) -> AnchorSubmissionRecord | None:
    return session.scalar(
        select(AnchorSubmissionRecord)
        .where(AnchorSubmissionRecord.event_id == event_id)
        .where(AnchorSubmissionRecord.status == ANCHOR_SUBMISSION_PENDING)
        .order_by(AnchorSubmissionRecord.id.desc())
    )


def _retry_alert_severity(error: Exception) -> str:
    if isinstance(error, AnchorTimeoutError):
        return "medium"
    return "high"


def _transition_failure(
    session: Session,
    request: IngestRequest,
    *,
    error: Exception,
    max_retries: int,
    trace_id: str,
) -> str:
    request.retry_count += 1
    request.last_error = str(error)
    if request.retry_count >= max_retries:
        request.ingest_status = ANCHOR_STATE_DEAD_LETTER
        create_alert(
            session,
            event_id=request.event_id,
            alert_type=ALERT_TYPE_ANCHOR_DEAD_LETTER,
            severity="critical",
            message=(
                "Anchoring moved to dead letter after retry exhaustion. "
                f"Last error: {request.last_error}"
            ),
            status="open",
            suppression_window_seconds=0,
        )
        worker_logger.warning(
            "anchoring_transition outcome=dead_letter error=%s",
            request.last_error,
            extra=correlation_extra(trace_id=trace_id, event_id=request.event_id),
        )
        return "dead_letter"
    request.ingest_status = ANCHOR_STATE_FAILED_RETRYING
    create_alert(
        session,
        event_id=request.event_id,
        alert_type=ALERT_TYPE_ANCHOR_RETRY_FAILURE,
        severity=_retry_alert_severity(error),
        message=f"Anchoring failed and will retry. Error: {request.last_error}",
        status="open",
    )
    worker_logger.warning(
        "anchoring_transition outcome=failed_retrying error=%s",
        request.last_error,
        extra=correlation_extra(trace_id=trace_id, event_id=request.event_id),
    )
    return "failed_retrying"


def _anchor_request(
    session: Session,
    *,
    request: IngestRequest,
    adapter: AnchorAdapter,
    max_retries: int,
    rollout_controller: _RolloutController | None = None,
) -> None:
    trace_id = new_trace_id(prefix="worker")
    started_at = perf_counter()
    outcome = "failed_retrying"
    tx_hash = "-"
    active_submission: AnchorSubmissionRecord | None = None
    rollout_decision: _RolloutDecision | None = None
    confirmation_seconds: float | None = None
    event: _AnchoringEvent | None = None
    request.ingest_status = ANCHOR_STATE_ANCHORING
    request.last_error = None
    session.flush()

    try:
        existing_receipt = _existing_receipt_for_event(session, request.event_id)
        if existing_receipt is not None:
            request.ingest_status = ANCHOR_STATE_ANCHORED
            request.last_error = None
            outcome = "already_anchored"
            tx_hash = existing_receipt.transaction_hash
            worker_logger.info(
                "anchoring_skipped reason=existing_receipt",
                extra=correlation_extra(
                    trace_id=trace_id,
                    event_id=request.event_id,
                    tx_hash=tx_hash,
                ),
            )
            return

        event = _load_anchoring_event(session, request.event_id)
        if event is None:
            raise AnchorAdapterError(f"missing event for ingest request {request.id}")

        selected_adapter = adapter
        if rollout_controller is not None:
            rollout_decision = rollout_controller.decide(
                event_id=event.id,
                canonical_hash=event.canonical_hash,
            )
            selected_adapter = rollout_decision.adapter

        network = ""
        receipt = None
        recoverable_submission = _existing_submission_for_event(session, event.id)
        if recoverable_submission is not None:
            recovery_adapter = (
                rollout_controller.recovery_adapter()
                if rollout_controller is not None
                else selected_adapter
            )
            if recovery_adapter.supports_durable_submissions():
                selected_adapter = recovery_adapter
                active_submission = recoverable_submission
                tx_hash = recoverable_submission.transaction_hash
                network = recoverable_submission.network
                receipt = selected_adapter.get_receipt(
                    recoverable_submission.transaction_hash
                )
            else:
                recoverable_submission = None

        if recoverable_submission is None:
            submission = selected_adapter.anchor_event(
                event_id=event.id,
                canonical_hash=event.canonical_hash,
                payload=event.sensor_payload,
            )
            tx_hash = submission.transaction_hash
            network = submission.network
            active_submission = AnchorSubmissionRecord(
                event_id=event.id,
                network=submission.network,
                transaction_hash=submission.transaction_hash,
                canonical_hash=event.canonical_hash,
                status=ANCHOR_SUBMISSION_PENDING,
                metadata_=submission.metadata,
            )
            session.add(active_submission)
            session.flush()
            receipt = selected_adapter.get_receipt(submission.transaction_hash)

        if receipt is None:
            raise AnchorAdapterError("anchor receipt missing after submission")

        if not selected_adapter.verify_anchor(
            canonical_hash=event.canonical_hash, receipt=receipt
        ):
            raise AnchorVerificationError("anchor verification failed")

        if active_submission is not None:
            active_submission.status = ANCHOR_SUBMISSION_FINALIZED

        session.add(
            AnchorReceipt(
                event_id=event.id,
                network=network or receipt.network,
                transaction_hash=tx_hash,
                receipt_payload=receipt.receipt_payload,
                anchored_at=receipt.anchored_at,
            )
        )
        request.ingest_status = ANCHOR_STATE_ANCHORED
        request.last_error = None
        outcome = "anchored"
        confirmation_seconds = perf_counter() - started_at
        worker_logger.info(
            "anchoring_succeeded",
            extra=correlation_extra(
                trace_id=trace_id,
                event_id=event.id,
                tx_hash=tx_hash,
            ),
        )
        if (
            rollout_controller is not None
            and rollout_decision is not None
            and rollout_decision.shadow_probe
        ):
            rollout_controller.run_shadow_probe(event=event, trace_id=trace_id)
    except Exception as exc:  # noqa: BLE001 - all anchoring failures become state transitions.
        if active_submission is not None and isinstance(exc, AnchorVerificationError):
            active_submission.status = ANCHOR_SUBMISSION_REORGED
        outcome = _transition_failure(
            session,
            request,
            error=exc,
            max_retries=max_retries,
            trace_id=trace_id,
        )
    finally:
        if rollout_controller is not None and rollout_decision is not None:
            rollout_controller.observe_primary_outcome(
                decision=rollout_decision,
                outcome=outcome,
                confirmation_seconds=confirmation_seconds,
                trace_id=trace_id,
                event_id=request.event_id,
            )
        gate_outcome = {
            "anchored": "success",
            "already_anchored": "success",
            "failed_retrying": "retry",
            "dead_letter": "dead_letter",
        }.get(outcome)
        if gate_outcome is not None:
            observe_anchoring_outcome(outcome=gate_outcome)
        observe_anchoring_run(
            outcome=outcome,
            latency_seconds=perf_counter() - started_at,
        )
        worker_logger.info(
            "anchoring_processed outcome=%s",
            outcome,
            extra=correlation_extra(
                trace_id=trace_id,
                event_id=request.event_id,
                tx_hash=tx_hash,
            ),
        )


def run_anchor_state_machine(*, limit: int = 100, batch_id: str | None = None) -> int:
    configure_logging()
    database_url = _database_url()
    _ensure_schema(database_url)
    engine = _get_engine(database_url)
    adapter_name = os.getenv("ANCHOR_ADAPTER", "active_mock").strip().lower()
    rollout_controller = _build_rollout_controller(adapter_name=adapter_name)
    adapter = (
        rollout_controller.default_adapter()
        if rollout_controller is not None
        else _build_active_adapter()
    )
    max_retries = _max_retries()
    run_trace_id = new_trace_id(prefix="worker-run")

    with Session(engine) as session:
        pending_query = (
            select(IngestRequest)
            .where(
                IngestRequest.ingest_status.in_(
                    [
                        ANCHOR_STATE_RECEIVED,
                        ANCHOR_STATE_ANCHORING,
                        ANCHOR_STATE_FAILED_RETRYING,
                    ]
                )
            )
            .order_by(IngestRequest.id)
            .limit(limit)
        )
        if batch_id is not None:
            pending_query = pending_query.join(Event).where(Event.batch_id == batch_id)

        pending_requests = list(
            session.scalars(pending_query)
        )

        worker_logger.info(
            "anchoring_batch_started pending=%s limit=%s",
            len(pending_requests),
            limit,
            extra=correlation_extra(trace_id=run_trace_id),
        )

        for request in pending_requests:
            _anchor_request(
                session,
                request=request,
                adapter=adapter,
                max_retries=max_retries,
                rollout_controller=rollout_controller,
            )

        session.commit()
        worker_logger.info(
            "anchoring_batch_completed processed=%s",
            len(pending_requests),
            extra=correlation_extra(trace_id=run_trace_id),
        )
        return len(pending_requests)
