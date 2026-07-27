from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, schemas
from .db import Base, engine, get_session
from .seed import seed_demo
from .services import ControlPlaneService
from .voice import VoiceOperationsService


Base.metadata.create_all(bind=engine)
app = FastAPI(title="Production Agent Platform", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["content-type", "idempotency-key", "authorization"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "production-agent-platform"}


@app.post("/v1/tenants", response_model=schemas.TenantRead)
def create_tenant(payload: schemas.TenantCreate, session: Session = Depends(get_session)):
    return ControlPlaneService(session).create_tenant(payload.name)


@app.get("/v1/tenants", response_model=list[schemas.TenantRead])
def list_tenants(session: Session = Depends(get_session)):
    return list(session.scalars(select(models.Tenant).order_by(models.Tenant.created_at.desc())))


@app.post("/v1/agents", response_model=schemas.AgentRead)
def create_agent(payload: schemas.AgentCreate, session: Session = Depends(get_session)):
    try:
        return ControlPlaneService(session).create_agent(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/v1/agents", response_model=list[schemas.AgentRead])
def list_agents(tenant_id: str | None = None, session: Session = Depends(get_session)):
    query = select(models.AgentDefinition).order_by(models.AgentDefinition.created_at.desc())
    if tenant_id:
        query = query.where(models.AgentDefinition.tenant_id == tenant_id)
    return list(session.scalars(query))


@app.post("/v1/agents/{agent_id}/execute", response_model=schemas.ExecutionRead)
def execute_agent(agent_id: str, payload: schemas.ExecuteRequest, session: Session = Depends(get_session)):
    try:
        return ControlPlaneService(session).execute(agent_id, payload.tenant_id, payload.idempotency_key, payload.payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/v1/executions", response_model=list[schemas.ExecutionRead])
def list_executions(tenant_id: str | None = None, session: Session = Depends(get_session)):
    query = select(models.Execution).order_by(models.Execution.created_at.desc())
    if tenant_id:
        query = query.where(models.Execution.tenant_id == tenant_id)
    return list(session.scalars(query.limit(100)))


@app.post("/v1/executions/{execution_id}/approve", response_model=schemas.ExecutionRead)
def approve_execution(execution_id: str, payload: schemas.DecisionRequest, session: Session = Depends(get_session)):
    try:
        return ControlPlaneService(session).approve(execution_id, payload.actor, payload.note)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/v1/executions/{execution_id}/reject", response_model=schemas.ExecutionRead)
def reject_execution(execution_id: str, payload: schemas.DecisionRequest, session: Session = Depends(get_session)):
    try:
        return ControlPlaneService(session).reject(execution_id, payload.actor, payload.note)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/v1/executions/{execution_id}/cancel", response_model=schemas.ExecutionRead)
def cancel_execution(execution_id: str, payload: schemas.DecisionRequest, session: Session = Depends(get_session)):
    try:
        return ControlPlaneService(session).cancel(execution_id, payload.actor)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/v1/executions/{execution_id}/replay", response_model=schemas.ExecutionRead)
def replay_execution(execution_id: str, payload: schemas.DecisionRequest, session: Session = Depends(get_session)):
    try:
        return ControlPlaneService(session).replay(execution_id, payload.actor)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/v1/demo/seed")
def create_demo_data(session: Session = Depends(get_session)):
    seeded = seed_demo(session)
    return {
        "tenant": schemas.TenantRead.model_validate(seeded["tenant"]),
        "agents": [schemas.AgentRead.model_validate(agent) for agent in seeded["agents"]],
    }


@app.get("/v1/dead-letter", response_model=list[schemas.ExecutionRead])
def dead_letter(tenant_id: str | None = None, session: Session = Depends(get_session)):
    query = select(models.Execution).where(models.Execution.status == "failed").order_by(models.Execution.updated_at.desc())
    if tenant_id:
        query = query.where(models.Execution.tenant_id == tenant_id)
    return list(session.scalars(query.limit(100)))


@app.get("/v1/control-plane/metrics")
def control_plane_metrics(tenant_id: str | None = None, session: Session = Depends(get_session)):
    return ControlPlaneService(session).metrics(tenant_id)


@app.get("/v1/audit")
def audit_events(tenant_id: str | None = None, trace_id: str | None = None, session: Session = Depends(get_session)):
    query = select(models.AuditEvent).order_by(models.AuditEvent.created_at.desc())
    if tenant_id:
        query = query.where(models.AuditEvent.tenant_id == tenant_id)
    if trace_id:
        query = query.where(models.AuditEvent.trace_id == trace_id)
    return list(session.scalars(query.limit(200)))


@app.post("/v1/voice/calls")
def start_call(payload: schemas.CallCreate, session: Session = Depends(get_session)):
    try:
        call = VoiceOperationsService(session).start_call(payload.tenant_id, payload.provider_call_id, payload.caller_phone)
        return {"id": call.id, "status": call.status, "provider_call_id": call.provider_call_id}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/v1/voice/calls/{call_id}/turn")
def voice_turn(call_id: str, payload: schemas.VoiceTurnRequest, session: Session = Depends(get_session)):
    try:
        return VoiceOperationsService(session).process_turn(call_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/v1/voice/provider-events")
def provider_event(payload: schemas.ProviderEventCreate, session: Session = Depends(get_session)):
    event, created = VoiceOperationsService(session).receive_provider_event(payload.provider, payload.event_id, payload.payload)
    return {"event_id": event.event_id, "accepted": created, "duplicate": not created}


@app.get("/v1/voice/metrics")
def voice_metrics(tenant_id: str | None = None, session: Session = Depends(get_session)):
    return VoiceOperationsService(session).metrics(tenant_id)
