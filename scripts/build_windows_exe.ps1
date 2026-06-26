param(
    [string]$Python = "python",
    [switch]$SkipPyInstallerInstall
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$distRoot = Join-Path $root "dist"
$appDir = Join-Path $distRoot "MTU Pack Editor"
$exePath = Join-Path $appDir "MTU Pack Editor.exe"

Set-Location $root

if (-not $SkipPyInstallerInstall) {
    & $Python -m pip show pyinstaller *> $null
    if ($LASTEXITCODE -ne 0) {
        & $Python -m pip install pyinstaller
    }
}

if (Test-Path $appDir) {
    Remove-Item -LiteralPath $appDir -Recurse -Force
}

& $Python -m PyInstaller `
    --noconfirm `
    --onedir `
    --name "MTU Pack Editor" `
    --console `
    --clean `
    "tk_pack_builder\launcher.py"

if (-not (Test-Path $exePath)) {
    throw "Executable was not created: $exePath"
}

$workDir = Join-Path $appDir "work"
$webTarget = Join-Path $appDir "web"
$rpfmSource = Join-Path $root "work\rpfm-dist"
$rpfmTarget = Join-Path $workDir "rpfm-dist"
$snapshotSource = Join-Path $root "work\reference_snapshot.json"
$snapshotTarget = Join-Path $workDir "reference_snapshot.json"
$internalDbSource = Join-Path $root "work\internal_dbs"
$internalDbTarget = Join-Path $workDir "internal_dbs"
$assetSource = Join-Path $root "work\assets"
$assetTarget = Join-Path $workDir "assets"
robocopy (Join-Path $root "web") $webTarget /E | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "Failed to copy web assets. robocopy exit code: $LASTEXITCODE"
}
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $workDir "packs") | Out-Null
if (Test-Path $snapshotSource) {
    Copy-Item -LiteralPath $snapshotSource -Destination $snapshotTarget -Force
}
if (Test-Path $internalDbSource) {
    robocopy $internalDbSource $internalDbTarget /E | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to copy internal DB files. robocopy exit code: $LASTEXITCODE"
    }
}
if (Test-Path $assetSource) {
    robocopy $assetSource $assetTarget /E | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to copy extracted assets. robocopy exit code: $LASTEXITCODE"
    }
}

if (Test-Path $rpfmSource) {
    robocopy $rpfmSource $rpfmTarget /E /XF *.pdb | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to copy RPFM runtime. robocopy exit code: $LASTEXITCODE"
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $appDir "output") | Out-Null

Write-Host ""
Write-Host "Built: $exePath"
Write-Host "Run it by double-clicking MTU Pack Editor.exe."
