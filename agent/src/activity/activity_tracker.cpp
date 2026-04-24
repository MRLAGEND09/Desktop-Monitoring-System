// ============================================================================
// activity_tracker.cpp — Win32 GetForegroundWindow + GetLastInputInfo
// ============================================================================
#include "activity_tracker.hpp"
#include <spdlog/spdlog.h>
#include <algorithm>

#ifdef _WIN32
#  include <windows.h>
#  include <psapi.h>
#  pragma comment(lib, "psapi.lib")
#endif

namespace rdm {

// Work-related process names (lowercase)
static const char* WORK_APPS[] = {
    "chrome.exe", "firefox.exe", "msedge.exe",
    "outlook.exe", "teams.exe", "zoom.exe",
    "winword.exe", "excel.exe", "powerpnt.exe",
    "code.exe", "devenv.exe", "putty.exe",
    "wt.exe", "cmd.exe", "powershell.exe",
    nullptr
};

// Non-work / recreational processes
static const char* NONWORK_APPS[] = {
    "discord.exe", "steam.exe", "epicgameslauncher.exe",
    "spotify.exe", "vlc.exe", "netflix.exe",
    "youtube.exe",
    nullptr
};

ActivityTracker::ActivityTracker(const Config& cfg) : cfg_(cfg) {}

ActivityTracker::~ActivityTracker() { stop(); }

void ActivityTracker::start() {
    running_.store(true);
    thread_ = std::thread(&ActivityTracker::run, this);
}

void ActivityTracker::stop() {
    running_.store(false);
    if (thread_.joinable()) thread_.join();
}

ActivitySnapshot ActivityTracker::snapshot() const {
    std::lock_guard<std::mutex> lk(mutex_);
    return current_;
}

void ActivityTracker::run() {
    spdlog::info("Activity tracker started");
    while (running_.load()) {
        ActivitySnapshot snap;

#ifdef _WIN32
        // ── Active window ────────────────────────────────────────────────────
        HWND hwnd = GetForegroundWindow();
        if (hwnd) {
            char title[512] = {};
            GetWindowTextA(hwnd, title, sizeof(title));
            snap.active_window_title = title;

            DWORD pid = 0;
            GetWindowThreadProcessId(hwnd, &pid);
            HANDLE proc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
            if (proc) {
                char exe[MAX_PATH] = {};
                DWORD size = MAX_PATH;
                QueryFullProcessImageNameA(proc, 0, exe, &size);
                CloseHandle(proc);
                // Extract filename
                std::string full(exe);
                auto pos = full.find_last_of("\\/");
                snap.active_process_name = (pos != std::string::npos)
                    ? full.substr(pos + 1) : full;
            }
        }

        // ── Idle time ────────────────────────────────────────────────────────
        LASTINPUTINFO lii = { sizeof(LASTINPUTINFO) };
        if (GetLastInputInfo(&lii)) {
            DWORD idle_ms = GetTickCount() - lii.dwTime;
            snap.idle_seconds = idle_ms / 1000;
            snap.is_idle      = (snap.idle_seconds >= 300); // 5 min
        }
#endif

        snap.app_category = categorize(snap.active_process_name);

        {
            std::lock_guard<std::mutex> lk(mutex_);
            current_ = snap;
        }

        std::this_thread::sleep_for(std::chrono::seconds(10));
    }
}

std::string ActivityTracker::categorize(const std::string& process) {
    std::string p = process;
    std::transform(p.begin(), p.end(), p.begin(), ::tolower);

    for (int i = 0; WORK_APPS[i]; ++i)
        if (p == WORK_APPS[i]) return "work";
    for (int i = 0; NONWORK_APPS[i]; ++i)
        if (p == NONWORK_APPS[i]) return "non-work";
    return "unknown";
}

} // namespace rdm
