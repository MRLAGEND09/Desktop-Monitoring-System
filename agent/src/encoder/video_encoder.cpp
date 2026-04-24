// ============================================================================
// video_encoder.cpp — JPEG encoding using stb_image_write (header-only)
// For H.264 production use, replace with libx264 or Windows Media Foundation.
// ============================================================================
#include "video_encoder.hpp"
#include <spdlog/spdlog.h>
#include <cstring>

// stb_image_write — drop in third_party/include/stb_image_write.h
#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STB_IMAGE_WRITE_STATIC
#include "stb_image_write.h"

namespace rdm {

// Callback used by stb to accumulate output bytes
static void stb_write_callback(void* ctx, void* data, int size) {
    auto* vec = reinterpret_cast<std::vector<uint8_t>*>(ctx);
    const uint8_t* ptr = reinterpret_cast<const uint8_t*>(data);
    vec->insert(vec->end(), ptr, ptr + size);
}

JpegEncoder::JpegEncoder(int quality) : quality_(quality) {}

bool JpegEncoder::encode(const FrameBuffer& frame, EncodedFrame& out) {
    if (frame.data.empty() || frame.width <= 0 || frame.height <= 0) return false;

    // stb expects RGB; input is BGRA (Windows) — swap channels
    std::vector<uint8_t> rgb(static_cast<size_t>(frame.width) * frame.height * 3);
    const uint8_t* src = frame.data.data();
    uint8_t*       dst = rgb.data();

    for (int y = 0; y < frame.height; ++y) {
        const uint8_t* row = src + static_cast<size_t>(y) * frame.stride;
        for (int x = 0; x < frame.width; ++x) {
            dst[0] = row[2]; // R ← B
            dst[1] = row[1]; // G
            dst[2] = row[0]; // B ← R
            row += 4; dst += 3;
        }
    }

    out.data.clear();
    out.width  = static_cast<uint32_t>(frame.width);
    out.height = static_cast<uint32_t>(frame.height);

    int ok = stbi_write_jpg_to_func(stb_write_callback, &out.data,
                                    frame.width, frame.height, 3,
                                    rgb.data(), quality_);
    return ok != 0;
}

} // namespace rdm
