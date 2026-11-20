# POC12C offline Windows test package (synthetic data only).
# No Home Assistant address, token or robot interaction is used or requested.
# Steps: 1 prerequisites, 2 isolated environment, 3 regression suite,
#        4 Windows ACL verification, 5 GUI smoke test, 6 sanitized result archive.
# ASCII only (Windows PowerShell 5.1 reads BOM-less scripts as ANSI).

$ErrorActionPreference = 'Continue'
Set-StrictMode -Version 2.0

$SourceDir  = Split-Path -Parent $PSScriptRoot
$Stamp      = Get-Date -Format 'yyyyMMdd-HHmmss'
$WorkDir    = Join-Path $env:TEMP "scm-poc12c-$Stamp"
$Desktop    = [Environment]::GetFolderPath('Desktop')
$ResultDir  = Join-Path $Desktop "SCM-POC12C-testresultat-$Stamp"
$Steps      = New-Object System.Collections.ArrayList
$Overall    = 'PASS'

New-Item -ItemType Directory -Path $ResultDir -Force | Out-Null

function Write-Step([string]$Text) { Write-Host ''; Write-Host "=== $Text" -ForegroundColor Cyan }

function Add-Result([string]$Name, [string]$Status, $ExitCode, [string]$Detail) {
    [void]$Steps.Add([ordered]@{ step = $Name; status = $Status; exit_code = $ExitCode; detail = $Detail })
    if ($Status -ne 'PASS') { $script:Overall = 'FAIL' }
    $color = if ($Status -eq 'PASS') { 'Green' } else { 'Red' }
    Write-Host "$Name : $Status $Detail" -ForegroundColor $color
}

