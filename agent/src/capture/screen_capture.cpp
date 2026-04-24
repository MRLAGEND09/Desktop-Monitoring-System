// ============================================================================
// screen_capture.cpp — Windows DXGI Desktop Duplication implementation
// Falls back to GDI BitBlt when DXGI is unavailable (RDP sessions, etc.)
// ============================================================================
#include "screen_capture.hpp"
#include <spdlog/spdlog.h>
#include <stdexcept>

#ifdef _WIN32
#  include <windows.h>
#  include <dxgi1_2.h>
#  include <d3d11.h>
#  pragma comment(lib, "dxgi.lib")
#  pragma comment(lib, "d3d11.lib")

namespace rdm {

// ── DXGI Desktop Duplication ─────────────────────────────────────────────────
class DxgiCapture : public ScreenCapture {
public:
    DxgiCapture(int monitor_index) {
        HRESULT hr;

        // Create D3D11 device
        D3D_FEATURE_LEVEL feature_level;
        hr = D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr,
                               0, nullptr, 0, D3D11_SDK_VERSION,
                               &device_, &feature_level, &context_);
        if (FAILED(hr)) throw std::runtime_error("D3D11CreateDevice failed");

        // Get DXGI output for the requested monitor
        IDXGIDevice*  dxgi_device  = nullptr;
        IDXGIAdapter* dxgi_adapter = nullptr;
        IDXGIOutput*  dxgi_output  = nullptr;
        IDXGIOutput1* dxgi_output1 = nullptr;

        device_->QueryInterface(__uuidof(IDXGIDevice),  (void**)&dxgi_device);
        dxgi_device->GetParent(__uuidof(IDXGIAdapter),  (void**)&dxgi_adapter);
        dxgi_adapter->EnumOutputs(monitor_index,        &dxgi_output);
        dxgi_output->QueryInterface(__uuidof(IDXGIOutput1), (void**)&dxgi_output1);

        hr = dxgi_output1->DuplicateOutput(device_, &duplication_);
        dxgi_output1->Release(); dxgi_output->Release();
        dxgi_adapter->Release(); dxgi_device->Release();

        if (FAILED(hr)) throw std::runtime_error("DuplicateOutput failed");

        DXGI_OUTDUPL_DESC desc;
        duplication_->GetDesc(&desc);
        width_  = static_cast<int>(desc.ModeDesc.Width);
        height_ = static_cast<int>(desc.ModeDesc.Height);
        spdlog::info("DXGI capture: {}x{}", width_, height_);
    }

    ~DxgiCapture() override {
        if (staging_)     staging_->Release();
        if (duplication_) duplication_->Release();
        if (context_)     context_->Release();
        if (device_)      device_->Release();
    }

    bool capture(FrameBuffer& out) override {
        IDXGIResource*       resource  = nullptr;
        DXGI_OUTDUPL_FRAME_INFO info   = {};
        HRESULT hr = duplication_->AcquireNextFrame(50, &info, &resource);

        if (hr == DXGI_ERROR_WAIT_TIMEOUT) return false;  // no change
        if (hr == DXGI_ERROR_ACCESS_LOST) {
            spdlog::warn("DXGI access lost — reconnecting");
            return false;
        }
        if (FAILED(hr)) return false;

        // Get texture
        ID3D11Texture2D* tex = nullptr;
        resource->QueryInterface(__uuidof(ID3D11Texture2D), (void**)&tex);
        resource->Release();

        // Create/reuse staging texture for CPU readback
        if (!staging_) {
            D3D11_TEXTURE2D_DESC desc = {};
            tex->GetDesc(&desc);
            desc.Usage          = D3D11_USAGE_STAGING;
            desc.BindFlags      = 0;
            desc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
            desc.MiscFlags      = 0;
            device_->CreateTexture2D(&desc, nullptr, &staging_);
        }

        context_->CopyResource(staging_, tex);
        tex->Release();
        duplication_->ReleaseFrame();

        // Map for CPU access
        D3D11_MAPPED_SUBRESOURCE mapped = {};
        hr = context_->Map(staging_, 0, D3D11_MAP_READ, 0, &mapped);
        if (FAILED(hr)) return false;

        out.width  = width_;
        out.height = height_;
        out.stride = static_cast<int>(mapped.RowPitch);
        out.data.resize(static_cast<size_t>(height_) * out.stride);
        memcpy(out.data.data(), mapped.pData, out.data.size());
        context_->Unmap(staging_, 0);
        return true;
    }

private:
    ID3D11Device*          device_      = nullptr;
    ID3D11DeviceContext*   context_     = nullptr;
    IDXGIOutputDuplication* duplication_ = nullptr;
    ID3D11Texture2D*       staging_     = nullptr;
    int width_  = 0;
    int height_ = 0;
};

// ── GDI fallback ─────────────────────────────────────────────────────────────
class GdiCapture : public ScreenCapture {
public:
    GdiCapture() {
        width_  = GetSystemMetrics(SM_CXSCREEN);
        height_ = GetSystemMetrics(SM_CYSCREEN);
        spdlog::info("GDI capture fallback: {}x{}", width_, height_);
    }

    bool capture(FrameBuffer& out) override {
        HDC screen_dc = GetDC(nullptr);
        HDC mem_dc    = CreateCompatibleDC(screen_dc);
        HBITMAP bmp   = CreateCompatibleBitmap(screen_dc, width_, height_);
        HGDIOBJ old   = SelectObject(mem_dc, bmp);
        BitBlt(mem_dc, 0, 0, width_, height_, screen_dc, 0, 0, SRCCOPY | CAPTUREBLT);

        BITMAPINFOHEADER bi = {};
        bi.biSize        = sizeof(bi);
        bi.biWidth       = width_;
        bi.biHeight      = -height_;  // top-down
        bi.biPlanes      = 1;
        bi.biBitCount    = 32;
        bi.biCompression = BI_RGB;

        out.width  = width_;
        out.height = height_;
        out.stride = width_ * 4;
        out.data.resize(static_cast<size_t>(out.stride) * height_);
        GetDIBits(mem_dc, bmp, 0, height_, out.data.data(),
                  (BITMAPINFO*)&bi, DIB_RGB_COLORS);

        SelectObject(mem_dc, old);
        DeleteObject(bmp);
        DeleteDC(mem_dc);
        ReleaseDC(nullptr, screen_dc);
        return true;
    }

private:
    int width_  = 0;
    int height_ = 0;
};

// ── Factory ───────────────────────────────────────────────────────────────────
std::unique_ptr<ScreenCapture> ScreenCapture::create(int monitor_index) {
    try {
        return std::make_unique<DxgiCapture>(monitor_index);
    } catch (const std::exception& e) {
        spdlog::warn("DXGI unavailable ({}), falling back to GDI", e.what());
        return std::make_unique<GdiCapture>();
    }
}

} // namespace rdm

#else
// ── Linux / macOS stub ────────────────────────────────────────────────────────
namespace rdm {
std::unique_ptr<ScreenCapture> ScreenCapture::create(int) {
    throw std::runtime_error("ScreenCapture not implemented for this platform");
}
} // namespace rdm
#endif
