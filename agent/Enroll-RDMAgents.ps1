# ============================================================================
# Enroll-RDMAgents.ps1 — Mass-enroll Windows PCs with the RDM Agent
#
# What it does per target machine:
#   1. Generates a unique device token via the RDM backend API (POST /auth/device-token)
#   2. Copies the installer (rdm-agent.exe + config) over the network
#   3. Writes a machine-specific rdm-agent.toml
#   4. Silently installs/updates the Windows service
#   5. Starts the service and verifies it is running
#
# Prerequisites:
#   - Run from an admin account with WinRM or file-share access to all target PCs
#   - PowerShell 5.1+ on controller  (targets need PS 3+)
#   - RDM backend API reachable from this machine
#   - $AdminToken must be a valid admin JWT (from POST /auth/login)
#
# Usage examples:
#   # From a CSV list of hostnames
#   .\Enroll-RDMAgents.ps1 -CsvPath .\pcs.csv -ApiUrl https://rdm.company.com/api -AdminToken eyJ...
#
#   # Enumerate AD OU
#   Get-ADComputer -Filter * -SearchBase "OU=Sales,DC=company,DC=local" |
#       Select-Object -ExpandProperty Name |
#       .\Enroll-RDMAgents.ps1 -ApiUrl https://rdm.company.com/api -AdminToken eyJ...
#
# CSV format (pcs.csv):
#   Hostname
#   PC-SALES-01
#   PC-SALES-02
#   ...
# ============================================================================
[CmdletBinding(SupportsShouldProcess)]
param(
    # Path to CSV with a "Hostname" column, or pipe hostnames directly
    [Parameter(ValueFromPipeline, ValueFromPipelineByPropertyName)]
    [string]$Hostname,

    [string]$CsvPath,

    [Parameter(Mandatory)]
    [string]$ApiUrl,           # e.g. https://rdm.company.com/api

    [Parameter(Mandatory)]
    [string]$AdminToken,       # admin JWT from POST /api/auth/login

    # Path to the built rdm-agent.exe on this machine
    [string]$AgentExePath = "$PSScriptRoot\build\Release\rdm-agent.exe",

    # Path to rdm-agent.toml.example
    [string]$ConfigTemplatePath = "$PSScriptRoot\rdm-agent.toml.example",

    # Signaling WSS URL written into each agent's config
    [string]$SignalingUrl = "",   # defaults to $ApiUrl with /api → /signaling

    # Max parallel jobs (keep ≤ 20 to avoid WinRM throttling)
    [int]$ThrottleLimit = 10,

    # Log results to this file
    [string]$LogPath = "$PSScriptRoot\enrollment-$(Get-Date -Format 'yyyyMMdd-HHmmss').csv"
)

begin {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = "Stop"

    # Validate inputs
    if (-not (Test-Path $AgentExePath)) {
        throw "Agent executable not found: $AgentExePath`nBuild the agent first with: build.bat Release"
    }
    if (-not (Test-Path $ConfigTemplatePath)) {
        throw "Config template not found: $ConfigTemplatePath"
    }

    # Derive signaling URL from API URL if not provided
    if (-not $SignalingUrl) {
        $SignalingUrl = $ApiUrl -replace "/api$", "/signaling" -replace "^http", "ws"
    }

    # Remove trailing slash
    $ApiUrl = $ApiUrl.TrimEnd("/")

    # Collect results
    $results = [System.Collections.Concurrent.ConcurrentBag[PSCustomObject]]::new()

    # Build the list of hostnames (from CSV or pipeline)
    $allHostnames = [System.Collections.Generic.List[string]]::new()

    if ($CsvPath) {
        Import-Csv -Path $CsvPath | ForEach-Object {
            $h = $_.Hostname?.Trim()
            if ($h) { $allHostnames.Add($h) }
        }
    }

    Write-Host "RDM Mass Enrollment" -ForegroundColor Cyan
    Write-Host "API:       $ApiUrl"
    Write-Host "Signaling: $SignalingUrl"
    Write-Host "Agent exe: $AgentExePath"
    Write-Host ""
}

process {
    if ($Hostname) { $allHostnames.Add($Hostname.Trim()) }
}

