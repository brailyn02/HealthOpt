param(
  [string]$BundleName = "dfinder-deploy.tar.gz"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$bundlePath = Join-Path $root $BundleName

if (Test-Path $bundlePath) {
  Remove-Item $bundlePath -Force
}

Push-Location $root
try {
  tar -czf $BundleName `
    --exclude='.git' `
    --exclude='.github' `
    --exclude='.venv' `
    --exclude='venv' `
    --exclude='**/__pycache__' `
    --exclude='**/*.pyc' `
    --exclude='healthopt_frontend/node_modules' `
    --exclude='healthopt_frontend/dist' `
    --exclude='healthopt_frontend/healthopt.db' `
    --exclude='predict_called.log' `
    --exclude='*.log' `
    --exclude='dfinder-deploy.tar.gz' `
    --exclude='full database.xml' `
    --exclude='FoodData_Central_foundation_food_csv_2025-04-24' `
    --exclude='chembl_36_chemreps.txt' `
    --exclude='chembl_36_sqlite' `
    .
}
finally {
  Pop-Location
}

Write-Host "Created bundle: $bundlePath"
