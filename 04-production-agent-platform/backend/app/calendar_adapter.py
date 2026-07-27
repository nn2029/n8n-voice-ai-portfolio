from __future__ import annotations

import os
from datetime import datetime
from uuid import uuid4

import httpx


class CalendarAdapter:
    """Calendar boundary with deterministic local mode and an HTTP live-provider path.

    Point CALENDAR_TOOL_URL at a Google Calendar integration service that accepts
    validated create-event requests. The model never receives calendar credentials.
    """

    def create_event(self, title: str, start_at: datetime, end_at: datetime, idempotency_key: str) -> str:
        url = os.getenv("CALENDAR_TOOL_URL")
        if not url:
            return f"demo_{uuid4().hex[:12]}"
        headers = {"Idempotency-Key": idempotency_key}
        token = os.getenv("CALENDAR_TOOL_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = httpx.post(
            url,
            headers=headers,
            json={"title": title, "start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        event_id = data.get("event_id") or data.get("id")
        if not event_id:
            raise RuntimeError("Calendar adapter response did not include an event id.")
        return str(event_id)
