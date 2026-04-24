// ============================================================================
// h264_encoder.cpp — H.264 via Windows Media Foundation (MFT)
//
// No third-party libs required. Works on Windows 8+ (client) and
// Windows Server 2012+ (server) as long as the H.264 MFT codec is installed
// (it is on all modern Windows SKUs).
//
// Data flow:
//   BGRA frame → BGRA→NV12 color convert → H.264 MFT → NAL units
// ============================================================================
#include "h264_encoder.hpp"
#include "../capture/screen_capture.hpp"
#include <spdlog/spdlog.h>

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mfapi.h>
#include <mftransform.h>
#include <mfidl.h>
#include <mferror.h>
#include <codecapi.h>
#include <wrl/client.h>

#pragma comment(lib, "mf.lib")
#pragma comment(lib, "mfplat.lib")
#pragma comment(lib, "mfuuid.lib")

using Microsoft::WRL::ComPtr;

namespace rdm {

// ── Colour conversion: BGRA → NV12 (planar) ──────────────────────────────────
// NV12: Y plane followed by interleaved UV plane (half height/width)
static void bgra_to_nv12(const uint8_t* bgra, int w, int h,
                          uint8_t* y_plane, uint8_t* uv_plane) {
    for (int row = 0; row < h; ++row) {
        const uint8_t* src = bgra + row * w * 4;
        uint8_t*       dst_y = y_plane + row * w;
        for (int col = 0; col < w; ++col) {
            uint8_t b = src[col * 4 + 0];
            uint8_t g = src[col * 4 + 1];
            uint8_t r = src[col * 4 + 2];
            // BT.709 luma
            dst_y[col] = static_cast<uint8_t>(
                16 + (65 * r + 129 * g + 25 * b) / 256);
        }
    }
    for (int row = 0; row < h / 2; ++row) {
        const uint8_t* src0 = bgra + (row * 2)     * w * 4;
        const uint8_t* src1 = bgra + (row * 2 + 1) * w * 4;
        uint8_t*       dst_uv = uv_plane + row * w;
        for (int col = 0; col < w / 2; ++col) {
            auto avg = [&](int ch) -> uint8_t {
                return static_cast<uint8_t>((
                    src0[col * 2 * 4 + ch] + src0[(col * 2 + 1) * 4 + ch] +
                    src1[col * 2 * 4 + ch] + src1[(col * 2 + 1) * 4 + ch]) / 4);
            };
            uint8_t b = avg(0), g = avg(1), r = avg(2);
            // BT.709 chroma
            dst_uv[col * 2 + 0] = static_cast<uint8_t>(
                128 + (-38 * r - 74 * g + 112 * b) / 256); // Cb
            dst_uv[col * 2 + 1] = static_cast<uint8_t>(
                128 + (112 * r - 94 * g - 18 * b) / 256);  // Cr
        }
    }
}

// ── MF H.264 encoder ─────────────────────────────────────────────────────────
class MFH264Encoder final : public H264Encoder {
public:
    MFH264Encoder() = default;
    ~MFH264Encoder() override { shutdown(); }

    bool init(const Options& opts) {
        opts_ = opts;
        if (FAILED(MFStartup(MF_VERSION, MFSTARTUP_NOSOCKET))) {
            spdlog::error("MFStartup failed");
            return false;
        }
        mf_started_ = true;

        // Find the H.264 encoder MFT
        MFT_REGISTER_TYPE_INFO out_type{};
        out_type.guidMajorType = MFMediaType_Video;
        out_type.guidSubtype   = MFVideoFormat_H264;

        IMFActivate** activates = nullptr;
        UINT32 count = 0;
        HRESULT hr = MFTEnumEx(MFT_CATEGORY_VIDEO_ENCODER,
                               MFT_ENUM_FLAG_HARDWARE | MFT_ENUM_FLAG_SYNCMFT,
                               nullptr, &out_type, &activates, &count);
        if (FAILED(hr) || count == 0) {
            // Fallback to software
            hr = MFTEnumEx(MFT_CATEGORY_VIDEO_ENCODER, MFT_ENUM_FLAG_SYNCMFT,
                           nullptr, &out_type, &activates, &count);
        }
        if (FAILED(hr) || count == 0) {
            spdlog::error("No H.264 MFT found");
            return false;
        }
        hr = activates[0]->ActivateObject(IID_PPV_ARGS(&mft_));
        for (UINT32 i = 0; i < count; ++i) activates[i]->Release();
        CoTaskMemFree(activates);
        if (FAILED(hr)) { spdlog::error("ActivateObject failed"); return false; }

        // Configure codec
        ComPtr<ICodecAPI> codec_api;
        if (SUCCEEDED(mft_.As(&codec_api))) {
            VARIANT v{};
            v.vt     = VT_UI4;
            v.ulVal  = opts_.bitrate_kbps * 1000;
            codec_api->SetValue(&CODECAPI_AVEncCommonMeanBitRate, &v);
            v.ulVal  = eAVEncCommonRateControlMode_CBR;
            codec_api->SetValue(&CODECAPI_AVEncCommonRateControlMode, &v);
        }

        // Output type: H.264
        ComPtr<IMFMediaType> out_mt;
        MFCreateMediaType(&out_mt);
        out_mt->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Video);
        out_mt->SetGUID(MF_MT_SUBTYPE, MFVideoFormat_H264);
        out_mt->SetUINT32(MF_MT_AVG_BITRATE, opts_.bitrate_kbps * 1000);
        MFSetAttributeSize(out_mt.Get(), MF_MT_FRAME_SIZE, opts_.width, opts_.height);
        MFSetAttributeRatio(out_mt.Get(), MF_MT_FRAME_RATE, opts_.fps, 1);
        out_mt->SetUINT32(MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive);
        out_mt->SetUINT32(MF_MT_MPEG2_PROFILE, eAVEncH264VProfile_Base);
        if (FAILED(mft_->SetOutputType(0, out_mt.Get(), 0))) {
            spdlog::error("SetOutputType failed"); return false;
        }

