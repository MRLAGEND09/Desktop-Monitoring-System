// ============================================================================
// screen_capture.hpp — Cross-platform screen capture interface
// Windows: DXGI Desktop Duplication API (GPU-accelerated)
// ============================================================================
#pragma once
#include <vector>
#include <cstdint>
#include <memory>

namespace rdm {

struct FrameBuffer {
    std::vector<uint8_t> data;  // BGRA pixels
    int width   = 0;
    int height  = 0;
    int stride  = 0;            // bytes per row
};

class ScreenCapture {
public:
    virtual ~ScreenCapture() = default;

    // Capture current frame. Returns false if device lost / no change.
    virtual bool capture(FrameBuffer& out) = 0;

    // Factory — selects best backend for current OS
    static std::unique_ptr<ScreenCapture> create(int monitor_index = 0);
};

} // namespace rdm
