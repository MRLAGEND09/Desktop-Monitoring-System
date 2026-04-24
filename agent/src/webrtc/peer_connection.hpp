// ============================================================================
// peer_connection.hpp — WebRTC peer connection (libwebrtc API surface)
//
// In production: link against libwebrtc.lib built from Chromium depot_tools.
// For a quicker start, use the pre-built binaries from:
//   https://github.com/webrtc-build/webrtc-build/releases
// ============================================================================
#pragma once
#include <string>
#include <functional>
#include <memory>
#include <vector>

namespace rdm {

struct IceCandidate {
    std::string sdp_mid;
    int         sdp_mline_index = 0;
    std::string candidate;
};

struct SessionDescription {
    std::string type;  // "offer" | "answer"
    std::string sdp;
};

// Callbacks fired on the signaling thread
struct PeerConnectionObserver {
    std::function<void(const SessionDescription&)> on_local_description;
    std::function<void(const IceCandidate&)>       on_ice_candidate;
    std::function<void(bool)>                      on_connected;  // true=connected
    std::function<void(const uint8_t*, size_t)>    on_data_channel_message;
};

// ── PeerConnection ────────────────────────────────────────────────────────────
// Wraps RTCPeerConnection. Screen frames are sent via a DataChannel
// (reliable=false, ordered=false) for lowest latency.
// Phase 2 upgrade path: replace DataChannel with a video MediaStreamTrack.
class PeerConnection {
public:
    struct Config {
        std::vector<std::string> stun_urls;
        std::string              turn_url;
        std::string              turn_user;
        std::string              turn_credential;
    };

    explicit PeerConnection(const Config& cfg, PeerConnectionObserver obs);
    ~PeerConnection();

    // Called by device when a viewer requests a stream
    void create_offer();

    // Called by device when viewer sends an answer
    void set_remote_description(const SessionDescription& sdp);

    // ICE candidate exchange
    void add_ice_candidate(const IceCandidate& candidate);

    // Send a JPEG frame over the DataChannel
    void send_frame(const uint8_t* data, size_t len);

    bool is_connected() const;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace rdm
