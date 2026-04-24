// ============================================================================
// activity_tracker.hpp — Active window + idle time tracking (Win32)
// ============================================================================
#pragma once
#include "../config.hpp"
#include <string>
#include <atomic>
#include <thread>
#include <mutex>

namespace rdm {

struct ActivitySnapshot {
    std::string active_window_title;
    std::string active_process_name;
    std::string app_category;   // "work" | "non-work" | "unknown"
    uint32_t    idle_seconds = 0;
    bool        is_idle      = false;
};

class ActivityTracker {
public:
    explicit ActivityTracker(const Config& cfg);
    ~ActivityTracker();

    void start();
    void stop();

    ActivitySnapshot snapshot() const;

private:
    void run();
    static std::string categorize(const std::string& process);

    const Config&     cfg_;
    std::thread       thread_;
    std::atomic<bool> running_{false};
    mutable std::mutex mutex_;
    ActivitySnapshot  current_;
};

} // namespace rdm
