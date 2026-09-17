from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Callable, Optional


@dataclass(frozen=True)
class QueueJob:
    """Represents a request waiting for background processing."""

    job_id: str
    file_path: str
    customer_message: str
    created_at: float


@dataclass
class QueueResult:
    """Result returned by the background queue."""

    job_id: str
    status: str
    message: str
    result: object | None = None


@dataclass
class BackgroundJobQueue:
    """
    Simple thread-based background queue.

    Jobs can be submitted when processing is expected to exceed
    the synchronous processing limit.

    The implementation is intentionally dependency-free so it
    works with the existing internship project.
    """

    worker_count: int = 1
    max_queue_size: int = 100

    _queue: Queue = field(
        default_factory=lambda: Queue(maxsize=100),
        init=False,
        repr=False,
    )

    _results: dict[str, QueueResult] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    _workers: list[threading.Thread] = field(
        default_factory=list,
        init=False,
        repr=False,
    )

    _lock: threading.Lock = field(
        default_factory=threading.Lock,
        init=False,
        repr=False,
    )

    _running: bool = field(
        default=False,
        init=False,
        repr=False,
    )

    _processor: Optional[
        Callable[[QueueJob], object]
    ] = field(
        default=None,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if isinstance(self.worker_count, bool):
            raise ValueError(
                "worker_count must be a positive integer"
            )

        if not isinstance(self.worker_count, int):
            raise ValueError(
                "worker_count must be a positive integer"
            )

        if self.worker_count <= 0:
            raise ValueError(
                "worker_count must be greater than zero"
            )

        if isinstance(self.max_queue_size, bool):
            raise ValueError(
                "max_queue_size must be a positive integer"
            )

        if not isinstance(self.max_queue_size, int):
            raise ValueError(
                "max_queue_size must be a positive integer"
            )

        if self.max_queue_size <= 0:
            raise ValueError(
                "max_queue_size must be greater than zero"
            )

        # Recreate the queue using the configured size.
        self._queue = Queue(
            maxsize=self.max_queue_size
        )

    # =========================================================
    # START / STOP
    # =========================================================

    def start(
        self,
        processor: Callable[[QueueJob], object],
    ) -> None:
        """
        Start background workers.

        processor receives a QueueJob and performs the actual
        long-running processing.
        """

        if not callable(processor):
            raise TypeError(
                "processor must be callable"
            )

        with self._lock:
            if self._running:
                return

            self._processor = processor
            self._running = True

            self._workers = []

            for index in range(self.worker_count):
                worker = threading.Thread(
                    target=self._worker_loop,
                    name=f"kb-worker-{index + 1}",
                    daemon=True,
                )

                self._workers.append(worker)
                worker.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop all background workers."""

        if isinstance(timeout, bool):
            raise TypeError(
                "timeout must be a number"
            )

        if timeout < 0:
            raise ValueError(
                "timeout must not be negative"
            )

        with self._lock:
            self._running = False

        for worker in self._workers:
            worker.join(timeout=timeout)

        self._workers.clear()

    # =========================================================
    # SUBMISSION
    # =========================================================

    def submit(
        self,
        file_path: str,
        customer_message: str,
    ) -> QueueResult:
        """
        Add a request to the background queue.
        """

        if not isinstance(file_path, str):
            raise TypeError(
                "file_path must be a string"
            )

        if not file_path.strip():
            raise ValueError(
                "file_path must not be empty"
            )

        if not isinstance(customer_message, str):
            raise TypeError(
                "customer_message must be a string"
            )

        if not self._running:
            raise RuntimeError(
                "Background queue is not running"
            )

        job_id = uuid.uuid4().hex

        job = QueueJob(
            job_id=job_id,
            file_path=file_path,
            customer_message=customer_message,
            created_at=time.time(),
        )

        try:
            self._queue.put_nowait(job)
        except Exception as exc:
            return QueueResult(
                job_id=job_id,
                status="queue_failed",
                message=f"Could not queue request: {exc}",
            )

        result = QueueResult(
            job_id=job_id,
            status="queued",
            message=(
                "Processing is taking longer than "
                "expected. Your request has been moved "
                "to the background queue."
            ),
        )

        with self._lock:
            self._results[job_id] = result

        return result

    # =========================================================
    # RESULT HANDLING
    # =========================================================

    def get_result(
        self,
        job_id: str,
    ) -> QueueResult | None:
        """Return the current result for a queued job."""

        if not isinstance(job_id, str):
            raise TypeError(
                "job_id must be a string"
            )

        with self._lock:
            return self._results.get(job_id)

    def pending_count(self) -> int:
        """Return the number of jobs waiting in the queue."""

        return self._queue.qsize()

    # =========================================================
    # WORKER
    # =========================================================

    def _worker_loop(self) -> None:
        while True:
            with self._lock:
                running = self._running
                processor = self._processor

            if not running:
                break

            if processor is None:
                time.sleep(0.05)
                continue

            try:
                job = self._queue.get(
                    timeout=0.1
                )
            except Empty:
                continue

            try:
                result = processor(job)

                queue_result = QueueResult(
                    job_id=job.job_id,
                    status="completed",
                    message=(
                        "Background processing completed."
                    ),
                    result=result,
                )

            except Exception as exc:
                queue_result = QueueResult(
                    job_id=job.job_id,
                    status="failed",
                    message=(
                        f"Background processing failed: {exc}"
                    ),
                )

            finally:
                self._queue.task_done()

            with self._lock:
                self._results[job.job_id] = queue_result


class ProcessingTimeout:
    """
    Utility for detecting when synchronous processing exceeds
    the configured time limit.
    """

    def __init__(
        self,
        timeout_seconds: float = 30.0,
    ) -> None:
        if isinstance(timeout_seconds, bool):
            raise ValueError(
                "timeout_seconds must be a positive number"
            )

        if not isinstance(
            timeout_seconds,
            (int, float),
        ):
            raise ValueError(
                "timeout_seconds must be a positive number"
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero"
            )

        self.timeout_seconds = float(
            timeout_seconds
        )

    def exceeded(
        self,
        started_at: float,
    ) -> bool:
        """Return True when the 30-second limit is exceeded."""

        if not isinstance(
            started_at,
            (int, float),
        ):
            raise TypeError(
                "started_at must be a number"
            )

        elapsed = time.time() - started_at

        return elapsed > self.timeout_seconds