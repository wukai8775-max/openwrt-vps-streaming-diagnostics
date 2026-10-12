#!/bin/sh
# Bounded read-only telemetry; preserve raw socket details for actual CA review.
set -u
umask 077

usage() {
    cat <<'EOF'
Usage: sample.sh --port PORT [--count N] [--interval SECONDS] [--interface IFACE] [--dry-run]

Read-only Linux/OpenWrt telemetry on stdout; no test traffic is generated.
Defaults: 30 samples, 2-second interval. Integer intervals only.
Limits: count 1..300, interval 1..60, count * interval <= 600 seconds.
Local command execution adds overhead; this is a configured sampling budget,
not a hard process deadline. Samples contain UTC time and raw /proc/uptime.
The explicit port filters both directions of TCP sockets. Raw ss output is
preserved: inspect the actual sending connection during traffic, not just the
system default or a listener. A leading ss flag such as "ts" is not a CA name.
--interface limits qdisc inspection; /proc counters remain system-wide.
--dry-run prints a single sample plan and does not execute collection commands.
SIGINT/SIGTERM produce an interrupted marker with completed sample count.
Missing tools/files are unavailable, never zero. Protect and redact raw output.
EOF
}
error() { printf 'error: %s\n' "$*" >&2; exit 2; }
port=
interface=
count=30
interval=2
dry_run=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --port|--interface|--count|--interval)
            option=$1
            [ "$#" -ge 2 ] || error "$option requires a value"
            [ -n "$2" ] || error "$option requires a nonempty value"
            case "$option" in
                --port) port=$2 ;;
                --interface) interface=$2 ;;
                --count) count=$2 ;;
                --interval) interval=$2 ;;
            esac
            shift 2 ;;
        --dry-run) dry_run=1; shift ;;
        *) error "unknown argument: $1" ;;
    esac
done
for number in "$port" "$count" "$interval"; do
    case "$number" in *[!0-9]*|'') error 'port, count, and interval must be positive integers' ;; esac
done
[ "$port" -ge 1 ] 2>/dev/null && [ "$port" -le 65535 ] 2>/dev/null || error '--port must be from 1 to 65535'
[ "$count" -ge 1 ] 2>/dev/null && [ "$count" -le 300 ] 2>/dev/null || error '--count must be from 1 to 300'
[ "$interval" -ge 1 ] 2>/dev/null && [ "$interval" -le 60 ] 2>/dev/null || error '--interval must be from 1 to 60'
# Normalize leading zeros using shell builtins before decimal arithmetic.
while [ "${port#0}" != "$port" ]; do port=${port#0}; done
while [ "${count#0}" != "$count" ]; do count=${count#0}; done
while [ "${interval#0}" != "$interval" ]; do interval=${interval#0}; done
[ "$((count * interval))" -le 600 ] || error 'configured sampling budget exceeds 600 seconds'
if [ -n "$interface" ]; then
    case "$interface" in -*|*[!a-zA-Z0-9_.:@-]*) error 'invalid interface name' ;; esac
    [ "${#interface}" -le 64 ] || error 'interface name is too long'
fi

run() {
    label=$1
    shift
    printf '\n--- %s ---\ncommand:' "$label"
    for arg in "$@"; do printf ' [%s]' "$arg"; done
    printf '\n'
    if [ "$dry_run" -eq 1 ]; then printf 'status=planned\n'; return; fi
    if ! command -v "$1" >/dev/null 2>&1; then
        printf 'status=unavailable reason=missing-tool tool=%s\n' "$1"
        return
    fi
    "$@" 2>&1
    result=$?
    if [ "$result" -eq 0 ]; then printf 'status=ok\n'; else printf 'status=failed exit=%s\n' "$result"; fi
}
read_file() {
    printf '\n--- %s ---\n' "$1"
    if [ "$dry_run" -eq 1 ]; then printf 'command: [cat] [%s]\nstatus=planned\n' "$2"; return; fi
    if [ ! -r "$2" ]; then printf 'status=unavailable reason=missing-or-unreadable-file path=%s\n' "$2"; return; fi
    if ! command -v cat >/dev/null 2>&1; then printf 'status=unavailable reason=missing-tool tool=cat\n'; return; fi
    cat "$2"
    result=$?
    if [ "$result" -eq 0 ]; then printf '\nstatus=ok\n'; else printf '\nstatus=failed exit=%s\n' "$result"; fi
}
sample() {
    run time-utc date -u '+%Y-%m-%dT%H:%M:%SZ'
    run time-epoch date '+%s'
    read_file uptime /proc/uptime
    read_file cpu-counters /proc/stat
    read_file cpu-pressure /proc/pressure/cpu
    read_file memory-pressure /proc/pressure/memory
    read_file interface-counters /proc/net/dev
    read_file softnet-counters /proc/net/softnet_stat
    read_file snmp-counters /proc/net/snmp
    read_file extended-tcp-counters /proc/net/netstat
    run tcp-socket-details ss -H -tinp "( sport = :$port or dport = :$port )"
    if [ -n "$interface" ]; then
        run actual-qdisc tc -s qdisc show dev "$interface"
    else
        run actual-qdisc tc -s qdisc show
    fi
}

printf 'collector=sample schema=1 read_only=true requested=%s interval_seconds=%s port=%s\n' "$count" "$interval" "$port"
printf 'privacy=raw-output-may-contain-addresses-and-PIDs\n'
printf 'completion=collection-finished-does-not-imply-every-section-available\n'
printf 'counter_scope=system-wide-not-a-per-connection-loss-rate\n'
printf 'cpu_usage=requires-deltas-between-two-samples-not-first-cumulative-row\n'
completed=0
trap 'printf "\nsampler_end status=interrupted signal=INT samples=%s requested=%s\n" "$completed" "$count"; exit 130' INT
trap 'printf "\nsampler_end status=interrupted signal=TERM samples=%s requested=%s\n" "$completed" "$count"; exit 143' TERM
if [ "$dry_run" -eq 1 ]; then
    sample
    printf '\nsampler_end status=planned samples=0 requested=%s\n' "$count"
    exit 0
fi
if ! command -v uname >/dev/null 2>&1; then error 'uname is unavailable; Linux support cannot be verified'; fi
[ "$(uname -s)" = Linux ] || error 'this collector requires Linux; use SSH to the router/VPS'
while [ "$completed" -lt "$count" ]; do
    printf '\nsample_begin index=%s\n' "$((completed + 1))"
    sample
    completed=$((completed + 1))
    printf '\nsample_end index=%s\n' "$completed"
    if [ "$completed" -lt "$count" ]; then
        if ! command -v sleep >/dev/null 2>&1; then
            printf '\nsampler_end status=failed reason=missing-sleep samples=%s requested=%s\n' "$completed" "$count"
            exit 2
        fi
        sleep "$interval" || { printf '\nsampler_end status=failed reason=sleep-failed samples=%s requested=%s\n' "$completed" "$count"; exit 2; }
    fi
done
printf '\nsampler_end status=complete samples=%s requested=%s\n' "$completed" "$count"
