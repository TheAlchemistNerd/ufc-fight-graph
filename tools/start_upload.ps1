param([string]$StateFile = 'logs/crawl-run.json')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Create the project .venv before starting the uploader.' }
$logDirectory = Join-Path $root 'logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$arguments = @('-u', 'run_upload.py', '--watch-state', ('"{0}"' -f $StateFile))
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDirectory 'drive-upload.out.log') `
    -RedirectStandardError (Join-Path $logDirectory 'drive-upload.err.log')
Write-Output "Drive upload watcher PID: $($process.Id). Status: logs/crawl-run.upload.json"
