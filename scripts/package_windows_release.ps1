$ErrorActionPreference = "Stop"

param(
    [string]$PackageName = "MTU-Pack-Editor-windows-portable",
    [string]$OutDir = "dist",
    [string]$PythonRoot = "",
    [string]$RpfmServer = ""
)

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutPath = Join-Path $Root $OutDir
$Stage = Join-Path $OutPath $PackageName
$ZipPath = Join-Path $OutPath "$PackageName.zip"

if (Test-Path -LiteralPath $Stage) {
    Remove-Item -LiteralPath $Stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

$Items = @(
    "MTU Pack Editor.bat",
    "README.md",
    "docs",
    "examples",
    "scripts",
    "tests",
    "tk_pack_builder",
    "web"
)

foreach ($Item in $Items) {
    $Source = Join-Path $Root $Item
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination (Join-Path $Stage $Item) -Recurse -Force
    }
}

$RuntimePython = Join-Path $Stage "runtime\python"
New-Item -ItemType Directory -Force -Path $RuntimePython | Out-Null

if (!$PythonRoot) {
    $PythonRoot = Split-Path (Get-Command python).Source -Parent
}
if (!(Test-Path -LiteralPath (Join-Path $PythonRoot "python.exe"))) {
    throw "python.exe was not found in PythonRoot: $PythonRoot"
}
Copy-Item -Path (Join-Path $PythonRoot "*") -Destination $RuntimePython -Recurse -Force

$RpfmTarget = Join-Path $Stage "work\rpfm-dist"
New-Item -ItemType Directory -Force -Path $RpfmTarget | Out-Null

if (!$RpfmServer) {
    $Candidates = @(
        (Join-Path $Root "work\rpfm-dist\rpfm_server.exe"),
        (Join-Path $Root "work\rpfm-master\target\release\rpfm_server.exe"),
        (Join-Path $Root "work\rpfm-master\target\debug\rpfm_server.exe")
    )
    $RpfmServer = ($Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)
}
if (!$RpfmServer -or !(Test-Path -LiteralPath $RpfmServer)) {
    throw "rpfm_server.exe was not found. Pass -RpfmServer or build it first."
}
Copy-Item -LiteralPath $RpfmServer -Destination (Join-Path $RpfmTarget "rpfm_server.exe") -Force

$PackTarget = Join-Path $Stage "work\packs"
$PackRefsTarget = Join-Path $PackTarget "refs"
New-Item -ItemType Directory -Force -Path $PackRefsTarget | Out-Null
$PackReadme = Join-Path $Root "work\packs\README.txt"
$PackRefsReadme = Join-Path $Root "work\packs\refs\README.txt"
if (Test-Path -LiteralPath $PackReadme) {
    Copy-Item -LiteralPath $PackReadme -Destination (Join-Path $PackTarget "README.txt") -Force
}
if (Test-Path -LiteralPath $PackRefsReadme) {
    Copy-Item -LiteralPath $PackRefsReadme -Destination (Join-Path $PackRefsTarget "README.txt") -Force
}

Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $Stage -Recurse -File -Include "*.pyc", ".DS_Store" |
    Remove-Item -Force

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -LiteralPath $Stage -DestinationPath $ZipPath -CompressionLevel Optimal

Write-Host "Package ready: $ZipPath"
