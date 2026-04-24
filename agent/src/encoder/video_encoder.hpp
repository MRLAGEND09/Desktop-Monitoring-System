// ============================================================================
// video_encoder.hpp — JPEG encoder (libturbo-jpeg or stb_image_write)
//                     and H.264 encoder stub (via libx264 / WMF)
// ============================================================================
#pragma once
#include "../capture/screen_capture.hpp"
#include <vector>
#include <cstdint>

namespace rdm {

struct EncodedFrame {
    std::vector<uint8_t> data;
    uint32_t             width   = 0;
    uint32_t             height  = 0;
    bool                 is_key  = true;
};

// ── JPEG encoder ─────────────────────────────────────────────────────────────
class JpegEncoder {
public:
    // quality: 0-100
    explicit JpegEncoder(int quality = 75);
    bool encode(const FrameBuffer& frame, EncodedFrame& out);
    void set_quality(int q) { quality_ = q; }

private:
    int quality_;
};

} // namespace rdm
