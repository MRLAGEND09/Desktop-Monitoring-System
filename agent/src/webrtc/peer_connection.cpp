// ============================================================================
// peer_connection.cpp
//
// Two compilation paths:
//   1. RDM_USE_LIBWEBRTC — full libwebrtc (Google's native WebRTC library)
//   2. Default          — DataChannel-over-WebSocket fallback (our signaling
//                         client already streams JPEG binary frames; this stub
//                         provides the same interface so the rest of the code
//                         compiles and runs without libwebrtc installed)
//
// To enable full WebRTC: cmake -DRDM_USE_LIBWEBRTC=ON -DWEBRTC_ROOT=<path>
// ============================================================================
#include "peer_connection.hpp"
#include <spdlog/spdlog.h>
#include <atomic>
#include <mutex>

#ifdef RDM_USE_LIBWEBRTC
// ── libwebrtc path ────────────────────────────────────────────────────────────
#  include <api/create_peerconnection_factory.h>
#  include <api/peer_connection_interface.h>
#  include <api/audio_codecs/builtin_audio_decoder_factory.h>
#  include <api/audio_codecs/builtin_audio_encoder_factory.h>
#  include <api/video_codecs/builtin_video_decoder_factory.h>
#  include <api/video_codecs/builtin_video_encoder_factory.h>
#  include <rtc_base/ssl_adapter.h>
#  include <rtc_base/thread.h>

