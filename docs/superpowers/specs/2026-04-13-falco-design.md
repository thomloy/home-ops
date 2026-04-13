# Falco — Design Spec

**Date:** 2026-04-13
**Namespace:** observability (existing)
**Status:** Approved

---

## Context

Add Falco runtime security monitoring to the homelab cluster. Falco captures kernel syscalls via eBPF and generates alerts when suspicious behaviour is detected (shell in container, sensitive file access, privilege escalation attempts, unexpected network activity).

The current observability stack (Fluent Bit → Victoria Logs, Prometheus → Alertmanager) covers logs and metrics but has no runtime security layer. Falco fills this gap.

---

## Architecture

```
Kernel syscalls (eBPF)
        │
        ▼
[Falco DaemonSet]          ← modern_ebpf driver, one pod per node
        │  events (JSON)
        ▼
[Falco Sidekick]           ← routes events to multiple outputs
        ├──→ Victoria Logs  (all events, priority >= debug)
        └──→ Alertmanager   (critical events only, priority >= warning)
```

---

## Files

```
kubernetes/apps/observability/
├── kustomization.yaml          ← add ./falco/ks.yaml
└── falco/
    ├── ks.yaml                 ← Flux Kustomization
    └── app/
        ├── kustomization.yaml
        ├── ocirepository.yaml  ← ghcr.io/falcosecurity/charts/falco
        └── helmrelease.yaml    ← Falco + Sidekick values
```

---

## Flux Kustomization (`ks.yaml`)

- `targetNamespace: observability`
- `dependsOn: kube-prometheus-stack, victoria-logs`
- `wait: false`

---

## HelmRelease

### Falco

| Key | Value |
|-----|-------|
| `driver.kind` | `modern_ebpf` |
| `falco.rules_files` | default + incubating rules |
| `serviceMonitor.enabled` | `true` |

### Falco Sidekick

| Output | Endpoint | Min priority |
|--------|----------|--------------|
| Loki (→ Victoria Logs) | `http://victoria-logs-server.observability.svc.cluster.local:9428` | `debug` |
| Alertmanager | `http://kube-prometheus-stack-alertmanager.observability.svc.cluster.local:9093` | `warning` |

Victoria Logs exposes a Loki-compatible `/loki/api/v1/push` endpoint — Sidekick uses the `loki` output type.

---

## Notes

- No `externalsecret.yaml` needed — no credentials required for internal cluster endpoints
- No PVC — Falco is stateless (events forwarded, not stored locally)
- Renovate will pick up chart version updates automatically via the OCIRepository tag
