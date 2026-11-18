<#
.SYNOPSIS
    Demo controls for the contrats-flow integration (RabbitMQ).

.DESCRIPTION
    Starts and reverts each demo incident with one command, so nothing has
    to be typed live during an interview. Needs kubectl and a KUBECONFIG
    that points at the cluster. Works with Windows PowerShell 5.1 and 7.

    These changes are made with kubectl for the demo only: Flux does not
    revert them, so run "reset" afterwards. Lasting changes go through Git.

.EXAMPLE
    .\docs\runbooks\integration-demo.ps1 check       # cluster access, pods, queues
    .\docs\runbooks\integration-demo.ps1 panne       # stop the central system
    .\docs\runbooks\integration-demo.ps1 reprise     # restart it, the backlog drains
    .\docs\runbooks\integration-demo.ps1 qualite     # 30 % defective contracts
    .\docs\runbooks\integration-demo.ps1 illisibles  # 5 % unreadable messages
    .\docs\runbooks\integration-demo.ps1 files       # queue depths only
    .\docs\runbooks\integration-demo.ps1 reset       # back to normal

.NOTES
    If Windows refuses to run scripts, allow local scripts once with:
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('check', 'files', 'panne', 'reprise', 'qualite', 'illisibles', 'reset')]
    [string]$Action = 'check'
)

$ErrorActionPreference = 'Stop'

$Namespace = 'integration'
$Producer  = 'deploy/contrats-flow-producteur'
$Central   = 'deploy/contrats-flow-si-central'
$Broker    = 'deploy/rabbitmq'
$Defaults  = @{ PRODUCER_ERROR_RATIO = '0.08'; PRODUCER_POISON_RATIO = '0.005' }

function Invoke-Kubectl {
    & kubectl --namespace $Namespace @args
    if ($LASTEXITCODE -ne 0) {
        throw "kubectl $($args -join ' ') a echoue (code $LASTEXITCODE)"
    }
}

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host $Message -ForegroundColor Cyan
}

function Show-Queues {
    Write-Step 'Files RabbitMQ'
    Invoke-Kubectl exec $Broker '--' rabbitmqctl --quiet list_queues --formatter pretty_table `
        name messages_ready messages_unacknowledged consumers
}

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw 'kubectl introuvable. Installe-le avec : winget install -e --id Kubernetes.kubectl'
}
if (-not $env:KUBECONFIG -and -not (Test-Path (Join-Path $HOME '.kube\config'))) {
    Write-Warning 'Aucun kubeconfig trouve. Exemple : $env:KUBECONFIG = "C:\chemin\vers\kubeconfig"'
}

switch ($Action) {
    'check' {
        Write-Step 'Pods du namespace integration'
        Invoke-Kubectl get pods
        Show-Queues
    }
    'files' {
        Show-Queues
    }
    'panne' {
        Write-Step 'Panne simulee : arret du SI central'
        Invoke-Kubectl scale $Central --replicas=0
        Write-Host 'La file contrats.valides va grossir : montre-la dans l interface RabbitMQ.'
        Start-Sleep -Seconds 15
        Show-Queues
    }
    'reprise' {
        Write-Step 'Reprise : redemarrage du SI central (30 a 60 s)'
        Invoke-Kubectl scale $Central --replicas=1
        Invoke-Kubectl rollout status $Central --timeout=180s
        Write-Host 'La file contrats.valides se vide, aucun message perdu.'
        Start-Sleep -Seconds 10
        Show-Queues
    }
    'qualite' {
        Write-Step 'Incident qualite de donnees : 30 % de contrats defectueux'
        Invoke-Kubectl set env $Producer PRODUCER_ERROR_RATIO=0.3
        Write-Host 'Le pic apparait dans Grafana dans 1 a 2 minutes. L alerte part au bout de 10 minutes.'
    }
    'illisibles' {
        Write-Step 'Incident messages illisibles : 5 % de messages corrompus'
        Invoke-Kubectl set env $Producer PRODUCER_POISON_RATIO=0.05
        Write-Host 'Les messages arrivent dans contrats.rejets avec la cle rejet.illisible.'
    }
    'reset' {
        Write-Step 'Retour a la normale'
        Invoke-Kubectl set env $Producer "PRODUCER_ERROR_RATIO=$($Defaults.PRODUCER_ERROR_RATIO)" `
            "PRODUCER_POISON_RATIO=$($Defaults.PRODUCER_POISON_RATIO)"
        Invoke-Kubectl scale $Central --replicas=1
        Invoke-Kubectl rollout status $Producer --timeout=180s
        Invoke-Kubectl rollout status $Central --timeout=180s
        Show-Queues
    }
}
