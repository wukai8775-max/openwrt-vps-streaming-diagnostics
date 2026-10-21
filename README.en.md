<p align="center">
  <img src="assets/banner.svg" alt="OpenWrt / VPS streaming network diagnostics: measure, isolate, verify" width="100%">
</p>

<p align="center">
  <a href="README.md">简体中文</a> · <strong>English</strong> ·
  <a href="docs/quick-start.md">Quick start / 快速入门</a> ·
  <a href="docs/latest-progress.md">Latest evidence</a>
</p>

<p align="center">
  <a href="https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml"><img src="https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml/badge.svg" alt="Offline verification"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB.svg" alt="Python 3.10 or newer">
</p>

# OpenWrt / VPS Streaming Network Diagnostics

An evidence-led toolkit for **OpenWrt/Kwrt → PassWall/Xray → Linux VPS → target service**. Separate local access, forwarding, cross-border TCP, proxy processing and the destination before changing production settings.

Useful when:

- **Wi-Fi connects, but proxied sites do not load.** Check access, DNS redirection, proxy listeners and firewall policy separately.
- **BBR is enabled, but transfers remain slow.** Inspect the actual sending socket and compare a fixed, complete object.
- **A speed test completes, but a live stream still stalls.** Measure small requests under load, then verify the real phone and application.

Start with one primary path, keep every failed attempt, and test at most one evidence-backed production change. Keeping the current configuration is a valid outcome.

## Start with an offline example

Requires Python 3.10+. Actual transfer tests also require curl 8.4+; no pip dependencies are needed. Linux collectors run through the SSH access you already use.

```sh
git clone https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics.git
cd openwrt-vps-streaming-diagnostics
python3 tools/summarize.py examples/synthetic-downloads.jsonl
```

Expected result: **3 attempts, 2 complete objects and 1 partial timeout**. Only complete objects contribute to completion-time and task-goodput statistics. This reads a synthetic file; it does not contact a router, VPS or test endpoint.

Preview a bounded test plan without sending traffic:

```sh
python3 tools/download-test.py \
  --url https://download.example.invalid/fixed-10mb.bin \
  --source 192.0.2.10 --bytes 10000000 --repeat 5 --timeout 90 \
  --object-id demo-10MB --group demo-A0 --dry-run
sh tools/snapshot.sh --port 8443 --dry-run
```

These are documentation-only values. `--dry-run` makes **zero network requests**, does not collect live device metrics and does not measure speed. Before any live run, replace the source, exact object URL, SSH aliases and business port with values verified in your own environment.

Follow the [15-minute orientation guide](docs/quick-start.md) (Chinese) for protected result storage, read-only snapshots and the first live-test checklist. Fifteen minutes is an introductory budget, not a promise to diagnose a root cause.

## Choose your next step

| Goal | Read |
|---|---|
| Find the likely layer and avoid common misdiagnoses | [Decision tree](docs/decision-tree.md) |
| Run one bounded investigation | [Eight-hour playbook](docs/eight-hour-playbook.md) |
| Propose one reversible experiment | [Experiment card](docs/experiment-card.md) |
| Verify application behavior and recovery | [Acceptance and rollback](docs/acceptance-and-rollback.md) |
| Review measured results and unresolved issues | [Latest progress](docs/latest-progress.md) |
| Build isolated access groups on the same node | [Segmented AU acceptance](docs/segmented-au-acceptance.md) |

Detailed runbooks and the historical case are currently in Chinese. Commands, tool output and the [latest machine-readable handoff](examples/2026-10-19-us-new-handoff.json) are readable independently of those narratives.

## What the tools do

| Tool | Purpose | Production configuration changes |
|---|---|---|
| `tools/snapshot.sh` | Read-only Linux/OpenWrt snapshot; missing metrics are explicit | None |
| `tools/sample.sh` | Bounded samples of CPU, counters, queues and selected sockets | None |
| `tools/download-test.py` | Fixed-size HTTPS completion tests with source binding | None; generates bounded traffic |
| `tools/upload-test.py` | Parallel POST streams with a declared payload and rate budget | None; generates bounded traffic |
| `tools/probe.py` | Bound HTTPS / STUN request latency, timeouts and reconnects | None; generates probe traffic |
| `tools/summarize.py` | Offline summary preserving the failure denominator | None |
| `tools/check-publication.py` | Check tracked files for common accidental disclosures | None; does not replace manual review |

