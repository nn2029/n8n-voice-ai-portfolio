from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .providers import ProviderRouter
from .queueing import QueueAdapter, build_queue


class ControlPlaneService:
    def __init__(self, session: Session, router: ProviderRouter | None = None, queue: QueueAdapter | None = None) -> None:
        self.session = session
        self.router = router or ProviderRouter()
        self.queue = queue or build_queue()

    def create_tenant(self, name: str) -> models.Tenant:
        tenant = models.Tenant(name=name)
        self.session.add(tenant)
        self.session.commit()
        return tenant

    def create_agent(self, **data) -> models.AgentDefinition:
        self._require_tenant(data["tenant_id"])
        agent = models.AgentDefinition(**data)
        self.session.add(agent)
        self.session.commit()
        return agent

    def execute(self, agent_id: str, tenant_id: str, idempotency_key: str, payload: dict) -> models.Execution:
        existing = self.session.scalar(
            select(models.Execution).where(
                models.Execution.tenant_id == tenant_id,
                models.Execution.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing

        agent = self.session.get(models.AgentDefinition, agent_id)
        if not agent or agent.tenant_id != tenant_id:
            raise ValueError("Agent does not belong to the supplied tenant.")

        trace_id = f"trc_{uuid4().hex}"
        execution = models.Execution(
            tenant_id=tenant_id,
            agent_id=agent.id,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
            status="queued",
            input_payload=payload,
        )
        self.session.add(execution)
        self._audit(tenant_id, trace_id, "execution.queued", "system", {"agent_id": agent.id})
        self.session.commit()
        self.queue.push(execution.id)
        return self.process_next() or execution

    def process_next(self) -> models.Execution | None:
        execution_id = self.queue.pop()
        if not execution_id:
            return None
        execution = self.session.get(models.Execution, execution_id)
        if not execution or execution.status != "queued":
            return execution
        agent = self.session.get(models.AgentDefinition, execution.agent_id)
        assert agent is not None
        execution.status = "running"
        self._audit(execution.tenant_id, execution.trace_id, "execution.running", "worker", {})
        self.session.commit()

        try:
            result = self.router.run(agent.provider, agent.kind, execution.input_payload)
            execution.proposed_action = result.content
            execution.provider_used = result.provider
            execution.latency_ms = result.latency_ms
            execution.token_cost_usd = result.token_cost_usd
            if self._needs_approval(agent, result.content):
                execution.status = "waiting_approval"
                self.session.add(
                    models.Approval(
                        tenant_id=execution.tenant_id,
                        execution_id=execution.id,
                        requested_reason="Agent policy requires a human to authorise this external or customer-facing action.",
                    )
                )
                self._audit(execution.tenant_id, execution.trace_id, "approval.requested", "worker", result.content)
            else:
                execution.output_payload = self._execute_authorised_action(agent.kind, result.content)
                execution.status = "completed"
                self._audit(execution.tenant_id, execution.trace_id, "execution.completed", "worker", execution.output_payload)
        except Exception as exc:
            execution.status = "failed"
            execution.failure_reason = f"{type(exc).__name__}: {exc}"
            self._audit(execution.tenant_id, execution.trace_id, "execution.failed", "worker", {"reason": execution.failure_reason})
        self.session.commit()
        return execution

    def approve(self, execution_id: str, actor: str, note: str | None = None) -> models.Execution:
        execution = self._require_execution(execution_id)
        if execution.status != "waiting_approval":
            raise ValueError("Execution is not waiting for approval.")
        approval = self.session.scalar(select(models.Approval).where(models.Approval.execution_id == execution_id))
        assert approval is not None
        approval.status = "approved"
        approval.decided_by = actor
        approval.decided_at = datetime.now(timezone.utc)
        agent = self.session.get(models.AgentDefinition, execution.agent_id)
        assert agent is not None
        execution.output_payload = self._execute_authorised_action(agent.kind, execution.proposed_action)
        execution.status = "completed"
        self._audit(execution.tenant_id, execution.trace_id, "approval.approved", actor, {"note": note or ""})
        self._audit(execution.tenant_id, execution.trace_id, "execution.completed", actor, execution.output_payload)
        self.session.commit()
        return execution

    def reject(self, execution_id: str, actor: str, note: str | None = None) -> models.Execution:
        execution = self._require_execution(execution_id)
        if execution.status != "waiting_approval":
            raise ValueError("Execution is not waiting for approval.")
        approval = self.session.scalar(select(models.Approval).where(models.Approval.execution_id == execution_id))
        assert approval is not None
        approval.status = "rejected"
        approval.decided_by = actor
        approval.decided_at = datetime.now(timezone.utc)
        execution.status = "cancelled"
        execution.failure_reason = note or "Rejected by human approver."
        self._audit(execution.tenant_id, execution.trace_id, "approval.rejected", actor, {"note": note or ""})
        self.session.commit()
        return execution

    def cancel(self, execution_id: str, actor: str) -> models.Execution:
        execution = self._require_execution(execution_id)
        if execution.status in {"completed", "cancelled"}:
            return execution
        execution.status = "cancelled"
        self._audit(execution.tenant_id, execution.trace_id, "execution.cancelled", actor, {})
        self.session.commit()
        return execution

    def replay(self, execution_id: str, actor: str) -> models.Execution:
        original = self._require_execution(execution_id)
        replay_key = f"replay:{original.id}:{uuid4().hex[:10]}"
        self._audit(original.tenant_id, original.trace_id, "execution.replay_requested", actor, {})
        self.session.commit()
        return self.execute(original.agent_id, original.tenant_id, replay_key, original.input_payload)

    def metrics(self, tenant_id: str | None = None) -> dict:
        filters = [models.Execution.tenant_id == tenant_id] if tenant_id else []
        rows = self.session.execute(
            select(models.Execution.status, func.count(models.Execution.id)).where(*filters).group_by(models.Execution.status)
        ).all()
        total_cost = self.session.scalar(select(func.coalesce(func.sum(models.Execution.token_cost_usd), 0.0)).where(*filters))
        return {"by_status": dict(rows), "token_cost_usd": round(float(total_cost or 0.0), 6)}

    def _needs_approval(self, agent: models.AgentDefinition, action: dict) -> bool:
        return bool(
            agent.requires_approval
            or action.get("requires_review")
            or action.get("recommended_action") in {"send_message", "issue_refund", "delete_record"}
        )

    def _execute_authorised_action(self, kind: str, action: dict) -> dict:
        return {
            "executed": True,
            "kind": kind,
            "action": action,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _require_tenant(self, tenant_id: str) -> models.Tenant:
        tenant = self.session.get(models.Tenant, tenant_id)
        if not tenant:
            raise ValueError("Tenant not found.")
        return tenant

    def _require_execution(self, execution_id: str) -> models.Execution:
        execution = self.session.get(models.Execution, execution_id)
        if not execution:
            raise ValueError("Execution not found.")
        return execution

    def _audit(self, tenant_id: str, trace_id: str, event_type: str, actor: str, details: dict) -> None:
        self.session.add(
            models.AuditEvent(
                tenant_id=tenant_id,
                trace_id=trace_id,
                event_type=event_type,
                actor=actor,
                details=details,
            )
        )
