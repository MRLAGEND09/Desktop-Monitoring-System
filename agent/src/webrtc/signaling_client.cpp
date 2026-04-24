// ============================================================================
// signaling_client.cpp — Boost.Beast WebSocket client with exponential backoff
//
// Frame protocol (binary WebSocket message):
//   [4 bytes big-endian header length][JSON header][raw JPEG bytes]
//
// JSON header fields: { device_id, width, height, quality, ts_ms }
// ============================================================================
#include "signaling_client.hpp"
#include "../capture/screen_capture.hpp"
#include "../encoder/video_encoder.hpp"
#include <spdlog/spdlog.h>
#include <nlohmann/json.hpp>
#include <boost/beast/core.hpp>
#include <boost/beast/websocket.hpp>
#include <boost/beast/ssl.hpp>
#include <boost/asio.hpp>
#include <boost/asio/ssl.hpp>
#include <chrono>
#include <thread>
#include <algorithm>

namespace beast     = boost::beast;
namespace websocket = beast::websocket;
namespace net       = boost::asio;
namespace ssl       = net::ssl;
using tcp           = net::ip::tcp;

namespace rdm {

namespace {

// Parse "wss://host:port/path" into components
struct ParsedUrl {
    bool        is_wss = true;
    std::string host;
    std::string port;
    std::string path = "/";
};

ParsedUrl parse_ws_url(const std::string& url) {
    ParsedUrl p;
    std::string rest = url;
    if (rest.substr(0, 6) == "wss://") { p.is_wss = true; rest = rest.substr(6); }
    else if (rest.substr(0, 5) == "ws://") { p.is_wss = false; rest = rest.substr(5); }

    auto path_pos = rest.find('/');
    std::string authority = (path_pos != std::string::npos) ? rest.substr(0, path_pos) : rest;
    if (path_pos != std::string::npos) p.path = rest.substr(path_pos);

    auto colon = authority.rfind(':');
    if (colon != std::string::npos) {
        p.host = authority.substr(0, colon);
        p.port = authority.substr(colon + 1);
    } else {
        p.host = authority;
        p.port = p.is_wss ? "443" : "80";
    }
    return p;
}

// Build binary frame: [4-byte header len][JSON header][JPEG bytes]
std::vector<uint8_t> build_frame(const std::string& device_id,
                                  const EncodedFrame& frame) {
    nlohmann::json hdr;
    hdr["device_id"] = device_id;
    hdr["width"]     = frame.width;
    hdr["height"]    = frame.height;
    hdr["ts_ms"]     = std::chrono::duration_cast<std::chrono::milliseconds>(
                         std::chrono::system_clock::now().time_since_epoch()).count();

    std::string hdr_str = hdr.dump();
    uint32_t    hdr_len = static_cast<uint32_t>(hdr_str.size());

    std::vector<uint8_t> out;
    out.reserve(4 + hdr_len + frame.data.size());

    // Big-endian header length
    out.push_back((hdr_len >> 24) & 0xFF);
    out.push_back((hdr_len >> 16) & 0xFF);
    out.push_back((hdr_len >>  8) & 0xFF);
    out.push_back( hdr_len        & 0xFF);

    out.insert(out.end(), hdr_str.begin(), hdr_str.end());
    out.insert(out.end(), frame.data.begin(), frame.data.end());
    return out;
}

} // namespace

SignalingClient::SignalingClient(const Config& cfg, const Identity& id)
    : cfg_(cfg), identity_(id) {}

void SignalingClient::connect_with_backoff(std::atomic<bool>& running) {
    auto parsed = parse_ws_url(cfg_.signaling_url);

    auto capture  = ScreenCapture::create();
    JpegEncoder encoder_low(cfg_.quality_low);
    JpegEncoder encoder_high(cfg_.quality_high);

    uint32_t backoff_ms = 1000;
    const uint32_t max_backoff = 30000;

    while (running.load()) {
        try {
            net::io_context ioc;
            ssl::context ssl_ctx(ssl::context::tls_client);
            if (!cfg_.verify_tls) {
                ssl_ctx.set_verify_mode(ssl::verify_none);
            }

            // Resolve
            tcp::resolver resolver(ioc);
            auto endpoints = resolver.resolve(parsed.host, parsed.port);

            // Connect SSL stream
            beast::ssl_stream<tcp::socket> ssl_stream(ioc, ssl_ctx);
            SSL_set_tlsext_host_name(ssl_stream.native_handle(),
                                     parsed.host.c_str());
            net::connect(beast::get_lowest_layer(ssl_stream), endpoints);
            ssl_stream.handshake(ssl::stream_base::client);

            // Upgrade to WebSocket
            websocket::stream<beast::ssl_stream<tcp::socket>> ws(
                std::move(ssl_stream));
            ws.set_option(websocket::stream_base::decorator(
                [&](websocket::request_type& req) {
                    req.set(beast::http::field::authorization,
                            "Bearer " + cfg_.device_token);
                    req.set(beast::http::field::user_agent, "rdm-agent/1.0");
                }));
            ws.handshake(parsed.host, parsed.path);
            ws.binary(true);
            spdlog::info("Signaling connected to {}", cfg_.signaling_url);
            backoff_ms = 1000; // reset on success

            // Register device
            nlohmann::json reg;
            reg["type"]      = "device_register";
            reg["device_id"] = identity_.device_id();
            reg["token"]     = cfg_.device_token;
            reg["hostname"]  = identity_.hostname();
            ws.write(net::buffer(reg.dump()));

            // Main capture + stream loop
            FrameBuffer  fb;
            EncodedFrame ef;
            bool has_viewer = false;
            auto interval   = std::chrono::milliseconds(1000 / cfg_.fps_low);

            while (running.load()) {
                // Check for incoming signaling messages (non-blocking poll)
                if (ws.is_open()) {
                    ws.read_some(net::buffer(std::vector<uint8_t>(4096)));
                }

                // Capture + encode + send
                if (capture->capture(fb)) {
                    auto& enc = has_viewer ? encoder_high : encoder_low;
                    if (enc.encode(fb, ef)) {
                        auto frm = build_frame(identity_.device_id(), ef);
                        ws.write(net::buffer(frm));
                    }
                }

                std::this_thread::sleep_for(interval);
            }

            ws.close(websocket::close_code::normal);

        } catch (const std::exception& e) {
            spdlog::error("Signaling error: {} — retry in {}ms", e.what(), backoff_ms);
            std::this_thread::sleep_for(std::chrono::milliseconds(backoff_ms));
            backoff_ms = std::min(backoff_ms * 2, max_backoff);
        }
    }
}

} // namespace rdm
