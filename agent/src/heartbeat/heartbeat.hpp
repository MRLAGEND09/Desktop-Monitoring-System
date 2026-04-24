// ============================================================================
// heartbeat.hpp — Periodic REST heartbeat to backend API
// ============================================================================
#pragma once
#include "../config.hpp"
#include "../identity.hpp"
#include "../activity/activity_tracker.hpp"
#include <thread>
#include <atomic>

namespace rdm {

class Heartbeat {
public:
    Heartbeat(const Config& cfg, const Identity& id, const ActivityTracker& at);
    ~Heartbeat();

    void start();
    void stop();

private:
    void run();
    bool post_heartbeat();
    bool post_log(const ActivitySnapshot& snap);

    const Config&          cfg_;
    const Identity&        identity_;
    const ActivityTracker& activity_;
    std::thread            thread_;
    std::atomic<bool>      running_{false};
};

} // namespace rdm
