// ============================================================================
// signaling_client.hpp — WebSocket client connecting to signaling server
// Sends JPEG frames; Phase 2 will negotiate full WebRTC SDP/ICE.
// ============================================================================
#pragma once
#include "../config.hpp"
#include "../identity.hpp"
#include <atomic>

namespace rdm {

class SignalingClient {
public:
    SignalingClient(const Config& cfg, const Identity& id);

    // Runs the WebSocket event loop with exponential back-off reconnect.
    // Blocks until running is false.
    void connect_with_backoff(std::atomic<bool>& running);

private:
    const Config&   cfg_;
    const Identity& identity_;
};

} // namespace rdm
