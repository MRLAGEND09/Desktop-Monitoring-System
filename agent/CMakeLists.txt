cmake_minimum_required(VERSION 3.20)
project(rdm-agent VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ── Options ───────────────────────────────────────────────────────────────────
option(RDM_ENABLE_TESTS   "Build unit tests"            OFF)
option(RDM_USE_LIBWEBRTC  "Link against libwebrtc"      OFF)
if(RDM_USE_LIBWEBRTC)
    set(WEBRTC_ROOT "" CACHE PATH "Path to libwebrtc build output")
endif()

# ── Find packages ─────────────────────────────────────────────────────────────
find_package(Threads REQUIRED)

# External dependencies (fetched via vcpkg or FetchContent)
find_package(OpenSSL REQUIRED)
find_package(ZLIB    REQUIRED)

# nlohmann/json — header-only, included via vcpkg
find_package(nlohmann_json CONFIG REQUIRED)

# spdlog — structured logging
find_package(spdlog CONFIG REQUIRED)

# libcurl — REST calls to backend API
find_package(CURL REQUIRED)

# ── Sources ───────────────────────────────────────────────────────────────────
set(AGENT_SOURCES
    src/main.cpp
    src/config.cpp
    src/identity.cpp
    src/capture/screen_capture.cpp
    src/encoder/video_encoder.cpp
    src/encoder/h264_encoder.cpp
    src/webrtc/peer_connection.cpp
    src/webrtc/signaling_client.cpp
    src/activity/activity_tracker.cpp
    src/heartbeat/heartbeat.cpp
    src/service/windows_service.cpp
)

add_executable(rdm-agent ${AGENT_SOURCES})

target_include_directories(rdm-agent PRIVATE
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_SOURCE_DIR}/third_party/include
)

target_link_libraries(rdm-agent PRIVATE
    Threads::Threads
    OpenSSL::SSL
    OpenSSL::Crypto
    ZLIB::ZLIB
    nlohmann_json::nlohmann_json
    spdlog::spdlog
    CURL::libcurl
)

# ── libwebrtc (optional) ─────────────────────────────────────────────────────
if(RDM_USE_LIBWEBRTC AND WEBRTC_ROOT)
    target_compile_definitions(rdm-agent PRIVATE RDM_USE_LIBWEBRTC)
    target_include_directories(rdm-agent PRIVATE "${WEBRTC_ROOT}/include")
    target_link_directories(rdm-agent PRIVATE "${WEBRTC_ROOT}/lib")
    target_link_libraries(rdm-agent PRIVATE webrtc)
endif()

# ── Windows-specific ──────────────────────────────────────────────────────────
if(WIN32)
    target_compile_definitions(rdm-agent PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN)
    target_link_libraries(rdm-agent PRIVATE
        ws2_32 winmm dxgi d3d11 dwmapi gdi32 user32 psapi
        mf mfplat mfuuid ole32
    )
    # Embed version info and manifest
    if(MSVC)
        target_compile_options(rdm-agent PRIVATE /W4 /WX- /MP)
    endif()
endif()

# ── Install ───────────────────────────────────────────────────────────────────
install(TARGETS rdm-agent RUNTIME DESTINATION bin)
install(FILES ${CMAKE_SOURCE_DIR}/rdm-agent.toml.example DESTINATION bin)

# ── Tests ─────────────────────────────────────────────────────────────────────
if(RDM_ENABLE_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()
