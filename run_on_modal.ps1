#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Upload data to Modal volume and/or run DFinder KGE training on Modal.com.

.PREREQUISITES
    pip install modal
    modal token new          # opens browser to authenticate (one-time)

.USAGE
    # First time — upload data + checkpoint, then launch:
    powershell -ExecutionPolicy Bypass -File .\run_on_modal.ps1

    # Upload only (re-run after editing train_kge.py):
    powershell -ExecutionPolicy Bypass -File .\run_on_modal.ps1 -UploadOnly

    # Run only (data already on volume):
    powershell -ExecutionPolicy Bypass -File .\run_on_modal.ps1 -RunOnly

    # Pull latest checkpoints + metrics from Modal volume:
    powershell -ExecutionPolicy Bypass -File .\run_on_modal.ps1 -Pull
#>
param(
    [switch]$UploadOnly,
    [switch]$RunOnly,
    [switch]$Pull
)

Set-StrictMode -Version Latest
Set-Location $PSScriptRoot

# ── Verify modal CLI is installed ─────────────────────────────────────────────
if (-not (Get-Command modal -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "ERROR: 'modal' CLI not found." -ForegroundColor Red
    Write-Host "Install it with:  pip install modal" -ForegroundColor Yellow
    Write-Host "Then auth with:   modal token new" -ForegroundColor Yellow
    exit 1
}

# ── Pull mode ─────────────────────────────────────────────────────────────────
if ($Pull) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Pulling checkpoints from Modal volume..."                   -ForegroundColor Cyan
    Write-Host "============================================================"
    modal run modal_train.py::pull
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Saved to: checkpoints_backup\" -ForegroundColor Green
        Get-ChildItem "checkpoints_backup\*modal*" -EA SilentlyContinue |
            Select-Object Name, @{N='MB';E={[math]::Round($_.Length/1MB,1)}}, LastWriteTime |
            Format-Table -AutoSize
    }
    exit $LASTEXITCODE
}

# ── Upload data + checkpoint to Modal volume ──────────────────────────────────
if (-not $RunOnly) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Uploading data to Modal volume 'dfinder-vol'..."            -ForegroundColor Cyan
    Write-Host "============================================================"
    Write-Host "  Files to upload:"
    Write-Host "    train_kge.py"
    Write-Host "    data\processed_hkg\kge_input\  (entity2id, relation2id, train/valid/test)"
    $ckp = "checkpoints_backup\periodic.pt"
    if (Test-Path $ckp) {
        $mb = [math]::Round((Get-Item $ckp).Length/1MB, 1)
        Write-Host "    $ckp  ($mb MB)  --> resume from epoch 50"
    } else {
        Write-Host "    (no periodic.pt found — will train from epoch 0)" -ForegroundColor DarkYellow
    }
    Write-Host ""

    modal run modal_train.py::upload
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Upload failed (exit $LASTEXITCODE). Check errors above." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host ""
    Write-Host "Upload complete." -ForegroundColor Green
}

# ── Launch training ───────────────────────────────────────────────────────────
if (-not $UploadOnly) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  Launching training on Modal A100-80GB..."                   -ForegroundColor Cyan
    Write-Host "============================================================"
    Write-Host "  Logs will stream here (Ctrl+C to detach — training keeps running)"
    Write-Host "  Pull checkpoints anytime in another terminal:"
    Write-Host "    powershell -ExecutionPolicy Bypass -File .\run_on_modal.ps1 -Pull"
    Write-Host ""

    modal run modal_train.py::main
    Write-Host ""
    Write-Host "Training job submitted and running detached on Modal servers." -ForegroundColor Green
    Write-Host "Ctrl+C will NOT stop training. Pull results anytime:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\run_on_modal.ps1 -Pull"
}
