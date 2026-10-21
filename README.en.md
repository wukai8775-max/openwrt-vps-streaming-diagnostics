<p align="center">
  <img src="assets/banner.svg" alt="OpenWrt / VPS network diagnostics: measure, isolate, verify" width="100%">
</p>

<p align="center">
  <a href="README.md">简体中文</a> · <strong>English</strong> ·
  <a href="docs/beginner-check.md">Start here</a> ·
  <a href="docs/cases.md">Cases and history</a>
</p>

<p align="center">
  <a href="https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml"><img src="https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml/badge.svg" alt="Offline verification"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB.svg" alt="Python 3.10 or newer">
</p>

# OpenWrt / VPS Network Diagnostics

**Find out what failed before changing network settings.** Start on your own computer, with no SSH access or router credentials. Read a short report, keep incomplete transfers in the failure count, then choose the next layer to inspect.

Useful when:

- **Wi-Fi connects but sites do not load:** begin with bounded HTTPS checks; use the deeper guide to separate access, DNS, proxy and firewall evidence.
- **A download looks fast but never finishes:** verify the HTTP status and exact byte count; partial data is still an incomplete task.
- **Speed tests pass but calls or streams stall:** check small requests under a separately bounded load, then verify the real application.

This toolkit does not install a parameter set or change production settings. A successful short check does not prove capacity, a specific proxy route or livestream stability.

## Try the report without sending traffic

Requires Python 3.10+. No pip dependencies.

```sh
git clone https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics.git
cd openwrt-vps-streaming-diagnostics
python3 tools/quick-check.py
```

The default is an **offline synthetic demonstration**, not a test of your network. It shows why a successful small request and a partially downloaded object need different conclusions. See [result examples](docs/result-examples.md) for explanations and failure counts.

Human-readable CLI output is currently Chinese; `--json` exposes stable field names. An English interpretation is provided below.

## Make a small live check

Requires curl 8.4+. Run this only when a few short requests fit your current network use:

```sh
python3 tools/quick-check.py --execute
```

This explicitly sends up to **three IPv4 HTTPS requests**, each limited to **5 seconds and a 64 KiB response-body budget**. It uses the computer's current route; no SSH login, secrets or manual source address are required. Use `--interface en0` only if you have verified that interface, or `--json` for structured output. Automatic routing does not verify your Wi-Fi group, DNS redirection or proxy-node mapping.

Use `--plan` to preview the budget without sending traffic. For a download, explicitly provide both `--download-url HTTPS_URL` and `--bytes EXACT_SIZE`: at most 8 MiB per object, two attempts, 15 seconds per attempt. Instructions and exact completion rules are in the [beginner guide](docs/beginner-check.md). Do not compare different objects or targets as a parameter A/B.

## Read the result before changing anything

An illustrative interpretation, **not a live measurement**:

```text
Small HTTPS requests: 3/3 complete
Fixed-object downloads: 1/2 complete, 1 partial timeout
The partial request received HTTP 200 but did not receive every byte.
Keep the failure. Compare complete tasks only; do not claim full stability.
```

HTTP **429** means the endpoint refused or rate-limited the request; respect its waiting instructions. It is not enough evidence to change BBR or buffers. A timeout reports a budget exceeded, not the location or cause of a fault. The [result examples](docs/result-examples.md) show what each outcome supports and what it does not.

## Choose the next step

| Need | Open |
|---|---|
| First live check and bounded fixed-object test | [Beginner guide](docs/beginner-check.md) · [Quick-start map](docs/quick-start.md) · [Result examples](docs/result-examples.md) |
| Separate local access, proxy, TCP and target behavior | [Decision tree](docs/decision-tree.md) · [Measurement guide](docs/measurement-guide.md) |
| Plan one reversible experiment and accept it | [Experiment card](docs/experiment-card.md) · [Acceptance and rollback](docs/acceptance-and-rollback.md) |
| Read measured outcomes, failures and rolled-back candidates | [Case index](docs/cases.md) · [Latest progress](docs/latest-progress.md) |
| Hand off an existing investigation to another Agent | [AU prompt](docs/au-agent-prompt.md) · [US-new prompt](docs/us-new-agent-prompt.md) |

Detailed historical narratives are currently in Chinese. Commands and linked JSON summaries can be read independently. **US-new and legacy US-main are different routes.** The case index keeps all stages and final decisions separate; historical BBR gains are not a prescription for a new node.

## Tools for a deeper investigation

| Tool | Purpose |
|---|---|
| `quick-check.py` | Offline first; explicit small live checks and optional exact-size download |
| `download-test.py` / `upload-test.py` | Bounded fixed-object downloads / declared-payload uploads |
| `probe.py` | Bounded HTTPS / STUN request observations |
| `snapshot.sh` / `sample.sh` | Read-only Linux/OpenWrt snapshots and bounded selected metrics |
| `summarize.py` | Offline aggregation that preserves the failure denominator |
| `check-publication.py` | Check tracked files for common accidental disclosures |

All tools are under `tools/`. Actual download tests use the source binding and curl requirements documented by each tool. Collectors use the SSH access you already have. No tool changes sysctl, queues, firewall rules or proxy settings. Traffic-generating tests can still affect shared bandwidth: stop if existing work degrades.

## Keep private evidence private

Do not publish raw reports, addresses, network labels, credentials, full backups, private keys or captures. `results/` is ignored, but review every public artifact manually; see [SECURITY.md](SECURITY.md). A sanitized example is an explanation, not a replacement for private recovery materials.

For reproducible reports, include complete / attempted counts, failures, conditions and what remains unverified. Use the issue templates and rebuild a baseline for each environment; hardware, firmware and paths differ. The [environment record](docs/environment.md) describes the case router, not a universal compatibility claim.

[Contributing](CONTRIBUTING.md) · [Design notes](docs/design-notes.md) · [MIT License](LICENSE)
