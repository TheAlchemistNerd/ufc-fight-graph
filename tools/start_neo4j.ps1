param(
    [string]$Neo4jHome = (Join-Path $env:LOCALAPPDATA 'Programs/Neo4j/neo4j-community-5.26.32'),
    [string]$StateRoot = (Join-Path $env:LOCALAPPDATA 'UFCFightGraph/neo4j'),
    [switch]$Console
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $Neo4jHome 'bin/neo4j.bat'
$config = Join-Path $StateRoot 'conf/neo4j.conf'
if (!(Test-Path -LiteralPath $launcher)) { throw "Neo4j launcher missing: $launcher" }
if (!(Test-Path -LiteralPath $config)) { throw "Neo4j configuration missing: $config" }
$env:NEO4J_HOME = $Neo4jHome
$env:NEO4J_CONF = Join-Path $StateRoot 'conf'

if ($Console) {
    & $launcher console
    exit $LASTEXITCODE
}

$logDirectory = Join-Path $StateRoot 'logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$arguments = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $PSCommandPath),
    '-Neo4jHome', ('"{0}"' -f $Neo4jHome), '-StateRoot', ('"{0}"' -f $StateRoot), '-Console'
)
$process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDirectory 'console.out.log') `
    -RedirectStandardError (Join-Path $logDirectory 'console.err.log')
Write-Output "Neo4j launcher PID: $($process.Id). Logs: $logDirectory"
