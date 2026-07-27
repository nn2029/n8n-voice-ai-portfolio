from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .calendar_adapter import CalendarAdapter


EMERGENCY_TERMS = {"suicide", "kill myself", "heart attack", "fire", "immediate danger", "emergency"}
KNOWLEDGE = {
    "hours": "We are open Monday to Friday, 09:00 to 17:00.",
    "pricing": "Consultations start at $75; final pricing depends on the selected service.",
    "location": "Appointments can be remote or at the configured business location.",
}


class VoiceOperationsService:
    def __init__(self, session: Session, calendar: CalendarAdapter | None = None) -> None:
        self.session = session
        self.calendar = calendar or CalendarAdapter()

    def start_call(self, tenant_id: str, provider_call_id: str, caller_phone: str) -> models.VoiceCall:
        existing = self.session.scalar(select(models.VoiceCall).where(models.VoiceCall.provider_call_id == provider_call_id))
        if existing:
            return existing
        if not self.session.get(models.Tenant, tenant_id):
            raise ValueError("Tenant not found.")
        call = models.VoiceCall(tenant_id=tenant_id, provider_call_id=provider_call_id, caller_phone=caller_phone)
        self.session.add(call)
        self.session.commit()
        return call

    def process_turn(
        self,
        call_id: str,
        transcript: str,
        intent: str,
        contact_name: str | None = None,
        contact_email: str | None = None,
        start_at: datetime | None = None,
        duration_minutes: int = 30,
        simulate_transfer_failure: bool = False,
    ) -> dict:
        call = self._require_call(call_id)
        call.transcript = (call.transcript + "\n" + transcript).strip()
        call.intent = intent
        lowered = transcript.lower()
        if any(term in lowered for term in EMERGENCY_TERMS):
            return self._escalate(call, "Emergency or immediate-danger language detected.", simulate_transfer_failure)

        if intent == "faq":
            answer, confidence, source = self._retrieve_faq(lowered)
            if confidence < 0.35:
                return self._escalate(call, "FAQ evidence confidence below threshold.", simulate_transfer_failure)
            response = {"action": "answer_faq", "answer": answer, "source": source, "confidence": confidence}
        elif intent in {"book", "reschedule"}:
            if not start_at:
                raise ValueError("start_at is required for booking or rescheduling.")
            contact = self._upsert_contact(call.tenant_id, call.caller_phone, contact_name or "Caller", contact_email)
            appointment = self._book(call.tenant_id, contact.id, start_at, duration_minutes)
            response = {"action": "appointment_booked", "appointment_id": appointment.id, "start_at": appointment.start_at.isoformat()}
        elif intent == "crm_update":
            contact = self._upsert_contact(call.tenant_id, call.caller_phone, contact_name or "Caller", contact_email)
            response = {"action": "crm_updated", "contact_id": contact.id}
        elif intent == "end_call":
            call.status = "completed"
            call.summary = self._summarise(call)
            response = {"action": "end_call", "summary": call.summary}
        else:
            return self._escalate(call, "Unsupported or ambiguous intent.", simulate_transfer_failure)

        call.tool_history = [*call.tool_history, response]
        call.latency_ms += 40
        call.cost_usd = round(call.cost_usd + 0.006, 4)
        self.session.commit()
        return response

    def receive_provider_event(self, provider: str, event_id: str, payload: dict) -> tuple[models.ProviderEvent, bool]:
        existing = self.session.scalar(select(models.ProviderEvent).where(models.ProviderEvent.event_id == event_id))
        if existing:
            return existing, False
        event = models.ProviderEvent(provider=provider, event_id=event_id, payload=payload, processed=True)
        self.session.add(event)
        self.session.commit()
        return event, True

    def metrics(self, tenant_id: str | None = None) -> dict:
        filters = [models.VoiceCall.tenant_id == tenant_id] if tenant_id else []
        rows = self.session.execute(
            select(models.VoiceCall.status, func.count(models.VoiceCall.id)).where(*filters).group_by(models.VoiceCall.status)
        ).all()
        total_cost = self.session.scalar(select(func.coalesce(func.sum(models.VoiceCall.cost_usd), 0.0)).where(*filters))
        return {"calls_by_status": dict(rows), "cost_usd": round(float(total_cost or 0.0), 4)}

    def _retrieve_faq(self, query: str) -> tuple[str, float, str]:
        query_terms = set(query.replace("?", "").split())
        best_key = ""
        best_score = 0.0
        for key, answer in KNOWLEDGE.items():
            terms = set((key + " " + answer).lower().replace(".", "").split())
            overlap = len(query_terms & terms)
            score = overlap / max(len(query_terms), 1)
            if score > best_score:
                best_key, best_score = key, score
        if not best_key:
            return "I do not have a grounded answer for that question.", 0.0, "none"
        return KNOWLEDGE[best_key], round(min(1.0, best_score + 0.25), 3), best_key

    def _book(self, tenant_id: str, contact_id: str, start_at: datetime, duration_minutes: int) -> models.Appointment:
        end_at = start_at + timedelta(minutes=duration_minutes)
        event_id = self.calendar.create_event(
            title="Voice-booked appointment",
            start_at=start_at,
            end_at=end_at,
            idempotency_key=f"{tenant_id}:{start_at.isoformat()}",
        )
        appointment = models.Appointment(
            tenant_id=tenant_id,
            contact_id=contact_id,
            start_at=start_at,
            end_at=end_at,
            external_event_id=event_id,
        )
        self.session.add(appointment)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ValueError("The requested appointment slot is no longer available.") from exc
        return appointment

    def _upsert_contact(self, tenant_id: str, phone: str, name: str, email: str | None) -> models.Contact:
        contact = self.session.scalar(
            select(models.Contact).where(models.Contact.tenant_id == tenant_id, models.Contact.phone == phone)
        )
        if contact:
            contact.name = name or contact.name
            contact.email = email or contact.email
            self.session.commit()
            return contact
        contact = models.Contact(tenant_id=tenant_id, phone=phone, name=name, email=email)
        self.session.add(contact)
        self.session.commit()
        return contact

    def _escalate(self, call: models.VoiceCall, reason: str, simulate_failure: bool) -> dict:
        call.escalation_reason = reason
        if simulate_failure:
            call.status = "handoff_failed"
            response = {"action": "take_message", "escalated": True, "transfer_status": "failed", "reason": reason}
        else:
            call.status = "transferred"
            response = {"action": "human_transfer", "escalated": True, "transfer_status": "connected", "reason": reason}
        call.tool_history = [*call.tool_history, response]
        self.session.commit()
        return response

    def _summarise(self, call: models.VoiceCall) -> str:
        transcript = " ".join(call.transcript.split())
        return f"Call completed with intent={call.intent or 'unknown'}. Transcript preview: {transcript[:220]}"

    def _require_call(self, call_id: str) -> models.VoiceCall:
        call = self.session.get(models.VoiceCall, call_id)
        if not call:
            raise ValueError("Call not found.")
        return call
