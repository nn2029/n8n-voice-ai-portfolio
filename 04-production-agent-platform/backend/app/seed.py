from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .services import ControlPlaneService


def seed_demo(session: Session) -> dict:
    tenant = session.scalar(select(models.Tenant).where(models.Tenant.name == "Demo Company"))
    service = ControlPlaneService(session)
    if not tenant:
        tenant = service.create_tenant("Demo Company")

    existing = list(session.scalars(select(models.AgentDefinition).where(models.AgentDefinition.tenant_id == tenant.id)))
    by_kind = {agent.kind: agent for agent in existing}
    definitions = [
        ("email_triage", "Support email triage", False),
        ("crm_update", "CRM update agent", False),
        ("document_generation", "Proposal document agent", True),
        ("daily_report", "Daily operations report", False),
    ]
    for kind, name, approval in definitions:
        if kind not in by_kind:
            by_kind[kind] = service.create_agent(
                tenant_id=tenant.id,
                name=name,
                kind=kind,
                provider="mock",
                requires_approval=approval,
                config={"demo": True},
            )
    return {"tenant": tenant, "agents": list(by_kind.values())}
