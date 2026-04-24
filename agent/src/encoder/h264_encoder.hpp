// ============================================================================
// h264_encoder.hpp — H.264 encoder interface
//
// Default backend: Media Foundation (Windows 8+, no extra libs)
// Upgrade path:    Intel QSV / NVIDIA NVENC via ffmpeg / MSDK
// ============================================================================
#pragma once
#include <cstdint>
#include <vector>
#include <memory>
#include <functional>

namespace rdm {

struct FrameBuffer;  // defined in screen_capture.hpp

struct EncodedH264 {
    std::vector<uint8_t> data;
    bool                 is_keyframe = false;
    int64_t              pts_ms      = 0;
};

class H264Encoder {
public:
    struct Options {
        int   width       = 1920;
        int   height      = 1080;
        int   fps         = 15;
        int   bitrate_kbps = 2000;  // kbps
        int   keyframe_interval = 60; // frames
    };

    static std::unique_ptr<H264Encoder> create(const Options& opts);

    virtual ~H264Encoder() = default;

    // Encode one BGRA frame; calls callback with encoded NAL units
    using OutputCallback = std::function<void(const EncodedH264&)>;
    virtual bool encode(const FrameBuffer& frame, const OutputCallback& cb) = 0;

    // Force next frame to be a keyframe (IDR)
    virtual void request_keyframe() = 0;
};

} // namespace rdm
