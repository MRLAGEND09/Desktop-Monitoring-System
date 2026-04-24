// ============================================================================
// identity.cpp — Load or generate stable device UUID, persist to JSON
// ============================================================================
#include "identity.hpp"
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <random>
#include <iomanip>
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>

#ifdef _WIN32
#  include <windows.h>
#endif

namespace rdm {

namespace {

// Generate RFC-4122 v4 UUID
std::string generate_uuid() {
    std::random_device rd;
    std::mt19937_64 gen(rd());
    std::uniform_int_distribution<uint32_t> dist;

    auto rand_hex = [&](int n) {
        std::ostringstream ss;
        for (int i = 0; i < n; ++i) {
            ss << std::hex << std::setw(1) << (dist(gen) & 0xF);
        }
        return ss.str();
    };

    // xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    std::ostringstream oss;
    oss << rand_hex(8) << '-'
        << rand_hex(4) << '-'
        << "4"         << rand_hex(3) << '-'
        << std::hex << ((dist(gen) & 0x3) | 0x8)  // variant bits
        << rand_hex(3) << '-'
        << rand_hex(12);
    return oss.str();
}

std::string get_hostname() {
#ifdef _WIN32
    char buf[MAX_COMPUTERNAME_LENGTH + 1];
    DWORD size = sizeof(buf);
    if (GetComputerNameA(buf, &size)) return std::string(buf);
#else
    char buf[256];
    if (gethostname(buf, sizeof(buf)) == 0) return std::string(buf);
#endif
    return "unknown";
}

} // namespace

Identity Identity::load_or_create(const std::string& path) {
    Identity id;
    id.hostname_ = get_hostname();

    // Try loading existing identity
    std::ifstream f(path);
    if (f.is_open()) {
        try {
            nlohmann::json j;
            f >> j;
            id.device_id_ = j.at("device_id").get<std::string>();
            spdlog::info("Loaded existing identity from {}", path);
            return id;
        } catch (...) {
            spdlog::warn("Identity file malformed — regenerating");
        }
    }

    // Generate new identity
    id.device_id_ = generate_uuid();
    spdlog::info("Generated new device ID: {}", id.device_id_);

    // Persist
    nlohmann::json j;
    j["device_id"] = id.device_id_;
    j["hostname"]  = id.hostname_;

    std::ofstream out(path);
    if (!out.is_open()) {
        throw std::runtime_error("Cannot write identity file: " + path);
    }
    out << j.dump(2) << '\n';
    return id;
}

} // namespace rdm
