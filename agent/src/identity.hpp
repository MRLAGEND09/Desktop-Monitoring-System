// ============================================================================
// identity.hpp — Stable device identity (UUID persisted to disk)
// ============================================================================
#pragma once
#include <string>

namespace rdm {

class Identity {
public:
    static Identity load_or_create(const std::string& path);

    const std::string& device_id()  const { return device_id_;  }
    const std::string& hostname()   const { return hostname_;    }

private:
    std::string device_id_;
    std::string hostname_;
};

} // namespace rdm
