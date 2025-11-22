import json
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

import redis

from .config import settings


class EventListener:
    """listens to redis events and maintains job state"""

    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe("ocr:events")

        # in-memory storage for jobs
        # structure: {recognition_id: job_data}
        self.jobs: dict[str, dict[str, Any]] = {}

        # lock for thread-safe access
        self.lock = threading.Lock()

        # background thread for listening
        self.listener_thread = None
        self.running = False

    def start_listening(self):
        """start background thread to listen for events"""
        if self.running:
            return

        self.running = True
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listener_thread.start()

    def stop_listening(self):
        """stop background listener"""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2)

    def _listen_loop(self):
        """background loop for processing redis messages"""
        while self.running:
            try:
                message = self.pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        event_name = data.get("event")
                        if event_name:
                            self._handle_event(event_name, data)
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass

    def _handle_event(self, event: str, data: dict[str, Any]):
        """handle incoming event and update job state"""
        recognition_id = data.get("recognitionId")
        if not recognition_id:
            return

        with self.lock:
            if recognition_id not in self.jobs:
                self.jobs[recognition_id] = {
                    "id": recognition_id,
                    "imageId": data.get("imageId", ""),
                    "status": "queued",
                    "stages": [],
                    "createdAt": datetime.now().isoformat(),
                    "sourceService": data.get("sourceService"),
                    "sourceReference": data.get("sourceReference"),
                }

            job = self.jobs[recognition_id]

            if event == "ocr.queued":
                job["status"] = "queued"
                job["position"] = data.get("position", 0)
                job["estimatedWait"] = data.get("estimatedWait", 0)

            elif event == "ocr.processing":
                job["status"] = "processing"
                job["processingStartedAt"] = datetime.now().isoformat()

            elif event == "ocr.debug.step" or event == "aligner.debug.step":
                stage = {
                    "step": data.get("step", "unknown"),
                    "stepNumber": data.get("stepNumber", 0),
                    "imageKey": data.get("imageKey", ""),
                    "description": data.get("description", ""),
                    "metadata": data.get("metadata", {}),
                    "timestamp": data.get("timestamp", time.time()),
                    "source": "aligner" if event == "aligner.debug.step" else "gateway",
                }
                job["stages"].append(stage)
                # sort stages by step number
                job["stages"].sort(key=lambda x: x["stepNumber"])

            elif event == "ocr.completed":
                job["status"] = "completed"
                job["completedAt"] = datetime.now().isoformat()
                job["resultType"] = data.get("resultType")
                job["processingTime"] = data.get("processingTime")

                if data.get("text"):
                    job["text"] = data["text"]
                if data.get("qr"):
                    job["qr"] = data["qr"]

            elif event == "ocr.failed":
                job["status"] = "failed"
                job["completedAt"] = datetime.now().isoformat()
                job["error"] = data.get("error", "unknown error")

    def get_jobs(self, limit: int | None = None, status: str | None = None) -> list[dict]:
        """
        get jobs with optional filtering

        args:
            limit: max number of jobs to return
            status: filter by status (queued, processing, completed, failed)

        returns:
            list of job dicts
        """
        with self.lock:
            jobs = list(self.jobs.values())

        # filter by status
        if status:
            jobs = [j for j in jobs if j.get("status") == status]

        # sort by created time (newest first)
        jobs.sort(key=lambda x: x.get("createdAt", ""), reverse=True)

        # limit
        if limit:
            jobs = jobs[:limit]

        return jobs

    def get_job(self, recognition_id: str) -> dict | None:
        """get single job by id"""
        with self.lock:
            return self.jobs.get(recognition_id)

    def get_stats(self) -> dict[str, int]:
        """get job statistics"""
        with self.lock:
            jobs = list(self.jobs.values())

        stats = defaultdict(int)
        for job in jobs:
            status = job.get("status", "unknown")
            stats[status] += 1
        stats["total"] = len(jobs)

        return dict(stats)
