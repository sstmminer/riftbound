param([switch]$Browser)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path '.venv\Scripts\python.exe')) {
        py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
    }
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if ($Browser) {
        & $python -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Optional dependency installation failed.' }
        & $python -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed.' }
        & $python scripts\sync.py --browser
    } else {
        & $python scripts\sync.py
    }
    $syncCode = $LASTEXITCODE
    if ($syncCode -ne 0) { Write-Warning "Sync returned $syncCode. Read data\errors.json; archive may be incomplete." }
    & $python scripts\audit_sources.py
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Source coverage audit could not recognize the current gallery structure.' }
    & $python scripts\validate.py
    if ($LASTEXITCODE -ne 0) { Write-Warning 'Archive validation found missing or invalid files. Read data\validation.json.' }
    & $python scripts\build_viewer.py
    if ($LASTEXITCODE -ne 0) { throw 'Viewer generation failed.' }
    & $python scripts\package.py
    if ($LASTEXITCODE -ne 0) { throw 'ZIP creation failed.' }
    exit $syncCode
} finally { Pop-Location }
