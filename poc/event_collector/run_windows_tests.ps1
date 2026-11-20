$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$log = Join-Path $PSScriptRoot ('windows-tests-' + (Get-Date -Format yyyyMMdd-HHmmss) + '.txt')
Start-Transcript -Path $log
try {
    py -3 -VV
    if ($LASTEXITCODE -ne 0) { throw 'Python 3 required' }
    py -3 -m venv .test-venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment failed' }
    $python = Join-Path $PSScriptRoot '.test-venv\Scripts\python.exe'
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & $python -m unittest discover -v
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed' }
    & $python -c "import tkinter as t; r=t.Tk(); r.update(); r.destroy(); print('Tk startup OK')"
    if ($LASTEXITCODE -ne 0) { throw 'Tk startup failed' }
    Write-Host 'Synthetic regression complete. Windows ACL acceptance requires separate verification.'
} finally { Stop-Transcript }
