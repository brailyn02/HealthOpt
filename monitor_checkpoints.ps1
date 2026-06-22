#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Pulls checkpoints + metrics from Lightning AI every N minutes.
    Uses scp only — no hanging SSH calls.

.USAGE
    powershell -ExecutionPolicy Bypass -File .\monitor_checkpoints.ps1
    powershell -ExecutionPolicy Bypass -File .\monitor_checkpoints.ps1 -IntervalMinutes 10
#>

param([int]$IntervalMinutes = 5)

$SSH_HOST = "lightning"
$REMOTE   = "/teamspace/studios/this_studio/dfinder/output/kge_rotate"
$PYKEEN   = "/teamspace/studios/this_studio/.data/pykeen/checkpoints"
$LOCAL    = "D:\23AIBox-DFinder\checkpoints_backup"
$INTERVAL = $IntervalMinutes * 60

New-Item -ItemType Directory -Force -Path $LOCAL | Out-Null

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DFinder Checkpoint Monitor  (every $IntervalMinutes min)"  -ForegroundColor Cyan
Write-Host "  Saving to: $LOCAL"
Write-Host "  Ctrl+C to stop"
Write-Host "============================================================"

$run = 0
while ($true) {
    $run++
    $stamp = Get-Date -Format "yyyyMMdd_HHmm"
    $ts    = Get-Date -Format "HH:mm:ss"
    Write-Host ""
    Write-Host "[$ts] Sync #$run" -ForegroundColor Yellow

    # 1. Periodic checkpoint
    scp -C -q "${SSH_HOST}:${REMOTE}/checkpoints/periodic.pt" "$LOCAL\periodic.pt" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $mb = [math]::Round((Get-Item "$LOCAL\periodic.pt").Length/1MB,1)
        Write-Host "  ✓ periodic.pt  ${mb} MB" -ForegroundColor Green
        Copy-Item "$LOCAL\periodic.pt" "$LOCAL\periodic_${stamp}.pt" -Force
    } else { Write-Host "  - periodic.pt  not ready" -ForegroundColor DarkGray }

    # 2. metrics.csv
    scp -C -q "${SSH_HOST}:${REMOTE}/metrics.csv" "$LOCAL\metrics.csv" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $kb = [math]::Round((Get-Item "$LOCAL\metrics.csv").Length/1KB,1)
        Write-Host "  ✓ metrics.csv  ${kb} KB" -ForegroundColor Green
        $mrr = Get-Content "$LOCAL\metrics.csv" | Where-Object { $_ -match "both.realistic.inverse_harmonic_mean_rank" } | Select-Object -Last 1
        if ($mrr) { $p = $mrr -split ","; Write-Host "    MRR: $($p[3].Trim())  (epoch $($p[1].Trim()))" -ForegroundColor Cyan }
    } else { Write-Host "  - metrics.csv  not ready" -ForegroundColor DarkGray }

    # 3. PyKEEN best model — copy to fixed path on remote first, then scp
    $cmd = "ls -t ${PYKEEN}/best-model-weights-*.pt 2>/dev/null | head -1 | xargs -r cp -t /teamspace/studios/this_studio/dfinder/output/kge_rotate/ 2>/dev/null; echo ok"
    $null = & ssh -o ConnectTimeout=10 -o BatchMode=yes $SSH_HOST $cmd 2>$null
    # find newest best-model-weights file in remote output dir
    scp -C -q "${SSH_HOST}:${REMOTE}/best-model-weights-*.pt" "$LOCAL\pykeen_best_model.pt" 2>$null
    if ($LASTEXITCODE -eq 0 -and (Get-Item "$LOCAL\pykeen_best_model.pt" -EA SilentlyContinue).Length -gt 0) {
        $mb = [math]::Round((Get-Item "$LOCAL\pykeen_best_model.pt").Length/1MB,1)
        Write-Host "  ✓ pykeen_best_model.pt  ${mb} MB" -ForegroundColor Green
        Copy-Item "$LOCAL\pykeen_best_model.pt" "$LOCAL\pykeen_best_${stamp}.pt" -Force
    } else { Write-Host "  - pykeen_best_model  not available yet" -ForegroundColor DarkGray }

    $count = (Get-ChildItem $LOCAL -Filter "*.pt").Count
    Write-Host "  Local .pt backups: $count  |  Next in $IntervalMinutes min"
    Write-Host "------------------------------------------------------------"
    Start-Sleep -Seconds $INTERVAL
}
