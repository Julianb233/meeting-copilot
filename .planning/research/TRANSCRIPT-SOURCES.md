# Real-Time Meeting Transcript Sources Research

**Project:** Meeting Copilot
**Researched:** 2026-03-20
**Mode:** Comparison / Ecosystem
**Overall Confidence:** MEDIUM-HIGH

---

## Executive Summary

After researching 10 options for real-time meeting transcription across Zoom and Google Meet, the clear recommendation is a **two-pronged approach**: use **Deepgram's streaming WebSocket API** as the transcription engine, fed by either **Zoom RTMS** (for Zoom meetings) or a **Chrome extension with tabCapture** (for Google Meet). This gives you real-time streaming, speaker diarization, no polling rate limits, and costs effectively $0 with the $200 free credit (~433 hours of transcription).

The "universal bot" approach (Recall.ai) works but costs $0.65/hr. The self-hosted Whisper approach is feasible given the 48-core VPS but adds significant complexity for marginal cost savings over Deepgram's free tier.

---

## Option-by-Option Analysis

### 1. Zoom RTMS SDK

| Attribute | Details |
|-----------|---------|
| **Works with** | Zoom only |
| **Streaming** | Yes -- real-time WebSocket delivery of audio, video, and transcript data |
| **Rate limits** | No polling needed -- push-based via WebSocket |
| **Speaker ID** | Yes (transcript stream includes speaker info) |
| **Self-hostable** | N/A -- it's a Zoom-hosted pipeline you connect to |
| **Pricing** | Free to use, but requires Zoom Pro/Licensed host account (~$13/mo) |
| **API quality** | HIGH -- official Zoom SDK, Python (`pip install rtms`) and Node.js (`npm install @zoom/rtms`), well-documented with samples |
| **Confidence** | HIGH (official Zoom docs) |

**How it works:** RTMS is a data pipeline giving direct access to live audio, video, and transcript data from Zoom meetings via WebSocket. No bot joins the meeting -- it taps the media stream directly from Zoom's infrastructure.

**Key requirement:** The meeting host must have a paid Zoom plan (Pro or above). Basic/Free accounts get "App could not reach meeting content" errors. Julian already has Zoom running on his MacBook Pro, so this is likely already met.

**Verdict: YES for Zoom meetings.** This is the best option for Zoom -- native, low-latency, no bot participant visible, and includes built-in transcript with speaker labels. However, it only covers Zoom, not Google Meet.

