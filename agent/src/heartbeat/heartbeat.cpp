// ============================================================================
// heartbeat.cpp — PATCH /devices/:id/heartbeat + POST /logs via libcurl
// ============================================================================
#include "heartbeat.hpp"
#include <spdlog/spdlog.h>
#include <nlohmann/json.hpp>
#include <curl/curl.h>
#include <chrono>

namespace rdm {

namespace {

size_t curl_discard(void*, size_t size, size_t nmemb, void*) {
    return size * nmemb; // discard response body
}

bool http_patch(const std::string& url, const std::string& token,
                const std::string& body) {
    CURL* curl = curl_easy_init();
    if (!curl) return false;

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    headers = curl_slist_append(headers,
        ("Authorization: Bearer " + token).c_str());

    curl_easy_setopt(curl, CURLOPT_URL,            url.c_str());
    curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST,  "PATCH");
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS,     body.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER,     headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION,  curl_discard);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT,        10L);

    CURLcode res = curl_easy_perform(curl);
    long status  = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return (res == CURLE_OK && status >= 200 && status < 300);
}

bool http_post(const std::string& url, const std::string& token,
               const std::string& body) {
    CURL* curl = curl_easy_init();
    if (!curl) return false;

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    headers = curl_slist_append(headers,
        ("Authorization: Bearer " + token).c_str());

    curl_easy_setopt(curl, CURLOPT_URL,           url.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS,    body.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER,    headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_discard);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT,       10L);

    CURLcode res = curl_easy_perform(curl);
    long status  = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &status);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return (res == CURLE_OK && status >= 200 && status < 300);
}

} // namespace

Heartbeat::Heartbeat(const Config& cfg, const Identity& id,
                     const ActivityTracker& at)
    : cfg_(cfg), identity_(id), activity_(at) {}

Heartbeat::~Heartbeat() { stop(); }

void Heartbeat::start() {
    curl_global_init(CURL_GLOBAL_DEFAULT);
    running_.store(true);
    thread_ = std::thread(&Heartbeat::run, this);
}

void Heartbeat::stop() {
    running_.store(false);
    if (thread_.joinable()) thread_.join();
    curl_global_cleanup();
}

void Heartbeat::run() {
    spdlog::info("Heartbeat started (interval={}s)", cfg_.heartbeat_secs);
    while (running_.load()) {
        if (!post_heartbeat()) {
            spdlog::warn("Heartbeat PATCH failed");
        }
        auto snap = activity_.snapshot();
        if (!post_log(snap)) {
            spdlog::warn("Log POST failed");
        }
        std::this_thread::sleep_for(
            std::chrono::seconds(cfg_.heartbeat_secs));
    }
}

bool Heartbeat::post_heartbeat() {
    std::string url = cfg_.api_url + "/devices/"
                    + identity_.device_id() + "/heartbeat";
    nlohmann::json body;
    body["hostname"] = identity_.hostname();
    return http_patch(url, cfg_.device_token, body.dump());
}

bool Heartbeat::post_log(const ActivitySnapshot& snap) {
    std::string url = cfg_.api_url + "/logs";
    nlohmann::json body;
    body["device_id"]     = identity_.device_id();
    body["active_app"]    = snap.active_process_name;
    body["window_title"]  = snap.active_window_title;
    body["app_category"]  = snap.app_category;
    body["idle_seconds"]  = snap.idle_seconds;
    body["is_idle"]       = snap.is_idle;
    return http_post(url, cfg_.device_token, body.dump());
}

} // namespace rdm