A transfer is complete only when curl exits successfully, HTTP status is 200, the exact object byte count matches and the required source check passes. A partial transfer remains a failure. Compare like-for-like objects, targets, directions, timeouts, bindings and rate conditions.

Source binding alone does not prove a transparent proxy mapping or the DNS path. A system default of BBR does not prove that the active sending connection uses BBR. HTTPS request timeouts are not video-packet loss. Public endpoints can refuse or rate-limit tests; preserve those outcomes and respect the service response.

## Latest follow-up · 2026-10-21 AU-group-12 download

**Production settings are retained; the short daytime checks did not reproduce the earlier timeout, and the cause remains unproven.** Historical load timeouts occurred in 12/13 visits; normalized neighboring group profiles match. Interleaved Wi-Fi downloads completed **4/4**, with **10/10** admitted load probes, but the last visit failed the next 192 MiB entry budget. An unbounded full-socket observer had accumulated about 21.5 MB on tmpfs; it was stopped, archived, verified and removed. A subsequent bounded original-SOCKS batch streamed its output to the test machine: downloads **3/3**, AU / US-new probes **8/8 each**, resource guards passed. No production rate cap, TCP change or restart was introduced. The earlier failures, collector flaw and missing per-visit exit-after checks remain explicit; this is not a stability signoff.

[Follow-up evidence and cleanup](docs/au-group-12-followup-2026-10-21.md) · [Machine summary](examples/2026-10-21-au-group-12-followup.json) · [Updated AU Agent prompt](docs/au-agent-prompt.md)

## Earlier evidence · 2026-10-21 AU expansion

**AU-group-6 through AU-group-15 are saved and applied. The original AU proxy path is retained; the extra Xray pool was rolled back and removed after a memory guard halt.** Measurements span 20–21 October, Asia/Shanghai. The ten new groups completed **28/30 downloads and 30/30 uploads**; group-12 completed only 1/3 downloads. Including three AU-main reference visits, full batches completed 35/39 and 39/39. HTTP probes under download load completed **116/143**, versus **44/44** under upload load; this is not full stability acceptance.

The specified IPv4 TCP isolation matrix passed 225/225 checks, including 210/210 directed cross-group rejections. This radio now uses its reported 16-AP quota. All AU groups share the same upstream, exit and bandwidth. Short candidate improvements did not meet the expanded resource gate; the original path also halted before cleanup. About 23.39 MB of verified diagnostic tmpfs was reclaimed, an evidenced resource contributor rather than a unique proven network cause. Phone streaming, peak hours, concurrency and reboot recovery remain unverified; application-stage short reassociations remain recorded.

[Configuration, per-group measurements and rollback](docs/au-expansion-2026-10-21.md) · [Machine-readable summary](examples/2026-10-21-au-expansion-summary.json) · [AU Agent handoff prompt](docs/au-agent-prompt.md) · [Latest progress](docs/latest-progress.md)

## Earlier evidence · 2026-10-19 US-new

**The new US route, US-new, is connected; no performance candidate from three investigation rounds was retained.** A BBR listener and forced receive buffer were rejected. A native 16 MiB router receive ceiling improved CF but failed the Google acceptance gate: median 34.511 Mbps original versus 16.706 Mbps candidate. The original configuration was restored.

The latest round completed 12/12 public-path data requests and, separately, 3/3 local Wi-Fi/LAN downloads at 535–612 Mbps. The independent Mac client had faster reused/Google transfers but a slower fresh connection and observed retransmission; this is not a universal offload benefit. AU reference probes completed 16/16 in that round and temporary test services/rules were removed. The earlier onboarding repair briefly reassociated AU groups; that negative event remains recorded.

US-new and legacy US-main below are different VPS routes. The new VPS retains CUBIC; the router retains its original default BBR. Phone livestreams, authenticated Claude long sessions, peak hours, sustained multi-device use and end-to-end 200 Mbps capacity remain unaccepted. Local short-transfer throughput is not public-path capacity.

Read the [Agent handoff and experiment ledger](docs/us-new-2026-10-19/index.md), [machine-readable handoff](examples/2026-10-19-us-new-handoff.json), [round 3 report](docs/us-new-2026-10-19/round3-bottlenecks.md) and [latest progress](docs/latest-progress.md). They distinguish executed-and-rejected candidates from hypotheses assessed but never executed.

## Historical evidence · 2026-10-14 US-main

