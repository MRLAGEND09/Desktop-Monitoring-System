# ============================================================================
# ops.ps1 — Operator helper for RDM administration tasks
#
# Prerequisites:
#   - curl (ships with Windows 10+) or PowerShell Invoke-RestMethod
#   - RDM backend must be reachable at $ApiUrl
#
# Usage:
#   .\ops.ps1 login              — get an admin JWT (saved to session)
#   .\ops.ps1 token <device-id>  — issue a device token
#   .\ops.ps1 devices            — list all registered devices
#   .\ops.ps1 enroll <csv>       — run full mass enrollment from a CSV
#   .\ops.ps1 alert <device-id> <severity> <message>  — create an alert
#   .\ops.ps1 users              — list all users
# ============================================================================
[CmdletBinding()]
param(
    [Parameter(Position=0, Mandatory)]
    [ValidateSet("login","token","devices","enroll","alert","users")]
    [string]$Command,

    [Parameter(Position=1)] [string]$Arg1,
    [Parameter(Position=2)] [string]$Arg2,
    [Parameter(Position=3)] [string]$Arg3,

    [string]$ApiUrl   = $env:RDM_API_URL,
    [string]$Username = $env:RDM_USERNAME,
    [string]$Password = $env:RDM_PASSWORD,
    [string]$Token    = $env:RDM_TOKEN
)

$ErrorActionPreference = "Stop"

if (-not $ApiUrl) {
    $ApiUrl = Read-Host "RDM API URL (e.g. https://rdm.company.com/api)"
}
$ApiUrl = $ApiUrl.TrimEnd("/")

function Get-AdminToken {
    if ($Token) { return $Token }

    $u = if ($Username) { $Username } else { Read-Host "Admin username" }
    $p = if ($Password) { $Password } else { Read-Host "Admin password" -AsSecureString | ConvertFrom-SecureString -AsPlainText }

    $body = @{ username = $u; password = $p } | ConvertTo-Json
    $resp = Invoke-RestMethod -Uri "$ApiUrl/auth/login" -Method Post `
        -Body $body -ContentType "application/json" -ErrorAction Stop
    $t = $resp.token
    Write-Host "Logged in as $($resp.user.username) (role: $($resp.user.role))" -ForegroundColor Green
    Write-Host "Export for reuse: `$env:RDM_TOKEN = '$t'"
    return $t
}

function Invoke-Api {
    param([string]$Method, [string]$Path, [object]$Body, [string]$AuthToken)
    $headers = @{ Authorization = "Bearer $AuthToken" }
    $params  = @{ Uri = "$ApiUrl$Path"; Method = $Method; Headers = $headers; ErrorAction = "Stop" }
    if ($Body) {
        $params.Body        = ($Body | ConvertTo-Json)
        $params.ContentType = "application/json"
    }
    return Invoke-RestMethod @params
}

switch ($Command) {

    "login" {
        $t = Get-AdminToken
        Write-Host "`nToken (set as environment variable to skip future login prompts):"
        Write-Host "`$env:RDM_TOKEN = '$t'"
    }

    "token" {
        if (-not $Arg1) { $Arg1 = Read-Host "Device ID (hostname)" }
        $t = Get-AdminToken
        $resp = Invoke-Api -Method Post -Path "/auth/device-token" `
            -Body @{ device_id = $Arg1; label = $Arg1 } -AuthToken $t
        Write-Host "Device token for '$Arg1':" -ForegroundColor Cyan
        Write-Host $resp.token
        Write-Host "`nPaste into C:\ProgramData\RDMAgent\rdm-agent.toml → device_token"
    }

    "devices" {
        $t = Get-AdminToken
        $devs = Invoke-Api -Method Get -Path "/devices" -AuthToken $t
        if ($devs.Count -eq 0) {
            Write-Host "No devices registered yet." -ForegroundColor Yellow
        } else {
            $devs | Format-Table id, name, status, last_seen, ip_address -AutoSize
        }
    }

    "enroll" {
        $csv = if ($Arg1) { $Arg1 } else { Read-Host "Path to CSV file" }
        if (-not (Test-Path $csv)) { Write-Error "CSV not found: $csv"; exit 1 }
        $t = Get-AdminToken
        & "$PSScriptRoot\Enroll-RDMAgents.ps1" -CsvPath $csv -ApiUrl $ApiUrl -AdminToken $t
    }

    "alert" {
        if (-not $Arg1) { $Arg1 = Read-Host "Device ID" }
        if (-not $Arg2) { $Arg2 = Read-Host "Severity (low/medium/high/critical)" }
        if (-not $Arg3) { $Arg3 = Read-Host "Message" }
        $t = Get-AdminToken
        $resp = Invoke-Api -Method Post -Path "/alerts" `
            -Body @{ device_id = $Arg1; severity = $Arg2; message = $Arg3 } -AuthToken $t
        Write-Host "Alert created (id: $($resp.id))" -ForegroundColor Green
    }

    "users" {
        $t = Get-AdminToken
        $users = Invoke-Api -Method Get -Path "/users" -AuthToken $t
        $users | Format-Table id, username, role, is_active, created_at -AutoSize
    }
}
