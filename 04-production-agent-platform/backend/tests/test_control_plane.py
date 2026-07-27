import pytest

from app.services import ControlPlaneService


def test_execution_is_idempotent_and_requires_approval(session):
    service = ControlPlaneService(session)
    tenant = service.create_tenant("Acme")
    agent = service.create_agent(
        tenant_id=tenant.id,
        name="Proposal generator",
        kind="document_generation",
        provider="mock",
        requires_approval=True,
        config={},
    )

    first = service.execute(agent.id, tenant.id, "proposal-42", {"subject": "Renewal proposal"})
    second = service.execute(agent.id, tenant.id, "proposal-42", {"subject": "Changed payload"})

    assert first.id == second.id
    assert first.status == "waiting_approval"
    approved = service.approve(first.id, "nasir")
    assert approved.status == "completed"
    assert approved.output_payload["executed"] is True


def test_replay_creates_a_new_trace(session):
    service = ControlPlaneService(session)
    tenant = service.create_tenant("Northwind")
    agent = service.create_agent(
        tenant_id=tenant.id,
        name="CRM updater",
        kind="crm_update",
        provider="mock",
        requires_approval=False,
        config={},
    )
    original = service.execute(agent.id, tenant.id, "crm-1", {"name": "Ada"})
    replay = service.replay(original.id, "operator")
    assert original.status == "completed"
    assert replay.status == "completed"
    assert replay.id != original.id
    assert replay.trace_id != original.trace_id


def test_tenant_boundary_blocks_cross_tenant_execution(session):
    service = ControlPlaneService(session)
    first = service.create_tenant("First")
    second = service.create_tenant("Second")
    agent = service.create_agent(
        tenant_id=first.id,
        name="Email triage",
        kind="email_triage",
        provider="mock",
        requires_approval=False,
        config={},
    )
    with pytest.raises(ValueError, match="does not belong"):
        service.execute(agent.id, second.id, "cross-tenant", {"subject": "Test"})
