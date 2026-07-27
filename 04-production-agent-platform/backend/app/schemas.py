from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)


class TenantRead(ORMModel):
    id: str
    name: str
    created_at: datetime


class AgentCreate(BaseModel):
    tenant_id: str
    name: str = Field(min_length=2, max_length=160)
    kind: Literal["email_triage", "crm_update", "document_generation", "daily_report"]
    provider: Literal["auto", "mock", "openai", "anthropic"] = "auto"
    requires_approval: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class AgentRead(ORMModel):
    id: str
    tenant_id: str
    name: str
    kind: str
    provider: str
    requires_approval: bool
    config: dict[str, Any]
    created_at: datetime


class ExecuteRequest(BaseModel):
    tenant_id: str
    idempotency_key: str = Field(min_length=3, max_length=180)
    payload: dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    actor: str = Field(min_length=2, max_length=160)
    note: str | None = Field(default=None, max_length=1000)


class ExecutionRead(ORMModel):
    id: str
    tenant_id: str
    agent_id: str
    idempotency_key: str
    trace_id: str
    status: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    proposed_action: dict[str, Any]
    provider_used: str
    failure_reason: str | None
    latency_ms: int
    token_cost_usd: float
    created_at: datetime
    updated_at: datetime


class CallCreate(BaseModel):
    tenant_id: str
    provider_call_id: str = Field(min_length=3, max_length=180)
    caller_phone: str = Field(min_length=5, max_length=40)


class VoiceTurnRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4000)
    intent: Literal["faq", "book", "reschedule", "crm_update", "end_call", "unknown"] = "unknown"
    contact_name: str | None = Field(default=None, max_length=160)
    contact_email: str | None = Field(default=None, max_length=200)
    start_at: datetime | None = None
    duration_minutes: int = Field(default=30, ge=10, le=180)
    simulate_transfer_failure: bool = False


class ProviderEventCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=40)
    event_id: str = Field(min_length=3, max_length=180)
    payload: dict[str, Any] = Field(default_factory=dict)
