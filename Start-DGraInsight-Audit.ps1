param(
    [string]$Config,
    [string]$Output = "dgrainsight_session_v2.json"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot

$BundledPython = Join-Path $ProjectRoot "artifacts\preflight\python39\python.exe"
if (Test-Path -LiteralPath $BundledPython -PathType Leaf) {
    $PythonCommand = $BundledPython
    $PythonPrefix = @()
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCommand = "python"
    $PythonPrefix = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCommand = "py"
    $PythonPrefix = @("-3")
} else {
    throw "Python was not found. Install a compatible PyTorch environment or include the bundled runtime."
}

if (-not $Config) {
    Write-Host "DGraInsight Local Audit" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "1. MTGNN / Exchange-Rate"
    Write-Host "2. DGraFormer / ETTh1"
    Write-Host "3. MSGNet / ETTh1"
    $Choice = Read-Host "Choose a supported model [1-3]"
    $Config = switch ($Choice) {
        "1" { "configs\local_audit_mtgnn_exchange.json" }
        "2" { "configs\local_audit_dgraformer_etth1.json" }
        "3" { "configs\local_audit_msgnet_etth1.json" }
        default { throw "Unsupported selection: $Choice" }
    }
}

$WizardArgs = @("-m", "dgraudit", "wizard", "--config", $Config, "--output", $Output)
$SourceRoot = Read-Host "Model source folder override (press Enter to use the config value)"
$Checkpoint = Read-Host "Checkpoint override (press Enter to use the config value)"
$Dataset = Read-Host "Dataset override (press Enter to use the config value)"
if ($SourceRoot) { $WizardArgs += @("--source-root", $SourceRoot) }
if ($Checkpoint) { $WizardArgs += @("--checkpoint", $Checkpoint) }
if ($Dataset) { $WizardArgs += @("--dataset", $Dataset) }

Write-Host ""
Write-Host "Starting the interactive graph and edge selection wizard..." -ForegroundColor Cyan
& $PythonCommand @PythonPrefix @WizardArgs
exit $LASTEXITCODE
