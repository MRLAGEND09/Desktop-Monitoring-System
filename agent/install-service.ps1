# Install / uninstall the RDM Agent Windows service using sc.exe
# Run as Administrator.

param(
    [Parameter(Mandatory)][ValidateSet("install","uninstall","start","stop")]
    [string]$Action,
    [string]$ExePath  = "$PSScriptRoot\rdm-agent.exe",
    [string]$ConfigDir = "$env:ProgramData\RDMAgent"
)

$ServiceName = "RDMAgent"
$DisplayName = "RDM Remote Desktop Monitoring Agent"
$Description = "Streams screen and activity data to the RDM admin dashboard."

switch ($Action) {
    "install" {
        if (-not (Test-Path $ExePath)) {
            Write-Error "Executable not found: $ExePath"
            exit 1
        }
        # Create config directory
        if (-not (Test-Path $ConfigDir)) {
            New-Item -ItemType Directory -Path $ConfigDir | Out-Null
        }
        # Copy example config if not present
        $ConfigFile = "$ConfigDir\rdm-agent.toml"
        if (-not (Test-Path $ConfigFile)) {
            Copy-Item "$PSScriptRoot\rdm-agent.toml.example" $ConfigFile
            Write-Warning "Config copied to $ConfigFile — edit device_token before starting!"
        }
        sc.exe create $ServiceName `
            binPath= "`"$ExePath`" --config `"$ConfigFile`"" `
            start= auto `
            DisplayName= $DisplayName
        sc.exe description $ServiceName $Description
        sc.exe failure $ServiceName reset= 60 actions= restart/5000/restart/10000/restart/30000
        Write-Host "Service '$ServiceName' installed. Edit $ConfigFile then run: .\install-service.ps1 -Action start"
    }
    "uninstall" {
        sc.exe stop    $ServiceName 2>$null
        sc.exe delete  $ServiceName
        Write-Host "Service '$ServiceName' removed."
    }
    "start" {
        sc.exe start $ServiceName
    }
    "stop" {
        sc.exe stop $ServiceName
    }
}
