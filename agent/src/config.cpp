// ============================================================================
// config.cpp — TOML config loader with ENV variable overrides
// ============================================================================
#include "config.hpp"
#include <fstream>
#include <stdexcept>
#include <sstream>
#include <cstdlib>
#include <spdlog/spdlog.h>

namespace rdm {

// Minimal TOML key=value parser (single-level only — no arrays/tables).
// For full TOML support, integrate toml++ or tomlplusplus via vcpkg.
static std::string get_env(const char* name, const std::string& fallback = "") {
    const char* v = std::getenv(name);
    return v ? std::string(v) : fallback;
}

Config Config::load(const std::string& path) {
    Config cfg;

    std::ifstream f(path);
    if (!f.is_open()) {
        spdlog::warn("Config file '{}' not found — using defaults + env vars", path);
    } else {
        std::string line;
        while (std::getline(f, line)) {
            // Strip comments and whitespace
            auto comment = line.find('#');
            if (comment != std::string::npos) line = line.substr(0, comment);
            if (line.empty()) continue;

            auto eq = line.find('=');
            if (eq == std::string::npos) continue;

            std::string key   = line.substr(0, eq);
            std::string value = line.substr(eq + 1);

            // Trim whitespace & quotes
            auto trim = [](std::string& s) {
                s.erase(0, s.find_first_not_of(" \t\r\n\"'"));
                s.erase(s.find_last_not_of(" \t\r\n\"'") + 1);
            };
            trim(key); trim(value);

            if (key == "signaling_url")   cfg.signaling_url   = value;
            else if (key == "api_url")    cfg.api_url         = value;
            else if (key == "device_token") cfg.device_token  = value;
            else if (key == "data_dir")   cfg.data_dir        = value;
            else if (key == "fps_low")    cfg.fps_low         = static_cast<uint32_t>(std::stoul(value));
            else if (key == "fps_high")   cfg.fps_high        = static_cast<uint32_t>(std::stoul(value));
            else if (key == "quality_low")  cfg.quality_low   = static_cast<uint32_t>(std::stoul(value));
            else if (key == "quality_high") cfg.quality_high  = static_cast<uint32_t>(std::stoul(value));
            else if (key == "heartbeat_secs") cfg.heartbeat_secs = static_cast<uint32_t>(std::stoul(value));
            else if (key == "verify_tls") cfg.verify_tls      = (value == "true" || value == "1");
        }
    }

    // ENV overrides (RDM_ prefix)
    auto env_s = [](const char* n, const std::string& d) { return get_env(n, d); };
    cfg.signaling_url  = env_s("RDM_SIGNALING_URL",  cfg.signaling_url);
    cfg.api_url        = env_s("RDM_API_URL",         cfg.api_url);
    cfg.device_token   = env_s("RDM_DEVICE_TOKEN",    cfg.device_token);
    cfg.data_dir       = env_s("RDM_DATA_DIR",        cfg.data_dir);

    if (cfg.device_token.empty()) {
        throw std::runtime_error("device_token is required (config or RDM_DEVICE_TOKEN env var)");
    }

    spdlog::info("Config loaded: signaling={} api={}", cfg.signaling_url, cfg.api_url);
    return cfg;
}

} // namespace rdm
