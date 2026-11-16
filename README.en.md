# OpenWrt / VPS Network Diagnostics

[简体中文](README.md) · **English**

Use this toolkit when Wi-Fi connects but pages fail to load, downloads stop halfway, or a stream keeps freezing. The first check runs on your computer and needs no router or server login.

| What do you want to do? | Start here |
|---|---|
| See what a report looks like, without installing anything | [Read a sample report](#read-a-sample-report) |
| Check the connection you are using now | [Run the first check](#check-your-connection) |
| Find out how to test two streams at once | [Read the dual-stream case (Chinese)](docs/us-dual-rtmp-2026-11-16.md) |
| Prepare firmware or flash an RG-X60 PRO | [Open the model-specific guides](#rg-x60-pro-firmware) |

## Check your connection

### 1. Try the offline example

On macOS or Linux, open a terminal and check that you have Python 3.10 or newer. The tools use Python's standard library.

```sh
python3 --version
```

If you have Git, clone the project and enter its folder.

```sh
git clone https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics.git
cd openwrt-vps-streaming-diagnostics
```

You can also choose **Code → Download ZIP** on GitHub, extract it, and open a terminal in the extracted folder. Run the example from the folder that contains `tools/`.

```sh
python3 tools/quick-check.py
```

The example uses built-in data and sends no test requests. The command prints a Chinese report. [Read the English explanation below](#read-a-sample-report) or add `--json` for structured output with English field names.

### 2. Send a small live check

Live checks also require curl 8.4 or newer. Check your version and preview the request budget.

```sh
curl --version
python3 tools/quick-check.py --plan
```

When you are ready to send requests, run the live check.

```sh
python3 tools/quick-check.py --execute
```

`--execute` sends up to three HTTPS requests over the computer's current IPv4 route. Each request has a five-second time limit and a 64 KiB response body budget. The [beginner guide (Chinese)](docs/beginner-check.md) covers the default target, saving results, and the optional exact-size download.

## Read a sample report

These numbers come from the offline example.

| What the report shows | What happened in the example |
|---|---|
| Small HTTPS requests completed 3 of 3 | All three simulated requests count as complete. |
| Fixed-size downloads completed 1 of 2 | One simulated transfer gets the full 1 MiB. The other gets 256 KiB before the 15-second limit and counts as incomplete. |

[Full example and error explanations (Chinese)](docs/result-examples.md) · [Sample JSON](examples/quick-check-demo.json)

## What each test tells you

| Result | What you can conclude |
|---|---|
| A small HTTPS request completes | Your computer reached that test site at that time. Check the specific site or app if the problem continues. |
| A fixed-size download finishes | The transfer received every expected byte within the time limit. A partial timeout counts as an incomplete attempt, even with HTTP 200. |
| Two streams reach the receiver for the full run | The tested route carried both streams at the recorded bitrate and duration. Phone and platform behavior need their own tests. |

## Real cases by symptom

| Symptom | What the case found |
|---|---|
| Wi-Fi drops immediately after joining | All 15 Australian Wi-Fi groups obtained an IP address and reached the expected exit after the repair. [Wi-Fi repair (Chinese)](docs/au-wifi-association-2026-11-11.md) |
| I need to know whether two streams will hold up | On the U.S. route, two streams each averaged 4.19 Mbps and delivered all 36,000 frames over 20 minutes and 2 seconds. One computer sent both streams to a private receiver. Two phones and public streaming platforms still need testing. [Dual-stream case, November 16 (Chinese)](docs/us-dual-rtmp-2026-11-16.md) · [JSON results](examples/2026-11-16-us-dual-rtmp.json) |
| A download receives data but keeps timing out | The case keeps the partial timeout in the results and checks which transfers completed when retested. [Download timeout follow-up (Chinese)](docs/au-group-12-followup-2026-10-21.md) |

Each case records the route and conditions used at the time. [Case index (Chinese)](docs/cases.md) · [Latest recorded results (Chinese)](docs/latest-progress.md)

## RG-X60 PRO firmware

Follow the guide that matches your hardware. The first-flash case covers the V2.00 hardware revision starting from stock firmware.

- [Download and verify the right firmware files (Chinese)](docs/x60-pro-firmware-preparation.md)
- [Follow the tested V2.00 stock-to-Kwrt first flash (Chinese)](docs/x60-pro-stock-to-kwrt-v2.md)
- [Review problems seen during flashing and how they were resolved (Chinese)](docs/x60-pro-flashing-troubleshooting.md)

## Go deeper

- [Measurement guide (Chinese)](docs/measurement-guide.md) and [decision tree (Chinese)](docs/decision-tree.md) for checking the router, server, and specific destination.
- [Experiment card (Chinese)](docs/experiment-card.md) and [verification and rollback (Chinese)](docs/acceptance-and-rollback.md) for comparing one change and checking its effects.
- [Handoff guides for AU (Chinese)](docs/au-agent-prompt.md), [US-new (Chinese)](docs/us-new-agent-prompt.md), and [CA (Chinese)](docs/ca-agent-prompt.md) for continuing an existing investigation.

When you share results, include the number of complete and attempted checks, the conditions, and the failures you saw. Keep credentials, actual network names, addresses, and raw logs private. [Privacy guidance](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [MIT License](LICENSE)

[![Offline verification](https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml/badge.svg)](https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml)
