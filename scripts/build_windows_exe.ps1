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
    $resolvedApp = [System.IO.Path]::GetFullPath($appDir)
    $resolvedDist = [System.IO.Path]::GetFullPath($distRoot).TrimEnd('\') + '\'
    if (-not $resolvedApp.StartsWith($resolvedDist, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a build directory outside dist: $resolvedApp"
    }
    Remove-Item -LiteralPath $appDir -Recurse -Force
}

& $Python -m PyInstaller `
    --noconfirm `
    --onedir `
    --name "MTU Pack Editor" `
    --console `
    --clean `
    --add-data "tk_pack_builder\data\assembly_kit_title_effects.ko.json;tk_pack_builder\data" `
    --add-data "tk_pack_builder\data\assembly_kit_skill_effects.ko.json;tk_pack_builder\data" `
    --add-data "tk_pack_builder\data\verified_ceo_registry.json;tk_pack_builder\data" `
    --add-data "tk_pack_builder\data\gathering_ko.loc.json;tk_pack_builder\data" `
    --add-data "tk_pack_builder\data\dedicated_armour_pools;tk_pack_builder\data\dedicated_armour_pools" `
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
$packSource = Join-Path $root "work\packs\my_hero.pack"
$coreReferenceSource = Join-Path $root "work\packs\refs\mtu_vanilla_reference.pack"
$packTarget = Join-Path $workDir "packs\my_hero.pack"
$coreReferenceTarget = Join-Path $workDir "packs\refs\mtu_vanilla_reference.pack"
$referencePackNames = @(
    "database.pack",
    "data_mh.pack",
    "data_ep.pack",
    "data_dlc07.pack",
    "data_dlc06.pack",
    "data_bl.pack",
    "data_yt_bl.pack"
)
$assetSource = Join-Path $root "work\assets"
$assetTarget = Join-Path $workDir "assets"
$internalMaterialsSource = Join-Path $root "work\internal_materials\vanilla_mtu"
$internalMaterialsTarget = Join-Path $workDir "internal_materials\vanilla_mtu"
$internalMaterialFiles = @(
    "materials.v015.json",
    "materials.v015.summary.json",
    "asset_manifest.v015.json",
    "assembly_kit_title_effects.ko.json",
    "assembly_kit_skill_effects.ko.json"
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
if (Test-Path $coreReferenceSource) {
    Copy-Item -LiteralPath $coreReferenceSource -Destination $coreReferenceTarget -Force
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
    foreach ($assetFolder in @("17309a40b912", "hby_generated_character_sets", "profile_190", "profile_korea")) {
        robocopy (Join-Path $assetSource $assetFolder) (Join-Path $assetTarget $assetFolder) /E | Out-Null
        if ($LASTEXITCODE -gt 7) {
            throw "Failed to copy portrait assets: $assetFolder"
        }
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
    $assetManifestTarget = Join-Path $internalMaterialsTarget "asset_manifest.v015.json"
    if (Test-Path $assetManifestTarget) {
        $sourceRootText = [System.IO.Path]::GetFullPath([string]$root).TrimEnd("\")
        function Convert-LocalBuildPath {
            param(
                [Parameter(ValueFromPipeline = $true)]
                [AllowNull()]
                [object]$Value,
                [string]$SourceRoot
            )

            if ($null -eq $Value) {
                return $null
            }
            if ($Value -is [string]) {
                $normalized = $Value.Replace("/", "\")
                if ($normalized.StartsWith($SourceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                    return $normalized.Substring($SourceRoot.Length).TrimStart("\")
                }
                return $Value
            }
            if ($Value -is [System.Management.Automation.PSCustomObject]) {
                foreach ($property in @($Value.PSObject.Properties)) {
                    $property.Value = Convert-LocalBuildPath -Value $property.Value -SourceRoot $SourceRoot
                }
                return $Value
            }
            if ($Value -is [System.Collections.IDictionary]) {
                foreach ($key in @($Value.Keys)) {
                    $Value[$key] = Convert-LocalBuildPath -Value $Value[$key] -SourceRoot $SourceRoot
                }
                return $Value
            }
            if ($Value -is [System.Collections.IEnumerable]) {
                return @($Value | ForEach-Object { Convert-LocalBuildPath -Value $_ -SourceRoot $SourceRoot })
            }
            return $Value
        }

        $manifest = Get-Content -LiteralPath $assetManifestTarget -Raw | ConvertFrom-Json
        $manifest = Convert-LocalBuildPath -Value $manifest -SourceRoot $sourceRootText
        $manifest | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $assetManifestTarget -Encoding UTF8
    }
}

foreach ($profile in @("190", "190-korea")) {
    $profileSource = Join-Path $root "work\internal_materials\$profile"
    $profileTarget = Join-Path $workDir "internal_materials\$profile"
    New-Item -ItemType Directory -Force -Path $profileTarget | Out-Null
    foreach ($name in @("materials.v015.json", "materials.v015.summary.json", "verified_ceo_registry.json", "assembly_kit_title_effects.ko.json", "audit.json")) {
        Copy-Item -LiteralPath (Join-Path $profileSource $name) -Destination (Join-Path $profileTarget $name) -Force
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

& $Python (Join-Path $root "scripts\stamp_windows_runtime_cache.py") --app-dir $appDir --source-root $root
if ($LASTEXITCODE -ne 0) {
    throw "Failed to stamp the packaged runtime cache."
}

New-Item -ItemType Directory -Force -Path (Join-Path $appDir "output") | Out-Null

$runtimeArtifacts = @(
    (Join-Path $workDir "pack_cache.sqlite3"),
    (Join-Path $workDir "api-build-error.log"),
    (Join-Path $workDir "server.err.log"),
    (Join-Path $workDir "server.out.log"),
    (Join-Path $workDir "rpfm-server.err.log"),
    (Join-Path $workDir "rpfm-server.out.log"),
    (Join-Path $workDir "rpfm-server.log")
)
foreach ($artifact in $runtimeArtifacts) {
    if (Test-Path -LiteralPath $artifact) {
        Remove-Item -LiteralPath $artifact -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Built: $exePath"
Write-Host "Run it by double-clicking MTU Pack Editor.exe."
