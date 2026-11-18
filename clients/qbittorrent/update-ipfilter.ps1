<#
.SYNOPSIS
  Updates qBittorrent IP filter and Enhanced Edition peer blacklist from rulesets.

.DESCRIPTION
  Downloads ipfilter.p2p and peer_blacklist.txt from the rulesets release branch,
  compares them with the local copies and replaces only changed files atomically.

  - ipfilter.p2p goes to -FilterPath; point qBittorrent at it once:
    Options -> Connection -> IP Filtering -> Filter path.
  - peer_blacklist.txt goes to the qBittorrent data folder; only qBittorrent
    Enhanced Edition reads it, plain qBittorrent ignores it.
  - peer_whitelist.txt is never created or touched: if it exists, Enhanced lets
    through ONLY the peers listed in it.

  qBittorrent reads peer_blacklist.txt only at startup, so a restart is needed
  after it changes. The script reports this but never kills qBittorrent.

.PARAMETER BaseUrl
  Base URL of the release branch.

.PARAMETER DataDir
  qBittorrent data folder. Defaults to %LOCALAPPDATA%\qBittorrent.

.PARAMETER FilterPath
  Where to store ipfilter.p2p. Defaults to <DataDir>\rulesets-ipfilter.p2p.

.PARAMETER SkipPeerBlacklist
  Do not download peer_blacklist.txt (plain qBittorrent).

.EXAMPLE
  .\update-ipfilter.ps1

.EXAMPLE
  # Daily scheduled task (run once in an elevated or normal PowerShell):
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\Tools\update-ipfilter.ps1"'
  Register-ScheduledTask -TaskName 'rulesets qBittorrent' -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At 4:20)

.NOTES
  Exit codes: 0 = up to date or updated, 1 = error, 2 = updated and restart required.
#>

[CmdletBinding()]
param(
  [string]$BaseUrl = 'https://raw.githubusercontent.com/Gesugao-san/rulesets/release/qbittorrent',
  [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'qBittorrent'),
  [string]$FilterPath,
  [switch]$SkipPeerBlacklist
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

<#
.SYNOPSIS
  Downloads a URL to a temp file and returns its path.
#>
function Get-RemoteFile {
  param([Parameter(Mandatory)][string]$Url)

  $temp = [System.IO.Path]::GetTempFileName()
  # Windows PowerShell 5.1 may default to TLS 1.0, which GitHub rejects.
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -Uri $Url -OutFile $temp -UseBasicParsing -TimeoutSec 60
  return $temp
}

<#
.SYNOPSIS
  Replaces Destination with the downloaded file if content differs.
.OUTPUTS
  $true if the file was replaced, $false if it was already up to date.
#>
function Update-LocalFile {
  param(
    [Parameter(Mandatory)][string]$Url,
    [Parameter(Mandatory)][string]$Destination
  )

  $temp = Get-RemoteFile -Url $Url
  try {
    if ((Get-Item $temp).Length -eq 0) { throw "Downloaded file is empty: $Url" }

    $isSame = (Test-Path $Destination) -and
      ((Get-FileHash $temp).Hash -eq (Get-FileHash $Destination).Hash)
    if ($isSame) {
      Write-Host "Up to date: $Destination"
      return $false
    }

    New-Item -ItemType Directory -Force -Path (Split-Path $Destination) | Out-Null
    # Move within one volume is atomic enough: qBittorrent never sees a half-written file.
    $staging = "$Destination.new"
    Copy-Item $temp $staging -Force
    Move-Item $staging $Destination -Force
    Write-Host "Updated:    $Destination"
    return $true
  }
  finally {
    Remove-Item $temp -Force -ErrorAction SilentlyContinue
  }
}

try {
  if (-not (Test-Path $DataDir)) { throw "qBittorrent data folder not found: $DataDir (use -DataDir)" }
  if (-not $FilterPath) { $FilterPath = Join-Path $DataDir 'rulesets-ipfilter.p2p' }

  $ipFilterChanged = Update-LocalFile -Url "$BaseUrl/ipfilter.p2p" -Destination $FilterPath

  $blacklistChanged = $false
  if (-not $SkipPeerBlacklist) {
    $blacklistChanged = Update-LocalFile -Url "$BaseUrl/peer_blacklist.txt" -Destination (Join-Path $DataDir 'peer_blacklist.txt')
  }

  if (Test-Path (Join-Path $DataDir 'peer_whitelist.txt')) {
    Write-Warning 'peer_whitelist.txt exists: Enhanced Edition allows ONLY peers listed in it.'
  }

  if (-not ($ipFilterChanged -or $blacklistChanged)) { exit 0 }

  Write-Host 'Restart qBittorrent to apply the changes.'
  exit 2
}
catch {
  Write-Error $_
  exit 1
}