        // Input type: NV12
        ComPtr<IMFMediaType> in_mt;
        MFCreateMediaType(&in_mt);
        in_mt->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Video);
        in_mt->SetGUID(MF_MT_SUBTYPE, MFVideoFormat_NV12);
        MFSetAttributeSize(in_mt.Get(), MF_MT_FRAME_SIZE, opts_.width, opts_.height);
        MFSetAttributeRatio(in_mt.Get(), MF_MT_FRAME_RATE, opts_.fps, 1);
        in_mt->SetUINT32(MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive);
        if (FAILED(mft_->SetInputType(0, in_mt.Get(), 0))) {
            spdlog::error("SetInputType failed"); return false;
        }

        if (FAILED(mft_->ProcessMessage(MFT_MESSAGE_COMMAND_FLUSH, 0)) ||
            FAILED(mft_->ProcessMessage(MFT_MESSAGE_NOTIFY_BEGIN_STREAMING, 0)) ||
            FAILED(mft_->ProcessMessage(MFT_MESSAGE_NOTIFY_START_OF_STREAM, 0))) {
            spdlog::error("MFT stream start failed"); return false;
        }

        frame_idx_ = 0;
        nv12_buf_.resize(opts_.width * opts_.height * 3 / 2);
        spdlog::info("H264Encoder: Media Foundation ({}x{}@{}fps {}kbps)",
                     opts_.width, opts_.height, opts_.fps, opts_.bitrate_kbps);
        return true;
    }

    bool encode(const FrameBuffer& fb, const OutputCallback& cb) override {
        if (!mft_) return false;
        if (fb.width != opts_.width || fb.height != opts_.height) return false;

        // Color convert
        bgra_to_nv12(fb.pixels.data(), opts_.width, opts_.height,
                     nv12_buf_.data(),
                     nv12_buf_.data() + opts_.width * opts_.height);

        // Build input sample
        ComPtr<IMFSample>      sample;
        ComPtr<IMFMediaBuffer> buf;
        MFCreateMemoryBuffer(static_cast<DWORD>(nv12_buf_.size()), &buf);
        BYTE* raw = nullptr; DWORD max = 0;
        buf->Lock(&raw, &max, nullptr);
        memcpy(raw, nv12_buf_.data(), nv12_buf_.size());
        buf->Unlock();
        buf->SetCurrentLength(static_cast<DWORD>(nv12_buf_.size()));

        MFCreateSample(&sample);
        sample->AddBuffer(buf.Get());

        int64_t pts = frame_idx_ * (10'000'000 / opts_.fps); // 100-ns units
        sample->SetSampleTime(pts);
        sample->SetSampleDuration(10'000'000 / opts_.fps);
        if (force_keyframe_) {
            sample->SetUINT32(MFSampleExtension_CleanPoint, 1);
            force_keyframe_ = false;
        }
        ++frame_idx_;

        if (FAILED(mft_->ProcessInput(0, sample.Get(), 0))) return false;

        // Drain output
        return drain_output(cb, pts / 10'000 /* ms */);
    }

    void request_keyframe() override { force_keyframe_ = true; }

private:
    bool drain_output(const OutputCallback& cb, int64_t pts_ms) {
        MFT_OUTPUT_DATA_BUFFER out{};
        DWORD status = 0;
        while (true) {
            HRESULT hr = mft_->ProcessOutput(0, 1, &out, &status);
            if (hr == MF_E_TRANSFORM_NEED_MORE_INPUT) return true;
            if (FAILED(hr)) return false;

            ComPtr<IMFMediaBuffer> out_buf;
            out.pSample->ConvertToContiguousBuffer(&out_buf);
            BYTE* raw_out = nullptr; DWORD len = 0;
            out_buf->Lock(&raw_out, nullptr, &len);

            UINT32 clean_point = 0;
            out.pSample->GetUINT32(MFSampleExtension_CleanPoint, &clean_point);

            EncodedH264 enc;
            enc.data.assign(raw_out, raw_out + len);
            enc.is_keyframe = (clean_point != 0);
            enc.pts_ms      = pts_ms;
            cb(enc);

            out_buf->Unlock();
            if (out.pSample) out.pSample->Release();
        }
    }

    void shutdown() {
        if (mft_) {
            mft_->ProcessMessage(MFT_MESSAGE_NOTIFY_END_OF_STREAM, 0);
            mft_->ProcessMessage(MFT_MESSAGE_COMMAND_DRAIN, 0);
            mft_ = nullptr;
        }
        if (mf_started_) { MFShutdown(); mf_started_ = false; }
    }

    Options               opts_;
    ComPtr<IMFTransform>  mft_;
    bool                  mf_started_   = false;
    bool                  force_keyframe_ = true;
    int64_t               frame_idx_    = 0;
    std::vector<uint8_t>  nv12_buf_;
};

// ── factory ──────────────────────────────────────────────────────────────────
std::unique_ptr<H264Encoder> H264Encoder::create(const Options& opts) {
    auto enc = std::make_unique<MFH264Encoder>();
    if (!enc->init(opts)) {
        spdlog::warn("H264Encoder: MF init failed, H.264 unavailable");
        return nullptr;
    }
    return enc;
}

} // namespace rdm
