param(
    [Parameter(Mandatory = $true)][string]$FolderId,
    [string]$RemoteName = 'ufc-backups',
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'UFCFightGraph/rclone.conf')
)
$ErrorActionPreference = 'Stop'
$version = 'v1.75.2'
$install = Join-Path $env:LOCALAPPDATA "Programs/rclone/$version"
$executable = Join-Path $install 'rclone.exe'
if (!(Test-Path -LiteralPath $executable)) {
    $archiveName = "rclone-$version-windows-amd64.zip"
    $baseUrl = "https://downloads.rclone.org/$version"
    $download = Join-Path $env:TEMP $archiveName
    Invoke-WebRequest -Uri "$baseUrl/$archiveName" -OutFile $download
    $checksums = (Invoke-WebRequest -Uri "$baseUrl/SHA256SUMS").Content
    $expected = ($checksums -split "`n" | Where-Object { $_ -match "\s+$([regex]::Escape($archiveName))\s*$" }) -split '\s+'
    if (!$expected[0] -or (Get-FileHash -LiteralPath $download -Algorithm SHA256).Hash -ne $expected[0]) {
        throw 'Rclone download checksum mismatch'
    }
    New-Item -ItemType Directory -Path $install -Force | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($download)
    try {
        $entry = $zip.GetEntry("rclone-$version-windows-amd64/rclone.exe")
        [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $executable, $false)
    } finally { $zip.Dispose() }
}
New-Item -ItemType Directory -Path (Split-Path $ConfigPath) -Force | Out-Null
$existing = & $executable --config $ConfigPath listremotes
if ($existing -contains "$($RemoteName):") { throw "Remote $RemoteName already exists; choose a new name or reuse its configuration." }
# Suppress configuration output because it contains the OAuth refresh token.
& $executable --config $ConfigPath config create $RemoteName drive scope drive root_folder_id $FolderId --no-output
if ($LASTEXITCODE -ne 0) { throw 'Google Drive connection was not completed' }
Write-Output "Connected. Set UFC_DRIVE_REMOTE=$($RemoteName):, UFC_DRIVE_FOLDER_ID=$FolderId, RCLONE_EXE=$executable and RCLONE_CONFIG=$ConfigPath in .env."
