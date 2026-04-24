// ============================================================================
// config.hpp — Agent configuration (loaded from TOML + env overrides)
// ============================================================================
#pragma once
#include <string>
#include <cstdint>

namespace rdm {

struct Config {
    // Signaling server WebSocket URL
    std::string signaling_url   = "wss://localhost:4000";
    // Backend REST API base URL
    std::string api_url         = "https://localhost:8000";
    // Device JWT token (issued by admin via backend)
    std::string device_token;
    // Directory for persisted data (identity.json etc.)
    std::string data_dir        = ".";

    // Capture settings
    uint32_t    fps_low         = 2;    // grid view
    uint32_t    fps_high        = 15;   // focused view
    uint32_t    quality_low     = 30;   // JPEG quality 0-100
    uint32_t    quality_high    = 80;

    // Heartbeat interval seconds
    uint32_t    heartbeat_secs  = 30;

    // TLS
    bool        verify_tls      = true;

    static Config load(const std::string& path);
};

} // namespace rdm
