// ============================================================================
// rdm-agent — main.cpp
// Entry point: loads config, registers device, starts capture + WebRTC loop.
// ============================================================================
#include <iostream>
#include <csignal>
#include <atomic>
#include <thread>
#include "config.hpp"
#include "identity.hpp"
#include "activity/activity_tracker.hpp"
#include "heartbeat/heartbeat.hpp"
#include "webrtc/signaling_client.hpp"
#include <spdlog/spdlog.h>
#include <spdlog/sinks/rotating_file_sink.h>
#include <spdlog/sinks/stdout_color_sinks.h>

static std::atomic<bool> g_running{true};

static void signal_handler(int sig) {
    spdlog::warn("Signal {} received — shutting down", sig);
    g_running.store(false);
}

namespace rdm {

int rdm_run() {
    // ── Setup logging ────────────────────────────────────────────────────────
    auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
    auto file_sink    = std::make_shared<spdlog::sinks::rotating_file_sink_mt>(
        "rdm-agent.log", 1024 * 1024 * 10, 3);
    auto logger = std::make_shared<spdlog::logger>(
        "rdm", spdlog::sinks_init_list{console_sink, file_sink});
    spdlog::set_default_logger(logger);
    spdlog::set_level(spdlog::level::info);
    spdlog::flush_on(spdlog::level::warn);

    spdlog::info("RDM Agent v{}.{}.{} starting", 1, 0, 0);

    // ── Load configuration ───────────────────────────────────────────────────
    rdm::Config cfg;
    try {
        cfg = rdm::Config::load("rdm-agent.toml");
    } catch (const std::exception& e) {
        spdlog::critical("Config load failed: {}", e.what());
        return 1;
    }

    // ── Stable device identity ───────────────────────────────────────────────
    rdm::Identity identity;
    try {
        identity = rdm::Identity::load_or_create(cfg.data_dir + "/identity.json");
        spdlog::info("Device ID: {}", identity.device_id());
    } catch (const std::exception& e) {
        spdlog::critical("Identity error: {}", e.what());
        return 1;
    }

    // ── Signal handlers ──────────────────────────────────────────────────────
    std::signal(SIGINT,  signal_handler);
    std::signal(SIGTERM, signal_handler);

    // ── Start activity tracker ───────────────────────────────────────────────
    rdm::ActivityTracker activity_tracker(cfg);
    activity_tracker.start();

    // ── Start heartbeat ──────────────────────────────────────────────────────
    rdm::Heartbeat heartbeat(cfg, identity, activity_tracker);
    heartbeat.start();

    // ── Start signaling / WebRTC loop ────────────────────────────────────────
    rdm::SignalingClient signaling(cfg, identity);
    signaling.connect_with_backoff(g_running);

    // ── Shutdown ─────────────────────────────────────────────────────────────
    heartbeat.stop();
    activity_tracker.stop();
    spdlog::info("RDM Agent stopped cleanly");
    return 0;
}

} // namespace rdm

int main(int argc, char* argv[]) {
    (void)argc;
    (void)argv;
    return rdm::rdm_run();
}
