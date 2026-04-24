; ============================================================================
; installer.nsi — NSIS installer for RDM Agent
;
; Produces:  RDMAgent-Setup-x64.exe
; Requires:  NSIS 3.x  (https://nsis.sourceforge.io)
;            NSIS plugin: nsProcess (for service management)
;
; Build:
;   makensis installer.nsi
;
; What it does:
;   1. Copies rdm-agent.exe + rdm-agent.toml.example to Program Files\RDMAgent
;   2. Creates C:\ProgramData\RDMAgent\  (config dir, writable by SYSTEM)
;   3. Creates rdm-agent.toml from the example if not already present
;   4. Installs as a Windows service (auto-start, restart-on-failure)
;   5. Adds an uninstaller and Control Panel entry
; ============================================================================

Unicode True
RequestExecutionLevel admin           ; require UAC elevation
SetCompressor     /SOLID lzma

!define PRODUCT_NAME      "RDM Agent"
!define PRODUCT_VERSION   "1.0.0"
!define PRODUCT_PUBLISHER "Your Company"
!define SERVICE_NAME      "RDMAgent"
!define SERVICE_DISPLAY   "RDM Remote Desktop Monitoring Agent"
!define SERVICE_DESC      "Streams screen and activity data to the RDM admin dashboard."
!define INSTALL_DIR       "$PROGRAMFILES64\RDMAgent"
!define CONFIG_DIR        "$COMMONAPPDATA\RDMAgent"
!define UNINSTALL_KEY     "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SERVICE_NAME}"

Name          "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile       "RDMAgent-Setup-x64.exe"
InstallDir    "${INSTALL_DIR}"

; ── Pages ─────────────────────────────────────────────────────────────────────
Page license
Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

LicenseData "LICENSE.txt"    ; create a LICENSE.txt next to this file

; ── Installer sections ────────────────────────────────────────────────────────
Section "RDM Agent (required)" SecMain
    SectionIn RO    ; cannot be deselected

    SetOutPath "${INSTALL_DIR}"
    File "build\Release\rdm-agent.exe"
    File "rdm-agent.toml.example"

    ; Create config directory (writable by SYSTEM service account)
    CreateDirectory "${CONFIG_DIR}"
    ; AccessControl plugin — give SYSTEM full control
    ; AccessControl::GrantOnFile "${CONFIG_DIR}" "(S-1-5-18)" "FullControl"

    ; Copy example config only if config does not already exist
    IfFileExists "${CONFIG_DIR}\rdm-agent.toml" config_exists 0
        CopyFiles "${INSTALL_DIR}\rdm-agent.toml.example" "${CONFIG_DIR}\rdm-agent.toml"
        MessageBox MB_OK "Config created at:$\n${CONFIG_DIR}\rdm-agent.toml$\n$\nEdit device_token before the service starts."
    config_exists:

    ; Install Windows service
    ExecWait 'sc.exe create "${SERVICE_NAME}" \
        binPath= "\"${INSTALL_DIR}\rdm-agent.exe\" --config \"${CONFIG_DIR}\rdm-agent.toml\"" \
        start= auto \
        DisplayName= "${SERVICE_DISPLAY}"' $0

    ExecWait 'sc.exe description "${SERVICE_NAME}" "${SERVICE_DESC}"'

    ; Restart on failure: after 5s, 10s, 30s
    ExecWait 'sc.exe failure "${SERVICE_NAME}" reset= 60 actions= restart/5000/restart/10000/restart/30000'

    ; Write uninstall registry keys
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayName"      "${PRODUCT_NAME}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "DisplayVersion"   "${PRODUCT_VERSION}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "Publisher"        "${PRODUCT_PUBLISHER}"
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "UninstallString"  '"${INSTALL_DIR}\uninstall.exe"'
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify"         1
    WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair"         1
    WriteRegStr   HKLM "${UNINSTALL_KEY}" "InstallLocation"  "${INSTALL_DIR}"

    WriteUninstaller "${INSTALL_DIR}\uninstall.exe"

    MessageBox MB_YESNO "Service installed.$\n$\nStart the RDM Agent service now?" IDNO done
        ExecWait 'sc.exe start "${SERVICE_NAME}"'
    done:
SectionEnd

; ── Uninstaller ───────────────────────────────────────────────────────────────
Section "Uninstall"
    ExecWait 'sc.exe stop   "${SERVICE_NAME}"'
    ExecWait 'sc.exe delete "${SERVICE_NAME}"'

    Delete "${INSTALL_DIR}\rdm-agent.exe"
    Delete "${INSTALL_DIR}\rdm-agent.toml.example"
    Delete "${INSTALL_DIR}\uninstall.exe"
    RMDir  "${INSTALL_DIR}"

    ; Leave config/data dir — contains logs and identity; user must remove manually
    MessageBox MB_OK "Uninstall complete.$\n$\nConfig and data in ${CONFIG_DIR} were NOT removed.$\nDelete that folder manually if no longer needed."

    DeleteRegKey HKLM "${UNINSTALL_KEY}"
SectionEnd
