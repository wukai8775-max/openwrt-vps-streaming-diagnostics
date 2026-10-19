# US-new round 3: passive VPS evidence

> Public snapshot: 2026-10-19; network identifiers use role labels. Original configurations, addresses, credentials and raw evidence remain private. Read [the handoff and experiment ledger](index.md) for the final decision.

Observed on 2026-10-19. This report contains no server addresses, client addresses, credentials, or node identifiers. The VPS configuration and system parameters were read only throughout this round.

## Scope and capture integrity

- The formal independent collector ran from 09:01:36.269 to 09:04:36.269 UTC, exactly 180 seconds. All 90 samples were available and both the metadata and `collector_end` records were present.
- It selected only established TCP sockets belonging to the actual US-new Xray service PID. It captured the inbound local-443 leg and the outbound remote-443 leg, with anonymous per-capture flow IDs and origin IP groups. Addresses were used only in process memory and were never emitted.
- The earlier 08:59 preparation collector is excluded from the formal evidence. Both preparation and formal collectors and their independent timeout supervisors were absent at the final process check.
- All workload phases, 09:02:16.154–09:03:54.486 UTC, fell inside the formal VPS capture and the separate formal router capture. The workload agent reported 12/12 complete data requests, including every attempted request in the denominator.
- The actual service process identity and configuration hash remained unchanged at both ends. Actual large sockets used CUBIC.

The VPS retained `tcp_rmem=4096 131072 3141312`, `tcp_wmem=4096 16384 3141312`, `tcp_mem=4599 6135 9198`, default CUBIC, and default fq_codel. The router retained its original receive vector `4096 131072 3916736`. No production service restart or sysctl change was performed by the VPS collector.

## Body-transfer observations

These flow assignments use phase times and approximately 25 MB or 75 MB of transferred data. They do not classify flows by the shared NAT source IP. Background small flows are excluded.

| Phase / anonymous outer flow | Observed RTT | Maximum sender-visible receive window | Receive-window limiting reported | Send-buffer limiting reported | Notes |
| --- | --- | ---: | --- | --- | --- |
| Router CF first fresh, flow-113 | 185–224 ms | 1,329,600 B | 8.3% at one reported sample | Field absent | About 25 MB sent during capture |
| Router CF second fresh, flow-160 | 197–219 ms | 1,328,256 B | 4.8–62.0% among reported samples | Field absent | About 25 MB sent during capture |
| Router CF three-request group, flow-190 | 192–259 ms | 1,329,600 B | 1.5–36.4% among reported samples | Field absent | About 75 MB; includes the group's initial new connection and two reused requests |
| Router Google, flow-410 | 235–247 ms | 1,283,776 B | 16.6–29.3% among reported samples | Field absent | About 25 MB; captured retrans cumulative 0/1, with no observed increment |
| Mac direct CF fresh, flow-481 | 233–254 ms | 3,041,344 B | Field absent | Field absent | Observed retransmitted-byte increment 782,520 B |
| Mac direct CF group, flow-523 | 217–302 ms | 4,194,240 B | 1.6–6.8% among reported samples | Field absent | Observed retransmitted-byte increment 1,626,052 B |
| Mac direct Google, flow-607 | 200–232 ms | 4,194,240 B | 13.9–24.5% among reported samples | 46 ms / 1.1% at one sample | About 25 MB |

The outer send-buffer accounting limit reached 3,141,312 B. A buffer reaching its allowed size or a nonempty SendQ does not by itself prove that this send-buffer limit is the active bottleneck. In this round the router-path large sockets did not report `sndbuf_limited`, unlike the earlier experiment conducted with a different, enlarged router receive ceiling. That earlier sender-limit observation must not be reused as evidence for the current original-router configuration.

The CF origin connections in both paths had the same anonymous destination group, `origin-18`; Google used `origin-36` in both paths. This agrees with the workload agent's fixed destination IPv4 and object checks. For the large origin download flows, observed RecvQ peaks were about 2.5–2.9 MB while the outer connection was still sending. This supports downstream/backpressure participation during those sampled body-transfer periods: data had already reached the VPS and was waiting to be drained. It does not establish the cause of all startup/TTFB delays or rule out every transient origin delay.

## Resources

- CPU idle median 97.494%; steal maximum 0.253%; iowait maximum 0.254% across the sampled intervals.
- IO pressure avg10/avg60/avg300 remained 0.00 throughout.
- Memory pressure averages remained 0.00. A few dozen microseconds were added to cumulative pressure totals; these are not substantial sustained pressure.
- Minimum available memory was 240,744 KiB.
- The same service PID and configuration hash remained in place for the entire capture.

## Decision supported by these observations

Do **not** start a VPS `tcp_wmem` maximum-increase experiment on the basis of the prior enlarged-router experiment. The current original-router baseline does not reproduce the previously reported material sender-buffer limiting. Current evidence more directly shows a small receiver window participating on the router path, plus path-dependent startup and retransmission variability. The Mac direct comparison had larger receive windows and faster reused transfers but also a slower fresh CF transfer with observed retransmission, so this single sequential comparison cannot prove that moving the proxy or changing one buffer will produce a general improvement.

Keep this round's unchanged VPS configuration. Any additional experiment needs a new, separately justified hypothesis and its own complete-request and multi-target acceptance gate. The previous router 16 MiB ceiling failed the Google acceptance gate; the present observations do not overturn that negative result.

## Interpretation limits

- This is one sequential workload block, not randomized or repeated A/B evidence.
- Sampling is every approximately two seconds. Short-lived states and connections may fall between samples. Flow counter differences are observed intervals, not exact complete-request wire accounting.
- Missing kernel fields remain missing. An absent `bytes_retrans`, `rwnd_limited`, or `sndbuf_limited` field is not presented as a measured zero.
- `app_limited` on the VPS origin socket concerns that socket's sending side and cannot identify the download bottleneck by itself.
- Instantaneous delivery/pacing rates are not whole-request goodput. Completion rate, exact object bytes, and complete transaction time remain the workload result.
- A temporary single-source forwarding exception enabled only the Mac comparison. The router agent owns its exact removal and cleanup verification; its cleanup state is not asserted by this VPS report.

Raw anonymous captures and process-exit receipts are retained in the protected local round3 evidence directory, outside Git. The collector sources in this directory contain no credentials.
