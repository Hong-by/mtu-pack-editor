param(
    [string]$Python = "python",
    [switch]$SkipPyInstallerInstall,
    [switch]$IncludeLegacyReferencePacks
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
$packSource = Join-Path $root "work\packs\refs\mtu_reference_core.pack"
if (-not (Test-Path $packSource)) {
    $packSource = Join-Path $root "work\packs\my_hero.pack"
}
$packTarget = Join-Path $workDir "packs\my_hero.pack"
$referencePackNames = @(
    "database.pack",
    "data_mh.pack",
    "data_ep.pack",
    "data_dlc07.pack",
    "data_dlc06.pack",
    "data_bl.pack",
    "data_yt_bl.pack",
    "BFG_Originals.pack",
    "BFG_for_MTU.pack",
    "BFG_Nanman2.pack",
    "BFG_Yellow_Turban.pack",
    "LSHZ_lbdc_lh.pack"
)
$assetSource = Join-Path $root "work\assets"
$assetTarget = Join-Path $workDir "assets"
$internalMaterialsSource = Join-Path $root "work\internal_materials"
$internalMaterialsTarget = Join-Path $workDir "internal_materials"
$internalMaterialFiles = @(
    "materials.v015.json",
    "asset_manifest.v015.json"
)
$schemaStoreSource = Join-Path $root "work\rpfm-schema-store"
$schemaStoreTarget = Join-Path $workDir "rpfm-schema-store"
robocopy (Join-Path $root "web") $webTarget /E | Out-Null
if ($LASTEXITCODE -gt 7) {
    throw "Failed to copy web assets. robocopy exit code: $LASTEXITCODE"
}
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $workDir "packs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $workDir "packs\refs") | Out-Null
if (Test-Path $snapshotSource) {
    Copy-Item -LiteralPath $snapshotSource -Destination $snapshotTarget -Force
}
if (Test-Path $packSource) {
    Copy-Item -LiteralPath $packSource -Destination $packTarget -Force
}
if ($IncludeLegacyReferencePacks) {
    foreach ($name in $referencePackNames) {
        $source = Join-Path $root "work\packs\refs\$name"
        $target = Join-Path $workDir "packs\refs\$name"
        if (Test-Path $source) {
            Copy-Item -LiteralPath $source -Destination $target -Force
        }
    }
}
if (Test-Path $assetSource) {
    robocopy $assetSource $assetTarget /E | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to copy extracted assets. robocopy exit code: $LASTEXITCODE"
    }
}

if (Test-Path $internalMaterialsSource) {
    New-Item -ItemType Directory -Force -Path $internalMaterialsTarget | Out-Null
    foreach ($name in $internalMaterialFiles) {
        $source = Join-Path $internalMaterialsSource $name
        $target = Join-Path $internalMaterialsTarget $name
        if (Test-Path $source) {
            Copy-Item -LiteralPath $source -Destination $target -Force
        }
    }
}

if (Test-Path $schemaStoreSource) {
    robocopy $schemaStoreSource $schemaStoreTarget /E | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "Failed to copy RPFM schema store. robocopy exit code: $LASTEXITCODE"
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
