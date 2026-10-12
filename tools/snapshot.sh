#!/bin/sh
# Read-only Linux/OpenWrt snapshot. Raw output can contain addresses and PIDs.
set -u
umask 077

usage() {
    cat <<'EOF'
Usage: snapshot.sh [--port PORT] [--interface IFACE] [--unit SYSTEMD_UNIT] [--dry-run]

Collect a read-only Linux snapshot on stdout. Redirect it into a protected
results directory. No installation, configuration changes, or network tests
are performed. Socket collection is skipped unless --port is supplied.
--interface limits link, address, and qdisc inspection to that interface.
--unit inspects only basic systemd service state, never service configuration.
--dry-run prints the collection plan without executing any collection command.
Missing tools/files are reported as unavailable, not as zero counters.
EOF
}

error() { printf 'error: %s\n' "$*" >&2; exit 2; }
port=
interface=
unit=
dry_run=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --port|--interface|--unit)
            option=$1
            [ "$#" -ge 2 ] || error "$option requires a value"
            [ -n "$2" ] || error "$option requires a nonempty value"
            case "$option" in
                --port) port=$2 ;;
                --interface) interface=$2 ;;
                --unit) unit=$2 ;;
            esac
            shift 2 ;;
        --dry-run) dry_run=1; shift ;;
        *) error "unknown argument: $1" ;;
    esac
done
if [ -n "$port" ]; then
    case "$port" in *[!0-9]*|'') error '--port must be an integer from 1 to 65535' ;; esac
    [ "$port" -ge 1 ] 2>/dev/null && [ "$port" -le 65535 ] 2>/dev/null || error '--port must be from 1 to 65535'
    while [ "${port#0}" != "$port" ]; do port=${port#0}; done
fi
if [ -n "$interface" ]; then
    case "$interface" in -*|*[!a-zA-Z0-9_.:@-]*) error 'invalid interface name' ;; esac
    [ "${#interface}" -le 64 ] || error 'interface name is too long'
fi
if [ -n "$unit" ]; then
    case "$unit" in -*|*[!a-zA-Z0-9_.:@-]*) error 'invalid systemd unit name' ;; esac
    [ "${#unit}" -le 128 ] || error 'systemd unit name is too long'
fi

section() { printf '\n=== %s ===\n' "$1"; }
run() {
    label=$1
    shift
    section "$label"
    printf 'command:'
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
    section "$1"
    if [ "$dry_run" -eq 1 ]; then printf 'command: [cat] [%s]\nstatus=planned\n' "$2"; return; fi
    if [ ! -r "$2" ]; then printf 'status=unavailable reason=missing-or-unreadable-file path=%s\n' "$2"; return; fi
    if ! command -v cat >/dev/null 2>&1; then printf 'status=unavailable reason=missing-tool tool=cat\n'; return; fi
    cat "$2"
    result=$?
    if [ "$result" -eq 0 ]; then printf '\nstatus=ok\n'; else printf '\nstatus=failed exit=%s\n' "$result"; fi
}

printf 'collector=snapshot schema=1 read_only=true\n'
printf 'privacy=raw-output-may-contain-addresses-and-PIDs\n'
printf 'completion=collection-finished-does-not-imply-every-section-available\n'
if [ "$dry_run" -eq 0 ]; then
    if ! command -v uname >/dev/null 2>&1; then error 'uname is unavailable; Linux support cannot be verified'; fi
    [ "$(uname -s)" = Linux ] || error 'this collector requires Linux; use SSH to the router/VPS'
fi
run time-utc date -u '+%Y-%m-%dT%H:%M:%SZ'
run kernel uname -a
run ip-version ip -V
run ss-version ss -V
run tc-version tc -V

read_file uptime /proc/uptime
read_file cpu-counters /proc/stat
read_file memory /proc/meminfo
read_file cpu-pressure /proc/pressure/cpu
read_file memory-pressure /proc/pressure/memory
read_file io-pressure /proc/pressure/io
read_file tcp-default-congestion-control /proc/sys/net/ipv4/tcp_congestion_control
read_file tcp-available-congestion-control /proc/sys/net/ipv4/tcp_available_congestion_control
read_file default-qdisc /proc/sys/net/core/default_qdisc
read_file tcp-mtu-probing /proc/sys/net/ipv4/tcp_mtu_probing
read_file tcp-ecn /proc/sys/net/ipv4/tcp_ecn
read_file tcp-read-buffer-limits /proc/sys/net/ipv4/tcp_rmem
read_file tcp-write-buffer-limits /proc/sys/net/ipv4/tcp_wmem
read_file core-read-buffer-limit /proc/sys/net/core/rmem_max
read_file core-write-buffer-limit /proc/sys/net/core/wmem_max
read_file interface-counters /proc/net/dev
read_file softnet-counters /proc/net/softnet_stat
read_file snmp-counters /proc/net/snmp
read_file extended-tcp-counters /proc/net/netstat

if [ -n "$interface" ]; then
    run links ip link show dev "$interface"
    run addresses ip address show dev "$interface"
    run actual-qdisc tc -s qdisc show dev "$interface"
else
    run links ip link show
    run addresses ip address show
    run actual-qdisc tc -s qdisc show
fi
run ipv4-routes ip -4 route show table all
run ipv6-routes ip -6 route show table all
run ipv4-policy-rules ip -4 rule show
run ipv6-policy-rules ip -6 rule show
if [ -n "$port" ]; then
    run tcp-listeners ss -H -lntp "( sport = :$port )"
    run tcp-socket-details ss -H -tinp "( sport = :$port or dport = :$port )"
else
    section tcp-sockets
    printf 'status=skipped reason=port-not-specified\n'
fi
if [ -n "$unit" ]; then
    run systemd-service-state systemctl show --property=Id,ActiveState,SubState,MainPID,MemoryCurrent,CPUUsageNSec -- "$unit"
fi
printf '\nsnapshot_end status=complete dry_run=%s\n' "$dry_run"