**Current decision: keep production settings; reject MSS 1200.** Five follow-up pairs completed **4/5** original-condition objects and **3/5** candidate objects. The candidate was about **18.45% slower** by paired complete-only median time. A paced 15 Mbps direct-TCP test received approximately **4.194 Mbps downstream / 14.670 Mbps upstream**. Synchronized sockets attributed part of an 11-second startup to outer TCP establishment and reply recovery; the exact public-network impairment location remains unproven.

Two actual-client upload conditions each lasted approximately **54 seconds**, completing **4/4** streams at group task goodput **4.969 / 14.915 Mbps**. Strict load probes completed HTTPS **91/91** and STUN **97/97**, with maximum response times still **2.037 / 1.379 seconds**. The 5 Mbps per-stream limit is a test budget, not a production setting. Production changes: **0**. AU reference probes completed **72/72** during the observation period and **30/30** around the MSS pairs. Phone/platform, peak-hour and long-duration acceptance remain pending.

Read the [transport and short-load report](docs/us-transport-and-load-2026-10-14.md), [that historical phase summary](examples/2026-10-14-us-transport-load-summary.json) and [timestamped progress](docs/latest-progress.md). Earlier failures stay in their original batches.

### Earlier phase: sequential layer comparison

The current evidence contains separate batches, not a combined all-pass result:

| Batch | Complete / attempted | Interpretation |
|---|---:|---|
| US VPS direct downloads, two targets | **6/6** | Median task goodput approximately 54.6 / 86.0 Mbps |
| Router downloads through the same US node | **6/6** | Approximately 4.3 / 8.4 Mbps, with Wi-Fi removed from the test path |
| Actual US client, two download targets and CF upload | **9/9** | Download medians approximately 8.5 / 10.4 Mbps; upload 19.2 Mbps, maximum single round 22.7 Mbps |

This narrows the investigation to the router upstream, US proxy connection and cross-border segment. Shared-WAN background traffic, the precise public-network location and mechanism remain unconfirmed. Router goodput uses curl's full transaction time; VPS/client goodput uses independent wall time. Sequential layer comparisons are not a parameter A/B experiment or evidence of an optimization gain.

US downloads remained slower at both targets, and second-scale connection startup was observed. **Real-phone live streaming, simultaneous streams and peak-hour behavior remain unaccepted.** A 15-second connection budget is a diagnostic condition, not a production fix. One router transaction completed after TLS startup exceeded the old five-second budget. The earlier six-group CF **73/84**, OVH **42/42**, separate US upload **7/7**, refusals and timeouts remain in the historical record.

No new production parameter changes were made. Read the [layer diagnosis](docs/us-diagnosis-2026-10-14.md), [machine-readable summary](examples/2026-10-14-us-diagnosis-summary.json) and [timestamped progress report](docs/latest-progress.md) for conditions, cleanup and evidence limits. This repository is a saved report, not live monitoring or an all-day speed guarantee.

## Case router and firmware

Read back on **2026-10-14**: **Ruijie RG-X60 Pro**, running **Kwrt 25.12-SNAPSHOT**, reported build revision `10.08.2026`, Linux kernel `6.12.112`. The [environment record](docs/environment.md) includes the target, board and field sources. This records the currently running system; the historical test windows and results remain separate.

## Run offline checks

```sh
python3 -m unittest discover -s tests -v
sh -n tools/snapshot.sh
sh -n tools/sample.sh
python3 tools/check-publication.py
git diff --check
```

GitHub Actions runs offline tests using synthetic data, fake curl and fake Linux commands. It does not speed-test a live network. Runtime coverage varies by tool and mode; [latest progress](docs/latest-progress.md) distinguishes the locally measured case from generic offline validation.

## Keep raw evidence private

```sh
umask 077
mkdir -p results
chmod 700 results
```

`results/` is ignored by Git. Raw output may contain addresses, socket identifiers and network labels even when it contains no passwords. Do not upload credentials, full configuration backups, private keys, unredacted captures or raw diagnostic logs. Publish only manually reviewed, sanitized evidence; see [SECURITY.md](SECURITY.md).

## Reuse with another Agent or node

Give the Agent this repository and ask it to read `README.en.md`, `docs/latest-progress.md` and the latest summary JSON first. It should distinguish historical results from pending acceptance, verify your own roles and current configuration, rebuild a baseline, and propose one evidence-backed change with a recovery method.

Please report reproducible symptoms and sanitized counts through the repository's issue templates. Include what completed, what failed and what remains unverified. Hardware, routes and proxy behavior differ; copying a parameter set is not a diagnosis.

Released under the [MIT License](LICENSE).