namespace rdm {

struct PeerConnection::Impl
    : public webrtc::PeerConnectionObserver
    , public webrtc::CreateSessionDescriptionObserver
    , public webrtc::DataChannelObserver {

    rtc::scoped_refptr<webrtc::PeerConnectionFactoryInterface> factory;
    rtc::scoped_refptr<webrtc::PeerConnectionInterface>        pc;
    rtc::scoped_refptr<webrtc::DataChannelInterface>           channel;
    PeerConnectionObserver                                      obs;
    std::atomic<bool>                                           connected{false};

    // ── PeerConnectionObserver ───────────────────────────────────────────────
    void OnSignalingChange(webrtc::PeerConnectionInterface::SignalingState) override {}

    void OnIceCandidate(const webrtc::IceCandidateInterface* candidate) override {
        std::string sdp;
        candidate->ToString(&sdp);
        IceCandidate ic;
        ic.sdp_mid         = candidate->sdp_mid();
        ic.sdp_mline_index = candidate->sdp_mline_index();
        ic.candidate       = sdp;
        if (obs.on_ice_candidate) obs.on_ice_candidate(ic);
    }

    void OnConnectionChange(
        webrtc::PeerConnectionInterface::PeerConnectionState state) override {
        bool ok = (state == webrtc::PeerConnectionInterface::PeerConnectionState::kConnected);
        connected.store(ok);
        if (obs.on_connected) obs.on_connected(ok);
    }

    void OnDataChannel(
        rtc::scoped_refptr<webrtc::DataChannelInterface> ch) override {
        channel = ch;
        channel->RegisterObserver(this);
    }

    void OnIceCandidateError(const std::string&, int, const std::string&) override {}
    void OnTrack(rtc::scoped_refptr<webrtc::RtpTransceiverInterface>) override {}
    void OnRemoveTrack(rtc::scoped_refptr<webrtc::RtpReceiverInterface>) override {}
    void OnAddStream(rtc::scoped_refptr<webrtc::MediaStreamInterface>) override {}
    void OnRemoveStream(rtc::scoped_refptr<webrtc::MediaStreamInterface>) override {}
    void OnRenegotiationNeeded() override {}
    void OnIceConnectionChange(webrtc::PeerConnectionInterface::IceConnectionState) override {}
    void OnIceGatheringChange(webrtc::PeerConnectionInterface::IceGatheringState) override {}
    void OnIceCandidatesRemoved(const std::vector<cricket::Candidate>&) override {}

    // ── CreateSessionDescriptionObserver ─────────────────────────────────────
    void OnSuccess(webrtc::SessionDescriptionInterface* desc) override {
        pc->SetLocalDescription(
            webrtc::DummySetSessionDescriptionObserver::Create().get(), desc);
        std::string sdp;
        desc->ToString(&sdp);
        SessionDescription sd{ desc->type(), sdp };
        if (obs.on_local_description) obs.on_local_description(sd);
    }
    void OnFailure(webrtc::RTCError e) override {
        spdlog::error("SDP creation failed: {}", e.message());
    }

    // ── DataChannelObserver ──────────────────────────────────────────────────
    void OnStateChange() override {}
    void OnMessage(const webrtc::DataBuffer& buf) override {
        if (obs.on_data_channel_message)
            obs.on_data_channel_message(buf.data.data<uint8_t>(), buf.data.size());
    }
    void OnBufferedAmountChange(uint64_t) override {}
};

PeerConnection::PeerConnection(const Config& cfg, PeerConnectionObserver obs) {
    rtc::InitializeSSL();
    impl_ = std::make_unique<Impl>();
    impl_->obs = std::move(obs);

    // Thread model
    auto network_thread   = rtc::Thread::CreateWithSocketServer();
    auto worker_thread    = rtc::Thread::Create();
    auto signaling_thread = rtc::Thread::Create();
    network_thread->Start();
    worker_thread->Start();
    signaling_thread->Start();

    impl_->factory = webrtc::CreatePeerConnectionFactory(
        network_thread.get(), worker_thread.get(), signaling_thread.get(),
        nullptr, // default ADM
        webrtc::CreateBuiltinAudioEncoderFactory(),
        webrtc::CreateBuiltinAudioDecoderFactory(),
        webrtc::CreateBuiltinVideoEncoderFactory(),
        webrtc::CreateBuiltinVideoDecoderFactory(),
        nullptr, nullptr);

    // ICE configuration
    webrtc::PeerConnectionInterface::RTCConfiguration rtc_cfg;
    for (auto& url : cfg.stun_urls) {
        webrtc::PeerConnectionInterface::IceServer stun;
        stun.uri = url;
        rtc_cfg.servers.push_back(stun);
    }
    if (!cfg.turn_url.empty()) {
        webrtc::PeerConnectionInterface::IceServer turn;
        turn.uri      = cfg.turn_url;
        turn.username  = cfg.turn_user;
        turn.password  = cfg.turn_credential;
        rtc_cfg.servers.push_back(turn);
    }
    rtc_cfg.sdp_semantics = webrtc::SdpSemantics::kUnifiedPlan;

    webrtc::PeerConnectionDependencies deps(impl_.get());
    auto result = impl_->factory->CreatePeerConnectionOrError(rtc_cfg, std::move(deps));
    if (!result.ok()) throw std::runtime_error("CreatePeerConnection failed");
    impl_->pc = result.MoveValue();

    // Open unreliable DataChannel for low-latency frame delivery
    webrtc::DataChannelInit dc_config;
    dc_config.reliable = false;
    dc_config.ordered  = false;
    auto dc_result = impl_->pc->CreateDataChannelOrError("frames", &dc_config);
    if (dc_result.ok()) {
        impl_->channel = dc_result.MoveValue();
        impl_->channel->RegisterObserver(impl_.get());
    }
}

PeerConnection::~PeerConnection() {
    if (impl_->pc) impl_->pc->Close();
    rtc::CleanupSSL();
}

void PeerConnection::create_offer() {
    webrtc::PeerConnectionInterface::RTCOfferAnswerOptions opts;
    opts.offer_to_receive_audio = 0;
    opts.offer_to_receive_video = 0;
    impl_->pc->CreateOffer(impl_.get(), opts);
}

void PeerConnection::set_remote_description(const SessionDescription& sd) {
    webrtc::SdpParseError err;
    auto desc = webrtc::CreateSessionDescription(sd.type, sd.sdp, &err);
    if (!desc) {
        spdlog::error("SDP parse error: {}", err.description);
        return;
    }
    impl_->pc->SetRemoteDescription(
        webrtc::DummySetSessionDescriptionObserver::Create().get(), desc.release());
}

void PeerConnection::add_ice_candidate(const IceCandidate& ic) {
    webrtc::SdpParseError err;
    auto candidate = webrtc::CreateIceCandidate(
        ic.sdp_mid, ic.sdp_mline_index, ic.candidate, &err);
    if (candidate) impl_->pc->AddIceCandidate(candidate.get());
}

void PeerConnection::send_frame(const uint8_t* data, size_t len) {
    if (!impl_->channel ||
        impl_->channel->state() != webrtc::DataChannelInterface::kOpen) return;

    rtc::CopyOnWriteBuffer buf(data, len);
    impl_->channel->Send(webrtc::DataBuffer(buf, true /* binary */));
}

bool PeerConnection::is_connected() const {
    return impl_->connected.load();
}

} // namespace rdm

#else
// ── Fallback stub (no libwebrtc) ──────────────────────────────────────────────
// The signaling_client.cpp already handles JPEG frame delivery over WebSocket.
// This stub satisfies the linker so the project builds without libwebrtc.
namespace rdm {

struct PeerConnection::Impl {
    std::atomic<bool> connected{false};
    PeerConnectionObserver obs;
};

PeerConnection::PeerConnection(const Config&, PeerConnectionObserver obs) {
    impl_ = std::make_unique<Impl>();
    impl_->obs = std::move(obs);
    spdlog::info("PeerConnection: running in JPEG-over-WebSocket mode "
                 "(rebuild with -DRDM_USE_LIBWEBRTC=ON for full WebRTC)");
}
PeerConnection::~PeerConnection() = default;
void PeerConnection::create_offer() {
    spdlog::warn("create_offer: libwebrtc not linked — no-op");
}
void PeerConnection::set_remote_description(const SessionDescription&) {}
void PeerConnection::add_ice_candidate(const IceCandidate&) {}
void PeerConnection::send_frame(const uint8_t*, size_t) {}
bool PeerConnection::is_connected() const { return false; }

} // namespace rdm
#endif
