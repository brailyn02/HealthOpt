#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Sync HKG data to Lightning AI and start KGE training.

.DESCRIPTION
    1. Uploads kge_input/ and train_kge.py to your Lightning AI Studio
    2. Installs dependencies remotely
    3. Launches training (detached with nohup so it survives SSH disconnect)

.USAGE
    From D:\23AIBox-DFinder:
        .\run_on_lightning.ps1

    To only sync (no training):
        .\run_on_lightning.ps1 -SyncOnly

    To only run (data already uploaded):
        .\run_on_lightning.ps1 -RunOnly
#>

param(
    [switch]$SyncOnly,
    [switch]$RunOnly,
    [string]$RemoteDir = "/teamspace/studios/this_studio/dfinder"
)

$SSH_HOST    = "lightning"                  # matches your ~/.ssh/config Host alias
$LOCAL_DATA  = "data\processed_hkg\kge_input"
$LOCAL_TRAIN = "train_kge.py"
$LOCAL_REQ   = "requirements_kge.txt"

# ── Banner ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  DFinder — Lightning AI KGE Training Launcher" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  SSH host  : $SSH_HOST"
Write-Host "  Remote dir: $RemoteDir"
Write-Host ""

# ── 1. Create remote directory ────────────────────────────────────────────────
if (-not $RunOnly) {
    Write-Host "[1/3] Creating remote directory..." -ForegroundColor Yellow
    ssh $SSH_HOST "mkdir -p $RemoteDir/data/kge_input $RemoteDir/output"
    if ($LASTEXITCODE -ne 0) { Write-Error "SSH connection failed. Check your SSH key and Lightning Studio status."; exit 1 }
    Write-Host "  OK" -ForegroundColor Green
}

# ── 2. Sync files ─────────────────────────────────────────────────────────────
if (-not $RunOnly) {
    Write-Host ""
    Write-Host "[2/3] Uploading data and scripts to Lightning AI..." -ForegroundColor Yellow
    Write-Host "  (kge_input is ~65MB — may take a minute on first upload)"

    # Use scp to copy the kge_input directory
    scp -r "$LOCAL_DATA" "${SSH_HOST}:${RemoteDir}/data/"
    if ($LASTEXITCODE -ne 0) { Write-Error "SCP failed for data directory."; exit 1 }

    # Copy scripts
    scp "$LOCAL_TRAIN" "$LOCAL_REQ" "${SSH_HOST}:${RemoteDir}/"
    if ($LASTEXITCODE -ne 0) { Write-Error "SCP failed for scripts."; exit 1 }

    Write-Host "  Upload complete" -ForegroundColor Green

    if ($SyncOnly) {
        Write-Host ""
        Write-Host "Sync-only mode: done." -ForegroundColor Green
        Write-Host "To start training, SSH in and run:"
        Write-Host "  ssh $SSH_HOST"
        Write-Host "  cd $RemoteDir && conda run -n base python train_kge.py --data_dir data/kge_input"
        exit 0
    }
}

# ── 3. Install deps & launch training ────────────────────────────────────────
Write-Host ""
Write-Host "[3/3] Installing dependencies and launching training..." -ForegroundColor Yellow

# Write the remote commands to a local temp bash script, then scp + execute.
# This avoids PowerShell heredoc escaping issues with $!, backticks, etc.
$TMP_SCRIPT = [System.IO.Path]::GetTempFileName() + ".sh"
$SCRIPT_CONTENT = @'
#!/usr/bin/env bash
set -e
cd /teamspace/studios/this_studio/dfinder

VENV="/teamspace/studios/this_studio/dfinder/venv"
PYTHON="$VENV/bin/python"

echo "--- Setting up venv (via uv) ---"
if [ ! -f "$PYTHON" ]; then
    uv venv "$VENV"
fi

echo "--- Checking / installing PyTorch (CUDA 12.1) ---"
"$PYTHON" -c "import torch" 2>/dev/null || \
    uv pip install --python "$PYTHON" torch --index-url https://download.pytorch.org/whl/cu121

echo "--- Checking / installing PyKEEN ---"
"$PYTHON" -c "import pykeen" 2>/dev/null || \
    uv pip install --python "$PYTHON" -r requirements_kge.txt

echo "--- Versions & GPU check ---"
"$PYTHON" --version
"$PYTHON" -c "import torch; cuda=torch.cuda.is_available(); print('torch', torch.__version__, '| CUDA:', cuda, '| GPU:', torch.cuda.get_device_name(0) if cuda else 'NOT DETECTED - check machine type in Lightning AI dashboard!')"
"$PYTHON" -c "import pykeen.version; print('pykeen', pykeen.version.get_version())" 2>/dev/null || "$PYTHON" -c "import importlib.metadata; print('pykeen', importlib.metadata.version('pykeen'))"

mkdir -p output

echo "--- Starting training (nohup, detached) ---"
nohup "$PYTHON" train_kge.py \
    --data_dir data/kge_input \
    --output_dir output/kge_rotate \
    --model RotatE \
    --embedding_dim 512 \
    --num_epochs 500 \
    --batch_size 4096 \
    --lr 0.0001 \
    --num_negatives 128 \
    --adversarial_temp 1.0 \
    --margin 9.0 \
    --oversample_minority \
    --oversample_cap 50 \
    --eval_every 25 \
    --checkpoint_every 10 \
    --device cuda \
    > output/train.log 2>&1 &

TRAIN_PID=$!
echo ""
echo "Training launched! PID: $TRAIN_PID"
echo "$TRAIN_PID" > output/train.pid
echo ""
echo "NOTE: Interruptible (Spot) A100 — checkpoints every 10 epochs."
echo "If reclaimed, PyKEEN auto-resumes from last checkpoint on re-run."
echo ""
echo "Monitor: tail -f /teamspace/studios/this_studio/dfinder/output/train.log"
'@

# Save with Unix LF line endings (important for bash on Lightning AI)
[System.IO.File]::WriteAllText($TMP_SCRIPT, $SCRIPT_CONTENT.Replace("`r`n", "`n"))

# Upload and execute
scp $TMP_SCRIPT "${SSH_HOST}:/tmp/dfinder_launch.sh"
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to upload launch script."; exit 1 }

ssh $SSH_HOST "bash /tmp/dfinder_launch.sh"
if ($LASTEXITCODE -ne 0) { Write-Error "Remote command failed."; exit 1 }

Remove-Item $TMP_SCRIPT -Force

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "  Training is running on Lightning AI" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To monitor progress:"
Write-Host "  ssh $SSH_HOST 'tail -f $RemoteDir/output/train.log'"
Write-Host ""
Write-Host "To check if it's still running:"
Write-Host "  ssh $SSH_HOST 'ps aux | grep train_kge'"
Write-Host ""
Write-Host "To download results when done:"
Write-Host "  scp -r ${SSH_HOST}:${RemoteDir}/output .\output_from_lightning\"
Write-Host ""
