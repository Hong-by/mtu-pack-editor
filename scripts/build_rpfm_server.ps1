$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$RpfmRoot = Join-Path $Root "work\rpfm-master"
$CargoToml = Join-Path $RpfmRoot "Cargo.toml"
$ServerExe = Join-Path $RpfmRoot "target\debug\rpfm_server.exe"
$RustupHome = Join-Path $Root "work\rustup"
$CargoHome = Join-Path $Root "work\cargo"
$CargoExe = Join-Path $CargoHome "bin\cargo.exe"
$RustupExe = Join-Path $CargoHome "bin\rustup.exe"
$RustupInit = Join-Path $Root "work\tools\rustup-init.exe"

if (!(Test-Path -LiteralPath $CargoToml)) {
    throw "RPFM source not found: $RpfmRoot"
}

New-Item -ItemType Directory -Force -Path (Split-Path $RustupInit) | Out-Null
New-Item -ItemType Directory -Force -Path $RustupHome, $CargoHome | Out-Null

$env:RUSTUP_HOME = $RustupHome
$env:CARGO_HOME = $CargoHome
$env:PATH = "$CargoHome\bin;$env:PATH"

$VsDevCmd = Get-ChildItem `
    -Path "C:\Program Files\Microsoft Visual Studio", "C:\Program Files (x86)\Microsoft Visual Studio" `
    -Recurse `
    -Filter "VsDevCmd.bat" `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($VsDevCmd) {
    Write-Host "Loading Visual Studio build environment..."
    cmd /c "`"$($VsDevCmd.FullName)`" -no_logo && set" | ForEach-Object {
        if ($_ -match "^(.*?)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

if (!(Test-Path -LiteralPath $CargoExe)) {
    if (!(Test-Path -LiteralPath $RustupInit)) {
        Write-Host "Downloading rustup-init.exe..."
        Invoke-WebRequest -UseBasicParsing `
            -Uri "https://win.rustup.rs/x86_64" `
            -OutFile $RustupInit
    }

    Write-Host "Installing Rust toolchain into work\cargo and work\rustup..."
    & $RustupInit -y --no-modify-path --default-toolchain stable-x86_64-pc-windows-msvc
}

if (!(Test-Path -LiteralPath $CargoExe)) {
    throw "cargo.exe was not installed: $CargoExe"
}

if (!(Get-Command link.exe -ErrorAction SilentlyContinue)) {
    throw @"
MSVC linker not found: link.exe

Install "Visual Studio Build Tools" with the "Desktop development with C++" workload,
then run this script again:

  powershell -ExecutionPolicy Bypass -File scripts\build_rpfm_server.ps1
"@
}

Write-Host "Building rpfm_server..."
Push-Location $RpfmRoot
try {
    & $CargoExe build -p rpfm_server
}
finally {
    Pop-Location
}

if (!(Test-Path -LiteralPath $ServerExe)) {
    throw "Build finished but rpfm_server.exe was not found: $ServerExe"
}

Write-Host "RPFM server ready: $ServerExe"