end {
    if ($allHostnames.Count -eq 0) {
        Write-Warning "No hostnames provided. Use -CsvPath or pipe hostnames."
        return
    }

    Write-Host "Enrolling $($allHostnames.Count) machines (throttle: $ThrottleLimit parallel)..."

    # ── Enroll each host in parallel ─────────────────────────────────────────
    $allHostnames | ForEach-Object -ThrottleLimit $ThrottleLimit -Parallel {
        $pc          = $_
        $apiUrl      = $using:ApiUrl
        $adminToken  = $using:AdminToken
        $sigUrl      = $using:SignalingUrl
        $exePath     = $using:AgentExePath
        $templatePath = $using:ConfigTemplatePath
        $results     = $using:results

        $status = "FAILED"
        $detail = ""

        try {
            # ── 1. Issue device token ─────────────────────────────────────────
            $body = @{ device_id = $pc; label = $pc } | ConvertTo-Json
            $headers = @{ Authorization = "Bearer $adminToken"; "Content-Type" = "application/json" }

            $resp = Invoke-RestMethod -Uri "$apiUrl/auth/device-token" `
                -Method Post -Body $body -Headers $headers -ErrorAction Stop
            $deviceToken = $resp.token
            if (-not $deviceToken) { throw "No token returned by API" }

            # ── 2. Prepare remote paths ───────────────────────────────────────
            $remoteBase   = "\\$pc\C$\ProgramData\RDMAgent"
            $remoteExeDir = "\\$pc\C$\Program Files\RDMAgent"

            foreach ($dir in $remoteBase, $remoteExeDir) {
                if (-not (Test-Path $dir)) {
                    New-Item -ItemType Directory -Path $dir -Force | Out-Null
                }
            }

            # ── 3. Copy agent binary ─────────────────────────────────────────
            Copy-Item -Path $exePath -Destination "$remoteExeDir\rdm-agent.exe" -Force

            # ── 4. Write machine-specific config ─────────────────────────────
            $configContent = Get-Content $templatePath -Raw
            $configContent = $configContent -replace 'signaling_url\s*=\s*"[^"]*"', "signaling_url = `"$sigUrl`""
            $configContent = $configContent -replace 'api_url\s*=\s*"[^"]*"',       "api_url       = `"$apiUrl`""
            $configContent = $configContent -replace 'device_token\s*=\s*"[^"]*"',  "device_token  = `"$deviceToken`""
            Set-Content -Path "$remoteBase\rdm-agent.toml" -Value $configContent -Force

            # ── 5. Install / update service ───────────────────────────────────
            $svcName  = "RDMAgent"
            $exeRemote = 'C:\Program Files\RDMAgent\rdm-agent.exe'
            $cfgRemote = 'C:\ProgramData\RDMAgent\rdm-agent.toml'
            $binPath   = "`"$exeRemote`" --config `"$cfgRemote`""

            Invoke-Command -ComputerName $pc -ScriptBlock {
                param($svcName, $binPath)
                $svc = Get-Service -Name $svcName -ErrorAction SilentlyContinue
                if ($svc) {
                    Stop-Service -Name $svcName -Force -ErrorAction SilentlyContinue
                    & sc.exe config $svcName binPath= $binPath start= auto | Out-Null
                } else {
                    & sc.exe create $svcName `
                        binPath= $binPath `
                        start= auto `
                        DisplayName= "RDM Remote Desktop Monitoring Agent" | Out-Null
                    & sc.exe description $svcName "Streams screen and activity data to the RDM admin dashboard." | Out-Null
                    & sc.exe failure $svcName reset= 60 actions= restart/5000/restart/10000/restart/30000 | Out-Null
                }
                Start-Service -Name $svcName
            } -ArgumentList $svcName, $binPath -ErrorAction Stop

            # ── 6. Verify ─────────────────────────────────────────────────────
            $svcStatus = Invoke-Command -ComputerName $pc -ScriptBlock {
                param($n) (Get-Service -Name $n).Status
            } -ArgumentList $svcName

            if ($svcStatus -ne "Running") { throw "Service status: $svcStatus" }

            $status = "OK"
            Write-Host "  OK   $pc" -ForegroundColor Green

        } catch {
            $detail = $_.Exception.Message
            Write-Host "  FAIL $pc — $detail" -ForegroundColor Red
        }

        $results.Add([PSCustomObject]@{
            Hostname  = $pc
            Status    = $status
            Detail    = $detail
            Timestamp = (Get-Date -Format "o")
        })
    }

    # ── Summary ───────────────────────────────────────────────────────────────
    $ok   = ($results | Where-Object Status -eq "OK").Count
    $fail = ($results | Where-Object Status -eq "FAILED").Count

    Write-Host ""
    Write-Host "Done: $ok succeeded, $fail failed." -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Yellow" })

    # Export CSV log
    $results | Sort-Object Hostname | Export-Csv -Path $LogPath -NoTypeInformation -Encoding UTF8
    Write-Host "Log saved: $LogPath"

    # Show failures for quick retry
    if ($fail -gt 0) {
        Write-Host "`nFailed machines:" -ForegroundColor Red
        $results | Where-Object Status -eq "FAILED" | ForEach-Object {
            Write-Host "  $($_.Hostname): $($_.Detail)" -ForegroundColor Red
        }
        Write-Host "`nRetry failed only:"
        Write-Host "  Import-Csv '$LogPath' | Where-Object Status -eq 'FAILED' | .\Enroll-RDMAgents.ps1 -ApiUrl $ApiUrl -AdminToken <token>"
    }
}
