# Security and privacy boundary

This portfolio project contains no real customer data, credentials, provider secrets, private prompts, or production recordings.

## Implemented controls

- tenant-bound agent execution;
- duplicate-safe execution and provider event IDs;
- model recommendation separated from authorised action execution;
- explicit human approval and rejection states;
- conflict-safe appointment writes;
- bounded emergency and low-confidence escalation;
- public-safe audit metadata and trace IDs;
- no provider credentials in n8n exports.

## Required before real deployment

- authenticated users, tenant API keys or SSO, and RBAC;
- webhook signature verification and replay windows;
- managed secrets and rotation;
- encryption and retention controls for transcripts and recordings;
- consent notices appropriate to the deployment jurisdiction;
- structured audit export, alerting, backups, and incident response;
- provider-specific threat modelling and penetration testing;
- legal and privacy review.

This repository does not claim HIPAA, PCI DSS, SOC 2, GDPR, or any other certification.