**Sources:**
- [Zoom RTMS Developer Docs](https://developers.zoom.us/docs/rtms/)
- [Zoom RTMS GitHub](https://github.com/zoom/rtms)
- [Zoom RTMS Samples](https://github.com/zoom/rtms-samples)
- [RTMS Plan Requirements Discussion](https://devforum.zoom.us/t/does-startrtms-require-the-meeting-host-to-have-a-paid-pro-licensed-zoom-plan/142303)

---

### 2. Google Meet REST API / Workspace Events API

| Attribute | Details |
|-----------|---------|
| **Works with** | Google Meet only |
| **Streaming** | NO -- transcripts only available after meeting ends |
| **Rate limits** | Standard Google API quotas |
| **Speaker ID** | Yes (in post-meeting transcript entries) |
| **Self-hostable** | No |
| **Pricing** | Free with Google Workspace |
| **API quality** | MEDIUM -- REST API is GA, but transcripts are post-meeting only |
| **Confidence** | HIGH (official Google docs) |

**How it works:** The Google Meet REST API provides access to recordings, transcripts, and participant data, but only after the meeting concludes. The Workspace Events API can notify you when a transcript starts/ends/is generated, but the actual transcript content is still only available post-meeting.

**Verdict: NO for real-time.** Completely useless for live/streaming transcription. Only good for post-meeting retrieval.

**Sources:**
- [Google Meet REST API Overview](https://developers.google.com/workspace/meet/api/guides/overview)
- [Google Workspace Events API for Meet](https://developers.google.com/workspace/events/guides/events-meet)

---

### 3. Google Meet Media API (NEW)

| Attribute | Details |
|-----------|---------|
| **Works with** | Google Meet only |
| **Streaming** | Yes -- real-time audio/video via WebRTC |
| **Rate limits** | Unknown (Developer Preview) |
| **Speaker ID** | Yes (participant metadata available) |
| **Self-hostable** | No |
| **Pricing** | Unknown (Developer Preview) |
| **API quality** | LOW -- Developer Preview only, requires all participants enrolled in preview program |
| **Confidence** | MEDIUM (official docs, but preview status makes it unreliable for production) |

**How it works:** The Meet Media API lets your app join a Google Meet conference and consume real-time audio/video streams via WebRTC. This is the Google equivalent of Zoom RTMS. However, it's in Developer Preview, meaning:
- Your Google Cloud project must be enrolled in the Developer Preview Program
- The OAuth principal must be enrolled
- **ALL participants in the conference must be enrolled** (dealbreaker)

**Verdict: NO for now.** The requirement that all participants be enrolled in the Developer Preview makes this unusable in production. Revisit when it reaches GA (no timeline announced).

**Sources:**
- [Meet Media API Overview](https://developers.google.com/workspace/meet/media-api/guides/overview)
- [Meet Media API Concepts](https://developers.google.com/workspace/meet/media-api/guides/concepts)

---

### 4. Recall.ai (Universal Meeting Bot)

| Attribute | Details |
|-----------|---------|
| **Works with** | Zoom, Google Meet, Teams, Webex, GoTo, Slack Huddles |
| **Streaming** | Yes -- real-time transcripts via webhook with sub-second latency |
| **Rate limits** | No polling needed -- webhook push |
| **Speaker ID** | Yes |
| **Self-hostable** | No |
| **Pricing** | $0.50/hr recording + $0.15/hr transcription = $0.65/hr total |
| **API quality** | HIGH -- well-documented, purpose-built for this use case |
| **Confidence** | HIGH (official pricing page, confirmed 2026) |

**How it works:** Recall.ai sends a bot participant to join your meeting. The bot records audio/video and streams real-time transcripts back to you via webhooks. It's the "easy button" -- universal platform support, no browser extension needed, no self-hosting.

**Cost analysis:** At $0.65/hr, a 1-hour daily meeting costs ~$20/month. A heavy meeting schedule (4 hrs/day, 20 days/month) would be ~$52/month.

**Pros:**
- Works everywhere with zero platform-specific code
- Real-time transcripts via webhook (no polling, no rate limits)
- Speaker identification included
- Free trial credits on signup

**Cons:**
- A visible bot joins the meeting (participants see "Recall Bot" or similar)
- Ongoing per-hour cost ($0.65/hr)
- Vendor lock-in -- no self-hosting option

**Verdict: MAYBE.** Best "it just works" universal option, but the cost adds up and the visible bot can be awkward. Good fallback if the Chrome extension approach for Google Meet proves too complex.

**Sources:**
- [Recall.ai Pricing](https://www.recall.ai/pricing)
- [Recall.ai 2026 Pricing Blog](https://www.recall.ai/blog/new-recall-ai-pricing-for-2026)
- [Recall.ai Google Meet Bot API](https://www.recall.ai/product/meeting-bot-api/google-meet)

---

### 5. Deepgram (Real-Time STT API)

| Attribute | Details |
|-----------|---------|
| **Works with** | Any audio source (platform-agnostic transcription engine) |
| **Streaming** | Yes -- WebSocket streaming with ~300ms latency |
| **Rate limits** | No request-based limits -- WebSocket is a persistent connection |
| **Speaker ID** | Yes -- speaker diarization supported in streaming mode |
| **Self-hostable** | No (cloud API), but on-prem available for enterprise |
| **Pricing** | $200 free credit (~433 hours), then $0.0077/min ($0.46/hr) streaming |
| **API quality** | HIGH -- excellent docs, SDKs for Python/JS/Go/etc, WebSocket-native |
| **Confidence** | HIGH (official pricing page, verified 2026) |

**How it works:** You open a WebSocket to Deepgram, stream raw audio (PCM/16-bit), and get back real-time transcript with speaker labels, timestamps, and confidence scores. Deepgram doesn't know or care where the audio comes from -- you need a separate mechanism to capture audio from Zoom/Meet.

**Cost analysis:**
- $200 free credit = ~433 hours of streaming transcription
- At 4 hours/day meetings, that's ~108 days (3.5 months) of free transcription
- After free credit: $0.46/hr = ~$37/month for 4 hrs/day

**Why this is the transcription engine pick:**
1. WebSocket = no polling, no rate limits
2. $200 free = months of free usage
3. Speaker diarization in streaming mode
4. Best-in-class accuracy (Nova-3 model)
5. Dead simple API -- send audio chunks, get text back

**Verdict: YES -- as the transcription engine.** Deepgram handles the speech-to-text. You still need something to capture the audio (RTMS for Zoom, Chrome extension for Meet).

**Sources:**
- [Deepgram Pricing](https://deepgram.com/pricing)
- [Deepgram Pricing Breakdown 2026](https://brasstranscripts.com/blog/deepgram-pricing-per-minute-2025-real-time-vs-batch)
- [Deepgram Chrome Extension Tutorial](https://deepgram.com/learn/transcribing-browser-tab-audio-chrome-extensions)

---

### 6. AssemblyAI (Real-Time STT API)

| Attribute | Details |
|-----------|---------|
| **Works with** | Any audio source (platform-agnostic transcription engine) |
| **Streaming** | Yes -- WebSocket streaming with ~300ms P50 latency |
| **Rate limits** | Unlimited concurrency, no request-based limits |
| **Speaker ID** | Partial -- streaming supports generic labels (Speaker A, Speaker B) but NOT named identification |
| **Self-hostable** | No |
| **Pricing** | 333 hours free, then $0.15/hr streaming |
| **API quality** | HIGH -- good docs, SDKs, active development |
| **Confidence** | HIGH (official docs) |

**How it works:** Similar to Deepgram -- WebSocket connection, stream audio, get real-time transcripts. Supports speaker diarization in streaming mode with `speaker_labels: true`.

**Cost comparison vs Deepgram:**
- Free tier: 333 hours (AssemblyAI) vs 433 hours (Deepgram)
- Per-hour: $0.15/hr (AssemblyAI) vs $0.46/hr (Deepgram)
- AssemblyAI is cheaper per-hour after free credits run out

**Why not the primary pick:** Deepgram has slightly better free credits, wider language support, and the Chrome extension tutorial (Deepgram published a guide specifically for tab audio capture). AssemblyAI is a strong alternative if Deepgram doesn't work out, and is cheaper long-term.

**Verdict: MAYBE -- strong alternative to Deepgram.** Cheaper per-hour rate but slightly less free credit. Keep as backup.

**Sources:**
- [AssemblyAI Pricing](https://www.assemblyai.com/pricing)
- [AssemblyAI Streaming Docs](https://assemblyai.com/docs/universal-streaming)
- [AssemblyAI Speaker Diarization](https://www.assemblyai.com/docs/pre-recorded-audio/speaker-diarization)

---

### 7. Rev.ai (Real-Time STT API)

| Attribute | Details |
|-----------|---------|
| **Works with** | Any audio source |
| **Streaming** | Yes -- WebSocket streaming |
| **Rate limits** | Unknown specifics |
| **Speaker ID** | Yes (pricing unclear if included or extra) |
| **Self-hostable** | No |
| **Pricing** | Conflicting reports: $0.003/min ($0.18/hr) to $0.25/min ($15/hr) -- unclear |
| **API quality** | MEDIUM -- decent docs but less community presence than Deepgram/AssemblyAI |
| **Confidence** | LOW (conflicting pricing info, less clear documentation) |

**Verdict: NO.** Pricing is unclear, documentation quality is lower than Deepgram/AssemblyAI, and no clear advantage over the alternatives.

**Sources:**
- [Rev.ai Pricing](https://www.rev.ai/pricing)
- [Rev.ai Pricing Analysis](https://brasstranscripts.com/blog/rev-ai-pricing-per-minute-2025-better-alternative)

---

### 8. Whisper (Self-Hosted)

| Attribute | Details |
|-----------|---------|
| **Works with** | Any audio source (self-hosted transcription engine) |
| **Streaming** | Possible with WhisperLiveKit or whisper_streaming, but complex |
| **Rate limits** | None (self-hosted) |
| **Speaker ID** | Yes with pyannote + whisperX, but adds complexity |
| **Self-hostable** | Yes -- the whole point |
| **Pricing** | Free (VPS costs only, already provisioned) |
| **API quality** | LOW -- cobbling together OSS projects, not a clean API |
| **Confidence** | MEDIUM (well-known projects, but integration complexity is real) |

**How it works:** Run faster-whisper or WhisperLiveKit on the VPS. Feed it audio chunks over a WebSocket. Get transcripts back. Add pyannote for speaker diarization.

**The 48-core VPS can handle this:** faster-whisper on CPU with large-v3 model works at ~10x realtime on modern CPUs. With 48 cores, multiple concurrent streams are feasible.

**Key projects:**
- **WhisperLiveKit** -- combines streaming + diarization, SOTA 2025
- **faster-whisper** -- CTranslate2 backend, fastest CPU inference
- **whisperX** -- word-level timestamps + diarization
- **pyannote** -- neural speaker diarization

**Why not the primary pick:**
1. Deepgram's $200 free credit gives 433 hours free -- that's ~3.5 months
2. Self-hosted requires significant setup: audio pipeline, WebSocket server, model serving, diarization pipeline
3. Latency: self-hosted streaming Whisper has higher latency than Deepgram (~1-3s vs ~300ms)
4. Ongoing maintenance burden

**Verdict: MAYBE -- good long-term fallback.** If Deepgram's free credit runs out and you want zero ongoing cost, self-hosted Whisper on the VPS is viable. But don't start here. Start with Deepgram, only move to self-hosted if cost becomes an issue.

**Sources:**
- [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [whisperX](https://github.com/m-bain/whisperX)
- [whisper_streaming](https://github.com/ufal/whisper_streaming)

---

### 9. Fireflies Realtime API (WebSocket)

| Attribute | Details |
|-----------|---------|
| **Works with** | Meetings where Fireflies bot is already present |
| **Streaming** | Yes -- WebSocket delivery of live transcription events |
| **Rate limits** | Unclear (beta), but general API: 50 req/day on Pro, 60 req/min on Business |
| **Speaker ID** | Yes (Fireflies identifies speakers) |
| **Self-hostable** | No |
| **Pricing** | Requires Fireflies Pro ($18/mo) or Business ($29/mo) plan |
| **API quality** | LOW -- beta, sparse documentation |
| **Confidence** | LOW (beta status, undocumented limits) |

**How it works:** Connect via WebSocket using API token + transcript ID to receive live transcription events as they're generated by the Fireflies bot.

**Problem:** You still need the Fireflies bot in the meeting, AND you're still subject to their plan limits for bot invocations. The WebSocket solves the polling rate limit (no more 50 req/day for fetching transcripts), but the underlying bot + plan limitations remain.

**Verdict: NO.** Doesn't solve the fundamental problem. You're already paying for Fireflies and hitting limits. The Realtime API helps with the polling issue but doesn't address meeting bot limitations or cost.

**Sources:**
- [Fireflies Realtime API Overview](https://docs.fireflies.ai/realtime-api/overview)
- [Fireflies Rate Limits](https://guide.fireflies.ai/articles/9908984274-learn-about-rate-limits)

---

### 10. Otter.ai API

| Attribute | Details |
|-----------|---------|
| **Works with** | Meetings where Otter bot is present |
| **Streaming** | Unknown -- API is beta, real-time capabilities unclear |
| **Rate limits** | Unknown (beta) |
| **Speaker ID** | Yes |
| **Self-hostable** | No |
| **Pricing** | Unknown (enterprise beta, contact sales) |
| **API quality** | LOW -- beta, enterprise-focused, no public docs |
| **Confidence** | LOW (beta, no public pricing or rate limit info) |

**Verdict: NO.** The API is in beta, enterprise-focused, and has no public documentation or pricing. Not viable for this use case.

**Sources:**
- [Otter.ai API FAQ](https://help.otter.ai/hc/en-us/articles/4412365535895-Does-Otter-offer-an-open-API)

---

### 11. Chrome Extension + Tab Audio Capture (for Google Meet)

| Attribute | Details |
|-----------|---------|
| **Works with** | Google Meet (and any browser-based meeting platform) |
| **Streaming** | Yes -- captures tab audio and streams to transcription API |
| **Rate limits** | None (audio capture is local) |
| **Speaker ID** | Depends on transcription backend (Deepgram supports it) |
| **Self-hostable** | Yes (extension is yours) |
| **Pricing** | Free (extension) + transcription API cost |
| **API quality** | MEDIUM -- well-documented Chrome APIs, Deepgram has a tutorial |
| **Confidence** | HIGH (chrome.tabCapture is a stable Chrome API, Deepgram tutorial exists) |

**How it works:**
1. Chrome extension uses `chrome.tabCapture` API to capture audio from the Google Meet tab
2. Audio is processed via Web Audio API (AudioContext + AudioWorklet) to get raw PCM
3. PCM chunks are streamed via WebSocket to Deepgram (or your VPS running Whisper)
4. Real-time transcripts come back with speaker labels

**Deepgram has published a complete tutorial for this exact pattern:** [Transcribing Browser Tab Audio with Chrome Extensions](https://deepgram.com/learn/transcribing-browser-tab-audio-chrome-extensions)

**Complexity:** Medium. You need to build:
- Chrome extension (manifest v3, ~200 lines)
- Audio capture + WebSocket streaming logic (~150 lines)
- Backend to receive and store transcripts

**Verdict: YES for Google Meet.** This is the best approach for Google Meet given that the Meet Media API is stuck in Developer Preview. Combined with Deepgram, it gives you real-time streaming transcription with speaker diarization.

**Sources:**
- [Deepgram Chrome Extension Tutorial](https://deepgram.com/learn/transcribing-browser-tab-audio-chrome-extensions)
- [Chrome tabCapture API](https://developer.chrome.com/docs/extensions/reference/api/tabCapture)
- [GitHub Discussion: Tab Audio from Zoom/Meet](https://github.com/orgs/community/discussions/162134)
- [Recall.ai: How to Build Chrome Recording Extension](https://www.recall.ai/blog/how-to-build-a-chrome-recording-extension)

---

## Comparison Matrix

| Option | Zoom | Meet | Real-Time | Rate Limits | Speaker ID | Cost | Recommendation |
|--------|------|------|-----------|-------------|------------|------|----------------|
| **Zoom RTMS** | YES | no | YES | None (WebSocket) | YES | Free (needs Pro plan) | **YES for Zoom** |
| **Google Meet REST API** | no | YES | NO | Standard | YES (post-meeting) | Free | NO |
| **Google Meet Media API** | no | YES | YES | Unknown | YES | Unknown | NO (preview only) |
| **Recall.ai** | YES | YES | YES | None (webhook) | YES | $0.65/hr | MAYBE (backup) |
| **Deepgram** | any | any | YES | None (WebSocket) | YES | $200 free, then $0.46/hr | **YES (engine)** |
| **AssemblyAI** | any | any | YES | None (WebSocket) | Partial | 333hr free, then $0.15/hr | MAYBE (alt engine) |
| **Rev.ai** | any | any | YES | Unknown | YES | Unclear | NO |
| **Whisper (self-hosted)** | any | any | YES* | None | YES* | Free | MAYBE (long-term) |
| **Fireflies Realtime** | YES | YES | YES | Beta, unclear | YES | $18-29/mo plan | NO |
| **Otter.ai API** | YES | YES | Unknown | Unknown | YES | Unknown (enterprise) | NO |
| **Chrome Extension** | no | YES | YES | None | Depends on backend | Free + backend | **YES for Meet** |

---

## Recommended Architecture

### Primary Approach: Zoom RTMS + Chrome Extension + Deepgram

```
ZOOM MEETINGS:
  Zoom RTMS SDK (WebSocket) --> raw audio/transcript --> Meeting Copilot Backend
                                                              |
                                                              v
                                                         [Store + Process]

GOOGLE MEET:
  Chrome Extension (tabCapture) --> raw audio (WebSocket) --> Deepgram API
                                                                   |
                                                                   v
                                                              [Transcript]
                                                                   |
                                                                   v
                                                         Meeting Copilot Backend
                                                              |
                                                              v
                                                         [Store + Process]
```

**For Zoom meetings:**
- Use Zoom RTMS SDK directly -- it provides both raw audio AND built-in transcripts with speaker labels
- No need for Deepgram for Zoom (RTMS includes transcript data)
- Zero additional cost beyond Zoom Pro subscription

**For Google Meet:**
- Chrome extension captures tab audio via `chrome.tabCapture`
- Audio streams to Deepgram via WebSocket for real-time transcription
- Deepgram returns transcript with speaker diarization
- $200 free credit covers ~433 hours

### Fallback: Recall.ai (Universal)

If the Chrome extension approach is too complex or unreliable, Recall.ai is the universal fallback:
- Works on both platforms with a single API
- Real-time transcripts via webhook
- $0.65/hr (manageable for occasional use)

### Long-Term: Self-Hosted Whisper

When Deepgram credits run out, migrate the Google Meet audio stream from Deepgram to a self-hosted faster-whisper + pyannote stack on the VPS. The architecture stays the same -- only the WebSocket endpoint changes.

---

## Implementation Priority

### Phase 1: Zoom RTMS (Easiest Win)
- Install `pip install rtms` or `npm install @zoom/rtms`
- Follow RTMS sample apps to connect to Zoom meeting stream
- Receive real-time transcript data with speaker labels
- Store in Meeting Copilot backend
- **Effort:** 1-2 days
- **Cost:** $0 (assuming Zoom Pro already active)

### Phase 2: Chrome Extension + Deepgram (Google Meet)
- Build Chrome extension with manifest v3
- Use `chrome.tabCapture` to capture Meet tab audio
- Stream to Deepgram WebSocket API
- Receive real-time transcript with speaker diarization
- Store in Meeting Copilot backend
- **Effort:** 3-5 days
- **Cost:** $0 for ~433 hours (Deepgram free credit)

### Phase 3 (Optional): Self-Hosted Whisper Migration
- Set up faster-whisper + pyannote on VPS
- Replace Deepgram WebSocket endpoint with self-hosted endpoint
- **Effort:** 2-3 days
- **Cost:** $0 (VPS already provisioned)

---

## Cost Comparison (4 hrs/day, 20 days/month)

| Approach | Monthly Cost | Notes |
|----------|-------------|-------|
| **Recommended (RTMS + Chrome + Deepgram)** | $0 for ~5.4 months, then ~$37/mo | Deepgram only needed for Meet |
| **Recall.ai universal** | ~$52/mo | Simple but visible bot |
| **Self-hosted Whisper** | $0 | Complex setup, higher latency |
| **Fireflies (current)** | $18-29/mo + rate limit pain | What you're escaping from |
| **AssemblyAI (alt engine)** | $0 for ~4.2 months, then ~$12/mo | Cheaper long-term than Deepgram |

---

## Open Questions

1. **Zoom plan verification:** Confirm Julian's Zoom account is Pro/Licensed (RTMS requirement). If it's Basic/Free, RTMS won't work.
2. **Chrome extension distribution:** Will this only run on Julian's browser, or does it need to be distributed? If personal use only, sideloading in developer mode is fine.
3. **AssemblyAI vs Deepgram long-term:** If cost matters after free credits, AssemblyAI at $0.15/hr is 67% cheaper than Deepgram at $0.46/hr. Consider switching engines later.
4. **Google Meet Media API timeline:** Monitor when it exits Developer Preview. Once GA, it could replace the Chrome extension approach with a cleaner server-side solution.

---

## Final Recommendation

**Drop Fireflies. Use Zoom RTMS for Zoom + Chrome Extension + Deepgram for Google Meet.**

This gives you:
- Real-time streaming (no polling, no rate limits)
- Speaker identification on both platforms
- $0 cost for months (Deepgram free credit + RTMS is free)
- No visible bot in meetings (RTMS is invisible, Chrome extension is local)
- Clean migration path to self-hosted Whisper when free credits expire
