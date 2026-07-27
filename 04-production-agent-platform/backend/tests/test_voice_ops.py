from datetime import datetime, timezone

import pytest

from app.services import ControlPlaneService
from app.voice import VoiceOperationsService


def test_booking_conflict_is_rejected(session):
    tenant = ControlPlaneService(session).create_tenant("Clinic")
    voice = VoiceOperationsService(session)
    first_call = voice.start_call(tenant.id, "call-1", "+234800000001")
    second_call = voice.start_call(tenant.id, "call-2", "+234800000002")
    slot = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)

    result = voice.process_turn(first_call.id, "Book me for ten", "book", "Ada", None, slot, 30)
    assert result["action"] == "appointment_booked"

    with pytest.raises(ValueError, match="no longer available"):
        voice.process_turn(second_call.id, "Same slot please", "book", "Grace", None, slot, 30)


def test_provider_callbacks_are_idempotent(session):
    voice = VoiceOperationsService(session)
    first, created = voice.receive_provider_event("vapi", "evt-1", {"type": "call-ended"})
    second, created_again = voice.receive_provider_event("vapi", "evt-1", {"type": "call-ended"})
    assert created is True
    assert created_again is False
    assert first.id == second.id


def test_emergency_language_escalates_and_transfer_failure_is_bounded(session):
    tenant = ControlPlaneService(session).create_tenant("Support")
    voice = VoiceOperationsService(session)
    call = voice.start_call(tenant.id, "call-emergency", "+234800000003")
    result = voice.process_turn(
        call.id,
        "There is a fire and immediate danger",
        "unknown",
        simulate_transfer_failure=True,
    )
    assert result["escalated"] is True
    assert result["transfer_status"] == "failed"
    assert result["action"] == "take_message"
