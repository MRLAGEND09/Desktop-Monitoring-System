// ============================================================================
// windows_service.cpp — Install / uninstall rdm-agent as a Windows service
// Build separately as rdm-agent-svc.exe; use sc.exe or this helper.
// ============================================================================
#include <windows.h>
#include <spdlog/spdlog.h>
#include <string>
#include <stdexcept>

namespace rdm {

static SERVICE_STATUS          g_svc_status   = {};
static SERVICE_STATUS_HANDLE   g_svc_handle   = nullptr;
static HANDLE                  g_stop_event   = nullptr;

void report_svc_status(DWORD state, DWORD exit_code, DWORD wait_hint) {
    static DWORD check_point = 1;
    g_svc_status.dwCurrentState  = state;
    g_svc_status.dwWin32ExitCode = exit_code;
    g_svc_status.dwWaitHint      = wait_hint;
    g_svc_status.dwCheckPoint    = (state == SERVICE_RUNNING ||
                                    state == SERVICE_STOPPED) ? 0 : check_point++;
    SetServiceStatus(g_svc_handle, &g_svc_status);
}

VOID WINAPI SvcCtrlHandler(DWORD ctrl) {
    if (ctrl == SERVICE_CONTROL_STOP || ctrl == SERVICE_CONTROL_SHUTDOWN) {
        report_svc_status(SERVICE_STOP_PENDING, NO_ERROR, 3000);
        SetEvent(g_stop_event);
    }
}

// Forward declaration — implemented in main.cpp
extern int rdm_run();

VOID WINAPI SvcMain(DWORD, LPTSTR*) {
    g_svc_handle = RegisterServiceCtrlHandlerA("RDMAgent", SvcCtrlHandler);
    if (!g_svc_handle) return;

    g_svc_status.dwServiceType             = SERVICE_WIN32_OWN_PROCESS;
    g_svc_status.dwServiceSpecificExitCode = 0;

    report_svc_status(SERVICE_START_PENDING, NO_ERROR, 3000);
    g_stop_event = CreateEvent(nullptr, TRUE, FALSE, nullptr);
    report_svc_status(SERVICE_RUNNING, NO_ERROR, 0);

    // Run agent in this thread — it will block until signalled
    rdm_run();

    report_svc_status(SERVICE_STOPPED, NO_ERROR, 0);
    CloseHandle(g_stop_event);
}

} // namespace rdm
