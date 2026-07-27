"use client"

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react"

type Tenant = { id: string; name: string }
type Agent = { id: string; tenant_id: string; name: string; kind: string; requires_approval: boolean }
type Execution = {
  id: string
  tenant_id: string
  agent_id: string
  trace_id: string
  status: string
  provider_used: string
  proposed_action: Record<string, unknown>
  output_payload: Record<string, unknown>
  token_cost_usd: number
}
type Metrics = {
  by_status?: Record<string, number>
  token_cost_usd?: number
  calls_by_status?: Record<string, number>
  cost_usd?: number
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail || `Request failed: ${response.status}`)
  return data
}

export default function Home() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [executions, setExecutions] = useState<Execution[]>([])
  const [control, setControl] = useState<Metrics>({})
  const [voice, setVoice] = useState<Metrics>({})
  const [online, setOnline] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("Ready for deterministic demo mode.")
  const [callId, setCallId] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [health, tenantRows, agentRows, executionRows, controlMetrics, voiceMetrics] = await Promise.all([
        api<{ status: string }>("/health"),
        api<Tenant[]>("/v1/tenants"),
        api<Agent[]>("/v1/agents"),
        api<Execution[]>("/v1/executions"),
        api<Metrics>("/v1/control-plane/metrics"),
        api<Metrics>("/v1/voice/metrics"),
      ])
      setOnline(health.status === "ok")
      setTenants(tenantRows)
      setAgents(agentRows)
      setExecutions(executionRows)
      setControl(controlMetrics)
      setVoice(voiceMetrics)
    } catch (error) {
      setOnline(false)
      setMessage(error instanceof Error ? error.message : "API unavailable")
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const demoTenant = tenants.find((tenant) => tenant.name === "Demo Company") || tenants[0]
  const documentAgent = useMemo(
    () => agents.find((agent) => agent.tenant_id === demoTenant?.id && agent.kind === "document_generation"),
    [agents, demoTenant],
  )
  const waiting = executions.filter((execution) => execution.status === "waiting_approval")

  async function run(label: string, task: () => Promise<void>) {
    setBusy(true)
    setMessage(label)
    try {
      await task()
      await refresh()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed")
    } finally {
      setBusy(false)
    }
  }

  const seed = () => run("Creating tenant and reference agents…", async () => {
    await api("/v1/demo/seed", { method: "POST", body: "{}" })
    setMessage("Demo tenant and four agent definitions are ready.")
  })

  const executeDocument = () => run("Creating an approval-gated document execution…", async () => {
    if (!demoTenant || !documentAgent) throw new Error("Seed the demo data first.")
    const execution = await api<Execution>(`/v1/agents/${documentAgent.id}/execute`, {
      method: "POST",
      body: JSON.stringify({
        tenant_id: demoTenant.id,
        idempotency_key: `portfolio-${Date.now()}`,
        payload: { subject: "Customer renewal proposal", recipient: "Northwind Logistics", title: "Renewal" },
      }),
    })
    setMessage(`Execution ${execution.id.slice(0, 14)} entered ${execution.status}.`)
  })

  const approve = (executionId: string) => run("Approving the proposed action…", async () => {
    await api(`/v1/executions/${executionId}/approve`, {
      method: "POST",
      body: JSON.stringify({ actor: "portfolio-reviewer", note: "Approved from the operations UI demo." }),
    })
    setMessage("The authorised service completed the action and recorded the audit events.")
  })

  const startCall = () => run("Starting a deterministic voice call…", async () => {
    if (!demoTenant) throw new Error("Seed the demo data first.")
    const result = await api<{ id: string }>("/v1/voice/calls", {
      method: "POST",
      body: JSON.stringify({ tenant_id: demoTenant.id, provider_call_id: `demo-${Date.now()}`, caller_phone: "+2348001234567" }),
    })
    setCallId(result.id)
    setMessage(`Voice call ${result.id.slice(0, 14)} is active.`)
  })

  const book = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    return run("Booking through the validated calendar tool boundary…", async () => {
      if (!callId) throw new Error("Start a voice call first.")
      const form = new FormData(event.currentTarget)
      const startAt = String(form.get("start_at"))
      const result = await api<{ action: string; start_at: string }>(`/v1/voice/calls/${callId}/turn`, {
        method: "POST",
        body: JSON.stringify({
          transcript: `Please book ${startAt}`,
          intent: "book",
          contact_name: "Portfolio Reviewer",
          contact_email: "reviewer@example.test",
          start_at: new Date(startAt).toISOString(),
          duration_minutes: 30,
        }),
      })
      setMessage(`${result.action}: ${result.start_at}`)
    })
  }

  const emergency = () => run("Testing emergency escalation and failed-transfer fallback…", async () => {
    if (!callId) throw new Error("Start a voice call first.")
    const result = await api<{ action: string; transfer_status: string }>(`/v1/voice/calls/${callId}/turn`, {
      method: "POST",
      body: JSON.stringify({ transcript: "There is a fire and immediate danger", intent: "unknown", simulate_transfer_failure: true }),
    })
    setMessage(`${result.action}; transfer status: ${result.transfer_status}. The failure was recorded instead of hidden.`)
  })

  return (
    <main>
      <header>
        <p className="eyebrow">Production agent platform</p>
        <h1>AI automation with explicit authority, approvals, traces, and recovery.</h1>
        <p className="lede">One operations surface for multi-tenant workflow agents and voice operations: tool boundaries, idempotency, booking safety, human handoff, cost telemetry, and audit history.</p>
        <div className="headerRow">
          <span className={online ? "status online" : "status"}>{online ? "API online" : "API unavailable"}</span>
          <span className="message">{message}</span>
        </div>
      </header>

      <section className="actionBar" aria-label="Demo controls">
        <button onClick={seed} disabled={busy}>1. Seed demo</button>
        <button onClick={executeDocument} disabled={busy || !documentAgent}>2. Run gated agent</button>
        <button onClick={startCall} disabled={busy || !demoTenant}>3. Start voice call</button>
        <button onClick={emergency} disabled={busy || !callId}>4. Test escalation</button>
      </section>

      <section className="grid">
        <article>
          <p className="eyebrow">Automation control plane</p>
          <h2>Executions</h2>
          <pre>{JSON.stringify(control.by_status || {}, null, 2)}</pre>
          <p>Tracked model cost: ${Number(control.token_cost_usd || 0).toFixed(4)}</p>
          {waiting.map((execution) => (
            <div className="approval" key={execution.id}>
              <div><strong>Human approval required</strong><small>{execution.trace_id}</small></div>
              <button onClick={() => approve(execution.id)} disabled={busy}>Approve</button>
            </div>
          ))}
        </article>

        <article>
          <p className="eyebrow">Voice operations</p>
          <h2>Calls</h2>
          <pre>{JSON.stringify(voice.calls_by_status || {}, null, 2)}</pre>
          <p>Tracked call cost: ${Number(voice.cost_usd || 0).toFixed(4)}</p>
          <form onSubmit={book} className="bookingForm">
            <label htmlFor="start_at">Conflict-safe appointment slot</label>
            <input id="start_at" name="start_at" type="datetime-local" defaultValue="2026-08-05T10:00" required />
            <button disabled={busy || !callId}>Book appointment</button>
          </form>
        </article>
      </section>

      <section className="capabilities">
        {[
          ["Tenant-scoped agents", "Definitions, executions, approvals and audit events are always tenant-bound."],
          ["Model authority boundary", "Models recommend structured actions; authorised services decide whether those actions execute."],
          ["Human approval", "Customer-facing and sensitive actions pause in a reviewable approval state."],
          ["Voice booking safety", "Appointment writes are conflict-protected and duplicate provider events are ignored."],
          ["Escalation", "Low-confidence, unsupported and emergency requests transfer or fall back to a bounded message path."],
          ["Replay and observability", "Every run carries a trace ID, status, provider, latency, cost and audit sequence."],
        ].map(([title, body]) => <article key={title}><h3>{title}</h3><p>{body}</p></article>)}
      </section>
    </main>
  )
}
