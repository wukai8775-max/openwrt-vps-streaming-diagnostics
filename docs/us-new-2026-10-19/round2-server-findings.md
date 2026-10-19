# Round 2: native receiver autotuning — passive evidence

> Public snapshot: 2026-10-19; network identifiers use role labels. Original configurations, addresses, credentials and raw evidence remain private. Read [the handoff and experiment ledger](index.md) for the final decision.

> Historical A0/B0 observation snapshot. This is not the final retention decision. Later B1/multi-target checks rejected the 16 MiB candidate and restored the original setting; read the [final round 2 report](round2-autotune.md) and [machine summary](../../examples/2026-10-19-us-new-round2-summary.json) first.

Date: 2026-10-19. This reviewer read server metrics and sampled TCP only. No server parameter, service, congestion algorithm, qdisc, buffer setting, or AU route was changed. Router setting changes and client downloads were performed by the coordinator and router reviewer.

## Current evidence supports a scoped receiver-window hypothesis

The original router `tcp_rmem` maximum was reported as **3916736 bytes**; B0 raised only its maximum to **16777216 bytes**, preserving minimum 4096, default 131072, automatic tuning and native TCP memory protections. Unlike the rejected `SO_RCVBUFFORCE` trial, this did not lock a receive buffer via an explicit socket option. The router namespace setting is shared by its TCP sockets; it must not be described as a US-new-only private socket setting. AU health checks and router memory protections are separate coordinator responsibilities.

The fixed VPS stayed on CUBIC, with unchanged Xray process identity and server `tcp_wmem` maximum **3141312 bytes** throughout the captured A0 and B0 windows. Fresh static evidence showed IO/memory PSI zero and about 250904 KiB available RAM.

## A0 receiver differences on the same fixed server

The A0 passive capture completed **91 samples / 180.013 seconds**, from **15:37:08.714 to 15:40:08.724 Asia/Shanghai**. Background small flows were not counted as download tests. Anonymous IDs are stable only within one capture, not across separate quick/long captures.

| Time window / matched size | Anonymous flow | Advertised send window | Receive-window limited | Other evidence |
|---|---|---|---|---|
| Mac independent-client reused group, 15:37:08–15:37:22; cumulative 75.12 MB | flow-42 | 1.436–4.194 MB | field absent | CUBIC; RTT227–327ms; sndbuf limited0.6–1.2%; final cumulative retrans2880 bytes / 2 segments |
| WiFi fresh candidate, 15:39:06–15:39:10; cumulative24.94 MB | flow-116 | 1.241–1.328 MB | 46.3–64.2% | CUBIC; RTT216–220ms |
| WiFi fresh candidate, 15:39:14–15:39:16; cumulative25.05 MB | flow-122 | 1.284 MB | 50.0–65.3% | CUBIC; RTT198–200ms |
| WiFi reused group, 15:39:20–15:39:42; cumulative75.12 MB | flow-124 | 0.408–1.330 MB | 4.3–35.6% | CUBIC; RTT222–266ms |

Path association uses coordinator start/end markers plus object byte totals. Anonymous server evidence alone does not prove a client's route. Both large-flow paths had MSS1440, so MSS was not used to distinguish them. The first slow Mac fresh request was not captured as a complete large-flow sequence; no socket explanation for it is invented. Its client TTFB1.119s versus total27.9007s establishes that most delay was in the body, not connection setup.

## B0 effect and data-quality limit

The intended B0 180-second capture ended with **SSH exit255 / timeout**, retaining **64 complete JSON samples over129.568 seconds**, **15:41:41.150–15:43:50.716**. This is an incomplete collector window, not a completed 180-second acceptance. The coordinator separately reported the Mac en5 management link failure; collector loss is not counted as a business-download failure.

The B0 reused75 MB flow (`flow-17` in this capture) had:

- Actual CC **CUBIC**, same server process identity.
- `snd_wnd` **5699072 bytes**, clearly larger than A0 WiFi's roughly1.3 MB.
- Bytes sent58.34→75.12 MB over about2 seconds; last sample bytes ACKed equaled sent and Send-Q was zero.
- RTT254.6→202.6ms, instantaneous delivery99.8→111.1 Mbps.
- Server socket `tb=3141312`; `sndbuf_limited`49.7–57.3%, with `app_limited` observed. This identifies a possible later constraint after opening the receiver window; it is not authorization to change sender settings in this experiment.
- No `rwnd_limited` field in the B0 large-flow tail; missing is not fabricated as zero.

Across the retained B0 samples, the service process identity was unchanged and all observed443 TCP algorithm fields were CUBIC (including background sockets). IO PSI avg10 maximum0%, CPU user maximum1.504%, system1.01%, iowait0.251%, steal0.249%; available RAM248116–267216 KiB. The later A1 download flows were not captured, so the old idle3.2 MB background socket was not used as A1 throughput evidence.

## Client outcomes reported by coordinator

| Stage | Fresh25 MB Mbps | Three-object sequence Mbps (first opens a connection) | Reused75 MB group |
|---|---|---|---|
| A0 Mac independent client | 7.17 | 19.62 / 58.06 / 57.67 | first reused curl request made a connection, later two reused it |
| A0 WiFi original router ceiling | coordinator retains raw per-request results | coordinator retains raw per-request results |25.266s,23.75 Mbps |
| B0 WiFi native larger ceiling |45.51 / 41.34 |41.34 / 74.34 / 83.16 |9.953s,60.28 Mbps; coordinator reports5/5 full completions |
| A1 WiFi restored original ceiling |29.76 / 31.75 |44.25 / 40.34 reported | not independently sampled in this collector window |

The enlarged advertised receive window and successful B0 complete-object improvement support the native-autotuning candidate more strongly than the prior forced-buffer trial. The reduction again when the coordinator restored A1 adds useful reversal evidence. B1 confirmation and final stable router readback remain necessary; these results are not a universal 200 Mbps guarantee or proof that all prior slowness had one cause.

## Private evidence

The evidence listed below is retained in a protected local directory, outside this repository:

- `vps-static.json`, `vps-socket-fresh.json`
- `vps-A0-paths-180s.jsonl`, `vps-A0-paths-safe-summary.json`
- `vps-A0-current-quick.jsonl`, `vps-A0-wifi-quick.jsonl`
- `vps-B0-native-180s.jsonl`, `vps-B0-native-quick.jsonl`, `vps-B0-native-safe-summary.json`
- `vps-A1-original-quick.jsonl` (idle / no matching active test flow; not treated as A1 test proof)

No new persistent long sampler was started after the coordinator reported the management-link change. The existing180-second collector source is ready for a fresh explicitly marked B1 window.
