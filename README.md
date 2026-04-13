<div align="center">
<img src="https://github.com/thomloy/home-ops/blob/main/assets/logo-home-ops.png" align="center" width="420px" height="420px"/>

### <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f680/512.gif" alt="🚀" width="16" height="16"> My Home Operations Repository <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f6a7/512.gif" alt="🚧" width="16" height="16">

_... managed with Flux, Renovate, and GitHub Actions_ <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f916/512.gif" alt="🤖" width="16" height="16">

</div>

<div align="center">

[![Discord](https://img.shields.io/discord/673534664354430999?style=for-the-badge&label&logo=discord&logoColor=white&color=blue)](https://discord.gg/home-operations)&nbsp;&nbsp;
[![Talos](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Ftalos_version&style=for-the-badge&logo=talos&logoColor=white&color=blue&label=%20)](https://talos.dev)&nbsp;&nbsp;
[![Kubernetes](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fkubernetes_version&style=for-the-badge&logo=kubernetes&logoColor=white&color=blue&label=%20)](https://kubernetes.io)&nbsp;&nbsp;
[![Flux](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fflux_version&style=for-the-badge&logo=flux&logoColor=white&color=blue&label=%20)](https://fluxcd.io)&nbsp;&nbsp;
[![Renovate](https://img.shields.io/github/actions/workflow/status/thomloy/home-ops/renovate.yaml?branch=main&label=&logo=renovatebot&style=for-the-badge&color=blue)](https://github.com/thomloy/home-ops/actions/workflows/renovate.yaml)

</div>

<div align="center">

[![Home-Internet](https://img.shields.io/endpoint?url=https%3A%2F%2Fstatus.k13.dev%2Fapi%2Fv1%2Fendpoints%2Fbuddy_ping%2Fhealth%2Fbadge.shields&style=for-the-badge&logo=opnsense&logoColor=white&label=Home%20Internet)](https://status.kryzql.space)&nbsp;&nbsp;
[![Status-Page](https://img.shields.io/endpoint?url=https%3A%2F%2Fstatus.k13.dev%2Fapi%2Fv1%2Fendpoints%2Fbuddy_status-page%2Fhealth%2Fbadge.shields&style=for-the-badge&logo=statuspage&logoColor=white&label=Status%20Page)](https://status.kryzql.space)&nbsp;&nbsp;
[![Alertmanager](https://img.shields.io/endpoint?url=https%3A%2F%2Fstatus.k13.dev%2Fapi%2Fv1%2Fendpoints%2Fbuddy_heartbeat%2Fhealth%2Fbadge.shields&style=for-the-badge&logo=prometheus&logoColor=white&label=Alertmanager)](https://status.kryzql.space)

</div>

<div align="center">

[![Age-Days](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fcluster_age_days&style=flat-square&label=Age)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Uptime-Days](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fcluster_uptime_days&style=flat-square&label=Uptime)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Node-Count](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fcluster_node_count&style=flat-square&label=Nodes)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Pod-Count](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fcluster_pod_count&style=flat-square&label=Pods)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![CPU-Usage](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fcluster_cpu_usage&style=flat-square&label=CPU)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Memory-Usage](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fcluster_memory_usage&style=flat-square&label=Memory)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Power-Usage](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fcluster_power_usage&style=flat-square&label=Power&cacheSeconds=300)](https://github.com/kashalls/kromgo)&nbsp;&nbsp;
[![Alerts](https://img.shields.io/endpoint?url=https%3A%2F%2Fkromgo.kryzql.space%2Fcluster_alert_count&style=flat-square&label=Alerts)](https://github.com/kashalls/kromgo)

</div>

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f4a1/512.gif" alt="💡" width="20" height="20"> Overview

Welcome to my home operations repository, this is a mono repository for my home infrastructure and Kubernetes cluster. I try to adhere to Infrastructure as Code (IaC) and GitOps practices using tools like [Ansible](https://www.ansible.com/), [Kubernetes](https://kubernetes.io/), [Flux](https://github.com/fluxcd/flux2), [Renovate](https://github.com/renovatebot/renovate), and [GitHub Actions](https://github.com/features/actions). Secrets are encrypted at rest with [SOPS](https://github.com/getsops/sops) and [Age](https://github.com/FiloSottile/age).

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f331/512.gif" alt="🌱" width="20" height="20"> Kubernetes

My Kubernetes cluster is deployed with [Talos](https://www.talos.dev). This is a semi-hyper-converged cluster, workloads and block storage are sharing the same available resources on my nodes while I have a separate server with ZFS for NFS/SMB shares, bulk file storage and backups.

### Core Components

- **Networking & Service Mesh**: [cilium](https://github.com/cilium/cilium) provides eBPF-based networking, while [istio](https://istio.io/latest/) powers service-to-service communication with L7 proxying and traffic management. [cloudflared](https://github.com/cloudflare/cloudflared) secures ingress traffic via Cloudflare, and [external-dns](https://github.com/kubernetes-sigs/external-dns) keeps DNS records in sync automatically.
- **Security & Secrets**: [cert-manager](https://github.com/cert-manager/cert-manager) automates SSL/TLS certificate management. For secrets, I use [external-secrets](https://github.com/external-secrets/external-secrets) with [1Password Connect](https://github.com/1Password/connect) to inject secrets into Kubernetes.
- **Storage & Data Protection**: [rook](https://github.com/rook/rook) provides distributed storage for persistent volumes, with [volsync](https://github.com/backube/volsync) handling backups and restores. [spegel](https://github.com/spegel-org/spegel) improves reliability by running a stateless, cluster-local OCI image mirror.
- **Automation & CI/CD**: [actions-runner-controller](https://github.com/actions/actions-runner-controller) runs self-hosted GitHub Actions runners directly in the cluster for continuous integration workflows.

### GitOps

[Flux](https://github.com/fluxcd/flux2) watches the clusters in my [kubernetes](./kubernetes/) folder (see Directories below) and makes the changes to my clusters based on the state of my Git repository.

The way Flux works for me here is it will recursively search the `kubernetes/apps` folder until it finds the most top level `kustomization.yaml` per directory and then apply all the resources listed in it. That aforementioned `kustomization.yaml` will generally only have a namespace resource and one or many Flux kustomizations (`ks.yaml`). Under the control of those Flux kustomizations there will be a `HelmRelease` or other resources related to the application which will be applied.

[Renovate](https://github.com/renovatebot/renovate) watches my **entire** repository looking for dependency updates, when they are found a PR is automatically created. When some PRs are merged Flux applies the changes to my cluster.

### Directories

This Git repository contains the following directories under [Kubernetes](./kubernetes/).

```sh
📁 kubernetes
├── 📁 apps       # applications
├── 📁 components # re-useable kustomize components
└── 📁 flux       # flux system configuration
📁 ansible
├── 📁 inventory  # hosts and group_vars
└── 📁 playbooks  # bootstrap, nas, network
📁 talos          # Talos OS node configurations
📁 templates      # Jinja2 templates (makejinja)
```

### Flux Workflow

This is a high-level look how Flux deploys my applications with dependencies. In most cases a `HelmRelease` will depend on other `HelmRelease`'s, in other cases a `Kustomization` will depend on other `Kustomization`'s, and in rare situations an app can depend on a `HelmRelease` and a `Kustomization`. The example below shows that `atuin` won't be deployed or upgrade until the `rook-ceph-cluster` Helm release is installed or in a healthy state.

```mermaid
graph TD
    A>Kustomization: rook-ceph] -->|Creates| B[HelmRelease: rook-ceph]
    A>Kustomization: rook-ceph] -->|Creates| C[HelmRelease: rook-ceph-cluster]
    C>HelmRelease: rook-ceph-cluster] -->|Depends on| B>HelmRelease: rook-ceph]
    D>Kustomization: atuin] -->|Creates| E(HelmRelease: atuin)
    E>HelmRelease: atuin] -->|Depends on| C>HelmRelease: rook-ceph-cluster]
```

### Networking

<details>
  <summary>Click here to see my high-level network diagram</summary>

  <img src="https://github.com/user-attachments/assets/01c2c51f-2ab1-4ae5-994c-2cd07c1301c4" align="center" width="600px" alt="network" />
</details>

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f636_200d_1f32b_fe0f/512.gif" alt="😶" width="20" height="20"> Cloud Dependencies

A few external services handle what doesn't make sense to self-host: secrets management, CI/CD, notifications, and the domain name.

| Service                                   | Use                                                            | Cost           |
|-------------------------------------------|----------------------------------------------------------------|----------------|
| [1Password](https://1password.com/)       | Secrets with [External Secrets](https://external-secrets.io/)  | ~€65/yr        |
| [GitHub](https://github.com/)             | Hosting this repository and continuous integration/deployments | Free           |
| [Pushover](https://pushover.net/)         | Kubernetes Alerts and application notifications                | €5 OTP         |
| Domain                                    | Public domain name                                             | €10.7/yr       |
|                                           |                                                                | Total: ~€6/mo |

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f30e/512.gif" alt="🌎" width="20" height="20"> DNS

In my cluster there are two instances of [ExternalDNS](https://github.com/kubernetes-sigs/external-dns) running. One for syncing private DNS records to my `OPNsense router` using [ExternalDNS webhook](https://github.com/kashalls/external-dns-unifi-webhook), while another instance syncs public DNS to `Cloudflare`. This setup is managed by creating ingresses with two specific classes: `internal` for private DNS and `external` for public DNS. The `external-dns` instances then syncs the DNS records to their respective platforms accordingly.

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/2699_fe0f/512.gif" alt="⚙" width="20" height="20"> Hardware

<details>
  <summary>Click here to see my server rack</summary>

  <img src="" align="center" width="250px" alt="rack" />
</details>

| Device                   | Num | OS Disk Size | Data Disk Size     | Ram  | OS            | Function              |
|--------------------------|-----|--------------|--------------------|------|---------------|-----------------------|
| Minisforum MS-01         | 3   | 256GB SSD    | 3x1TB (rook-ceph)  | 96GB | Talos         | Kubernetes            |
| NAS - N150 Motherboard   | 1   | 1TB SSD      | 4x4TB ZFS          | 16GB | TrueNAS SCALE | NFS + Backup Server   |
| JetKVM                   | 3   | -            | -                  | -    | -             | KVM for Kubernetes    |
| Lenovo m720q             | 1   | 256GB SSD    | -                  | -    | OPNsense      | Router                |
| Mikrotik CRS310-8G+2S+IN | 1   | -            | -                  | -    | -             | 2.5Gb  Switch         |
| EATON 3S 850             | 1   | -            | -                  | -    | -             | UPS                   |

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f31f/512.gif" alt="🌟" width="20" height="20"> Stargazers

<div align="center">

<a href="https://star-history.com/#thomloy/home-ops&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=thomloy/home-ops&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=thomloy/home-ops&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=thomloy/home-ops&type=Date" />
  </picture>
</a>

</div>

---

## <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f64f/512.gif" alt="🙏" width="20" height="20"> Gratitude and Thanks

Thanks to all the people who donate their time to the [Home Operations](https://discord.gg/home-operations) Discord community.
Be sure to check out [kubesearch.dev](https://kubesearch.dev/) for ideas on how to deploy applications or get ideas on what you could deploy.

---

<div align="center">

[![DeepWiki](https://img.shields.io/badge/deepwiki-purple?label=&logo=deepl&style=for-the-badge&logoColor=white)](https://deepwiki.com/thomloy/home-ops)

</div>