function ConvertTo-NativeArgument([string]$Value) {
    # Quote per CommandLineToArgvW rules so Python receives the argument unchanged.
    if ($Value -notmatch '[\s"]') { return $Value }
    $escaped = $Value -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

function Invoke-Logged([string]$Name, [string]$Exe, [string[]]$Arguments, [string]$WorkingDir) {
    # Runs a native command without a shell; stdout/stderr go to files in the result folder.
    $safe = ($Name -replace '[^A-Za-z0-9_-]', '_')
    $out = Join-Path $ResultDir "$safe.out.txt"
    $err = Join-Path $ResultDir "$safe.err.txt"
    $quoted = $Arguments | ForEach-Object { ConvertTo-NativeArgument $_ }
    try {
        $p = Start-Process -FilePath $Exe -ArgumentList $quoted -WorkingDirectory $WorkingDir -NoNewWindow -Wait -PassThru `
             -RedirectStandardOutput $out -RedirectStandardError $err
        $code = $p.ExitCode
    } catch {
        $_ | Out-File -FilePath $err -Append -Encoding utf8
        $code = -1
    }
    if ($null -eq $code) { $code = -1 }
    return $code
}

function Find-Python {
    foreach ($candidate in @(@('py', '-3.13'), @('py', '-3.12'), @('python'))) {
        $exe = $candidate[0]
        $pyArgs = @()
        if ($candidate.Count -gt 1) { $pyArgs += $candidate[1] }
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $path = & $exe @pyArgs -c "import sys; print(sys.executable if sys.version_info >= (3, 12) else '')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $path) { return ($path | Select-Object -Last 1).Trim() }
    }
    return $null
}

Start-Transcript -Path (Join-Path $ResultDir 'console-log.txt') | Out-Null
try {
    Write-Host 'SCM POC12C offline test package - synthetic data only, no Home Assistant connection.'
    Write-Host "Source:  $SourceDir"
    Write-Host "Results: $ResultDir"

    # 1. Prerequisites ------------------------------------------------------
    Write-Step '1/6 Prerequisites'
    $isWindows = [Environment]::OSVersion.Platform -eq 'Win32NT'
    $basePython = Find-Python
    $tools = @('icacls', 'whoami') | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) }
    if (-not $isWindows) { Add-Result 'prerequisites' 'FAIL' $null 'not running on Windows' }
    elseif (-not $basePython) { Add-Result 'prerequisites' 'FAIL' $null 'Python 3.12+ not found (install Python 3.13 from python.org incl. tcl/tk and the py launcher)' }
    elseif ($tools) { Add-Result 'prerequisites' 'FAIL' $null ("missing tools: " + ($tools -join ', ')) }
    else {
        $tkCode = Invoke-Logged 'prereq-tkinter' $basePython @('-c', 'import tkinter; r = tkinter.Tk(); r.destroy(); print(tkinter.TkVersion)') $SourceDir
        if ($tkCode -ne 0) { Add-Result 'prerequisites' 'FAIL' $tkCode 'tkinter unavailable (reinstall Python with tcl/tk)' }
        else { Add-Result 'prerequisites' 'PASS' 0 $basePython }
    }
    if ($Overall -ne 'PASS') { throw 'Prerequisites not met' }

    # 2. Isolated environment ---------------------------------------------------
    Write-Step '2/6 Isolated environment'
    New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
    $Code = Join-Path $WorkDir 'collector'
    New-Item -ItemType Directory -Path $Code -Force | Out-Null
    Get-ChildItem -Path $SourceDir -File | Where-Object { $_.Extension -in '.py', '.txt', '.md' } | Copy-Item -Destination $Code
    Copy-Item -Path (Join-Path $PSScriptRoot 'acl_evidence.py') -Destination $Code
    # Revision is taken from the extracted GitHub archive folder name when available.
    $env:SCM_COLLECTOR_REVISION = ''
    if ((Split-Path -Leaf (Split-Path -Parent (Split-Path -Parent $SourceDir))) -match '-([0-9a-f]{40})$') { $env:SCM_COLLECTOR_REVISION = $Matches[1] }
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    $venv = Join-Path $WorkDir 'venv'
    $c1 = Invoke-Logged 'env-venv' $basePython @('-m', 'venv', $venv) $WorkDir
    $py = Join-Path $venv 'Scripts\python.exe'
    $c2 = if ($c1 -eq 0) { Invoke-Logged 'env-pip-install' $py @('-m', 'pip', 'install', '--no-input', '-r', 'requirements.txt') $Code } else { -1 }
    $c3 = if ($c2 -eq 0) { Invoke-Logged 'env-pip-freeze' $py @('-m', 'pip', 'freeze') $Code } else { -1 }
    if ($c1 -eq 0 -and $c2 -eq 0 -and $c3 -eq 0) { Add-Result 'isolated-environment' 'PASS' 0 $WorkDir }
    else { Add-Result 'isolated-environment' 'FAIL' "$c1/$c2/$c3" 'venv or dependency installation failed (internet access to PyPI required)'; throw 'Environment failed' }
    $null = Invoke-Logged 'provenance' $py @('-c', 'import json, provenance; print(json.dumps(provenance.runtime_provenance(synthetic=True), indent=2))') $Code

    # 3. Regression suite -------------------------------------------------------
    Write-Step '3/6 Regression suite (synthetic)'
    $env:SCM_REQUIRE_WINDOWS_ACL = '1'
    $env:SCM_REQUIRE_GUI = '1'
    $c = Invoke-Logged 'regression-suite' $py @('-m', 'unittest', 'discover', '-v') $Code
    Add-Result 'regression-suite' $(if ($c -eq 0) { 'PASS' } else { 'FAIL' }) $c 'python -m unittest discover -v'

    # 4. Windows ACL verification ------------------------------------------------
    Write-Step '4/6 Windows storage permissions'
    $c = Invoke-Logged 'windows-acl-test' $py @('-m', 'unittest', '-v', 'test_storage.WindowsAclRealTests') $Code
    $c2 = Invoke-Logged 'windows-acl-evidence' $py @('acl_evidence.py') $Code
    Add-Result 'windows-acl' $(if ($c -eq 0 -and $c2 -eq 0) { 'PASS' } else { 'FAIL' }) "$c/$c2" 'current-user-only ACL, inheritance removed'

    # 5. GUI smoke test -----------------------------------------------------------
    Write-Step '5/6 GUI smoke test (a window opens and closes by itself - do not click)'
    $c = Invoke-Logged 'gui-smoke' $py @('-m', 'unittest', '-v', 'test_gui') $Code
    Add-Result 'gui-smoke' $(if ($c -eq 0) { 'PASS' } else { 'FAIL' }) $c 'synthetic capture and export via Tk window'
}
catch {
    Write-Host "Stopped: $($_.Exception.Message)" -ForegroundColor Red
    if ($Overall -eq 'PASS') { $Overall = 'FAIL' }
}
finally {
    # 6. Sanitized result archive -------------------------------------------------
    Write-Step '6/6 Result file'
    $summary = [ordered]@{
        package        = 'SCM POC12C offline Windows test package'
        overall        = $Overall
        started_local  = $Stamp
        os             = [Environment]::OSVersion.VersionString
        powershell     = $PSVersionTable.PSVersion.ToString()
        revision_hint  = $env:SCM_COLLECTOR_REVISION
        steps          = $Steps
        scope          = 'synthetic data only; no HA connection, token, address or robot interaction'
    }
    $summary | ConvertTo-Json -Depth 5 | Out-File -FilePath (Join-Path $ResultDir 'summary.json') -Encoding utf8
    try { Stop-Transcript | Out-Null } catch {}
    # Remove local identifiers before the archive is shared privately for review.
    $patterns = @()
    if ($env:USERPROFILE)  { $patterns += @{ from = [regex]::Escape($env:USERPROFILE); to = '<USERPROFILE>' } }
    if ($env:USERNAME)     { $patterns += @{ from = '(?i)\b' + [regex]::Escape($env:USERNAME) + '\b'; to = '<USER>' } }
    if ($env:COMPUTERNAME) { $patterns += @{ from = '(?i)\b' + [regex]::Escape($env:COMPUTERNAME) + '\b'; to = '<COMPUTER>' } }
    if ($env:USERDOMAIN)   { $patterns += @{ from = '(?i)\b' + [regex]::Escape($env:USERDOMAIN) + '\b'; to = '<DOMAIN>' } }
    $patterns += @{ from = 'S-1-5-21-[0-9-]+'; to = '<USER-SID>' }
    Get-ChildItem -Path $ResultDir -File | ForEach-Object {
        $text = [IO.File]::ReadAllText($_.FullName)
        foreach ($p in $patterns) { $text = [regex]::Replace($text, $p.from, $p.to) }
        [IO.File]::WriteAllText($_.FullName, $text, (New-Object System.Text.UTF8Encoding($false)))
    }
    $zip = "$ResultDir.zip"
    Compress-Archive -Path (Join-Path $ResultDir '*') -DestinationPath $zip -Force
    Write-Host ''
    Write-Host "OVERALL: $Overall" -ForegroundColor $(if ($Overall -eq 'PASS') { 'Green' } else { 'Red' })
    Write-Host "Result archive: $zip"
    Write-Host 'Upload this ZIP privately for review. Do not publish it.'
    if (Test-Path $WorkDir) { Remove-Item -Recurse -Force $WorkDir -ErrorAction SilentlyContinue }
}
