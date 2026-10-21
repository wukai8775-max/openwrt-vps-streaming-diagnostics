#!/usr/bin/env python3
"""A small client-only check. The default is a synthetic, offline demonstration.

Python 3.10+; live checks require curl 8.4+. No system settings are changed.
Reports intentionally omit endpoint identities, IPs, interface names and stderr.
"""

import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace


_SPEC = importlib.util.spec_from_file_location("completion_core", Path(__file__).with_name("download-test.py"))
core = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(core)

PROBE_URL = "https://www.gstatic.com/generate_204"
PROBE_BYTES = 64 * 1024
DOWNLOAD_BYTES = 8 * 1024 * 1024
PROBE_COUNT, PROBE_SECONDS = 3, 5
DOWNLOAD_COUNT, DOWNLOAD_SECONDS = 2, 15
METRIC_FIELDS = ("http_status", "received_bytes", "sent_bytes", "total_seconds",
                 "first_byte_seconds", "connect_seconds", "tls_seconds")
MESSAGES = {
    "success": "本次请求符合完成条件；不代表整条线路或直播已通过验收。",
    "dns_failure": "名称解析失败；尚不能判断是本地解析器还是上游原因。",
    "connect_failure": "连接建立失败；检查当前接入和目标可达性。",
    "tls_failure": "TLS 协商或证书校验失败；没有跳过证书验证。",
    "timeout_partial": "已收到部分下载数据但超时；不计成功吞吐。",
    "timeout_unresolved_stage": "请求超时；现有指标不足以确定卡在哪一层。",
    "http_rejected": "目标返回 403 或 429；已停止该分支，避免重复请求。",
    "http_unexpected": "HTTP 状态不符合目标约定；不能当作线路速度结论。",
    "object_size_mismatch": "对象大小不符合约定；已停止下载分支，请核对固定对象。",
    "body_limit": "响应触及安全大小限制；已停止该分支。",
    "metrics_invalid": "没有可验证的完成指标；不计成功。",
    "curl_failure": "请求失败；报告不保留可能包含敏感信息的 curl 错误原文。",
    "launch_failed": "无法启动本轮请求；未继续该分支。",
    "cancelled": "用户取消；仅终止并回收本工具创建的子进程。",
}


class PrivateParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's normal error may echo an invalid URL or unknown credential argument.
        self.print_usage(sys.stderr)
        self.exit(2, "参数无效：请检查模式、HTTPS URL、--bytes（1..8388608）和接口参数；用 --help 查看用法。\n")


def arguments(argv):
    parser = PrivateParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="执行有预算的真实客户端请求")
    mode.add_argument("--demo", action="store_true", help="离线合成示例（默认），不请求网络")
    mode.add_argument("--plan", action="store_true", help="只校验参数并显示计划，不请求网络")
    parser.add_argument("--json", action="store_true", help="只输出一个脱敏 JSON 对象")
    parser.add_argument("--interface", help="可选：强制本地接口；报告不记录名称")
    parser.add_argument("--download-url", help="可选：无凭据的固定大小 HTTPS 对象；不记录 URL")
    parser.add_argument("--bytes", dest="byte_count", type=core.positive_int,
                        help="固定对象精确字节数，1..8388608；与 --download-url 一起使用")
    args = parser.parse_args(argv)
    if bool(args.download_url) != (args.byte_count is not None):
        parser.error("download requires URL and bytes")
    if args.byte_count is not None and args.byte_count > DOWNLOAD_BYTES:
        parser.error("download exceeds budget")
    if args.interface is not None and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", args.interface):
        parser.error("invalid interface")
    if args.download_url:
        try:
            core.validated_url(args.download_url)
        except (ValueError, UnicodeError):
            parser.error("invalid URL")
        if not (args.execute or args.plan):
            parser.error("download options require execute or plan")
    return args


def budget(expected_download_bytes=None):
    count = DOWNLOAD_COUNT if expected_download_bytes is not None else 0
    return {"probe_requests": PROBE_COUNT, "probe_timeout_seconds": PROBE_SECONDS,
            "probe_response_body_limit_bytes": PROBE_BYTES,
            "download_requests": count, "download_timeout_seconds": DOWNLOAD_SECONDS if count else None,
            "maximum_download_object_bytes": expected_download_bytes if count else 0,
            "maximum_response_body_bytes": PROBE_COUNT * PROBE_BYTES + count * (expected_download_bytes or 0),
            "maximum_curl_time_seconds": PROBE_COUNT * PROBE_SECONDS + count * DOWNLOAD_SECONDS,
            "maximum_wall_time_seconds": 5 + PROBE_COUNT * (PROBE_SECONDS + 7) + count * (DOWNLOAD_SECONDS + 7)}


def branch(planned, expected_bytes=None):
    return {"planned": planned, "attempted": 0, "complete": 0, "failed": 0,
            "skipped": planned, "started_child_attempts": 0,
            "expected_bytes": expected_bytes, "attempts": []}


def report(mode, args):
    planned = budget(args.byte_count)
    return {"schema_version": 1, "type": "client_quick_check", "mode": mode,
            "route": "client-current-route", "route_verified": False,
            "binding_mode": "interface_forced" if args.interface else "current_route",
            "interface_name_recorded": False, "synthetic": mode == "demo",
            "overall_status": "planned", "cancelled": False,
            "network_requests": 0, "started_child_attempts": 0,
            "budget": planned, "probe": branch(PROBE_COUNT),
            "download": branch(DOWNLOAD_COUNT, args.byte_count) if args.download_url else None,
            "classifications": {}, "notes": [
                ("强制所选本地接口发送 IPv4 请求；报告不记录接口名，不证明经过任何指定节点或代理。" if args.interface
                 else "只检查系统当前 IPv4 路由；不证明经过任何指定节点或代理。"),
                "started_child_attempts 只计成功启动的 curl 任务；实际网络/HTTP 请求次数未测量，有已启动任务时 network_requests 为 null。",
                "不更改系统配置；不读取服务器凭据；禁用 curl 显式代理和 curlrc，但透明代理仍可能生效。",
                "小请求延迟不是 ICMP 延迟、丢包率或直播稳定性结论；目标或 CDN 也可能影响结果。",
                "默认报告不含 URL、IP、接口名、响应正文、头部或错误原文；分享前仍需人工检查。"]}


def command(args, executable, url, byte_limit, timeout):
    _, endpoint = core.validated_url(url)
    binding = SimpleNamespace(source=None, interface=args.interface or "unused", resolve=None, endpoint=endpoint)
    result = core.curl_base(binding, executable, timeout)
    if not args.interface:
        index = result.index("--interface")
        del result[index:index + 2]
    result[result.index("--output") + 1] = os.devnull
    return result + ["--max-filesize", str(byte_limit), "--url", url]


def classify(metrics, code, error, is_download, complete, outcome):
    if error == "cancelled":
        return "cancelled"
    if error == "curl_launch_failed":
        return "launch_failed"
    if complete:
        return "success"
    if metrics and metrics["http_status"] in (403, 429):
        return "http_rejected"
    if code == 6:
        return "dns_failure"
    if code == 7:
        return "connect_failure"
    if code in (35, 51, 58, 59, 60, 64, 66, 77, 80, 82, 83, 90, 91):
        return "tls_failure"
    if code == 28 or error == "outer_timeout":
        return "timeout_partial" if is_download and metrics and metrics["received_bytes"] else "timeout_unresolved_stage"
    if code == 63:
        return "body_limit"
    if metrics is None:
        return "metrics_invalid" if code == 0 else "curl_failure"
    if code != 0 or error:
        return "curl_failure"
    if metrics["http_status"] != (200 if is_download else 204):
        return "http_unexpected"
    if outcome == "unexpected_object_size" or (not is_download and metrics["received_bytes"]):
        return "object_size_mismatch"
    return "metrics_invalid"


def result(metrics, code, expected_bytes=None, error=None):
    is_download = expected_bytes is not None
    # Fixed object completion and goodput use the same core as the advanced CLI.
    evaluated = core.evaluate_result(metrics, code, expected_bytes, "download", error=error) if is_download else None
    complete = evaluated["completed"] if evaluated else bool(
        not error and code == 0 and metrics and metrics["http_status"] == 204 and metrics["received_bytes"] == 0)
    kind = classify(metrics, code, error, is_download, complete, evaluated["outcome"] if evaluated else None)
    return {"completed": complete, "classification": kind, "process_exit": code,
            "metrics": {key: metrics[key] for key in METRIC_FIELDS} if metrics else None,
            "task_goodput_mbps": evaluated["task_goodput_mbps"] if evaluated else None}


def append(target, row):
    target["attempts"].append(dict(row, attempt=len(target["attempts"]) + 1))
    target["attempted"] += 1
    target["complete"] += int(row["completed"])
    target["failed"] += int(not row["completed"])
    target["skipped"] = target["planned"] - target["attempted"]


def run_branch(target, args, executable, url, limit, timeout):
    for _ in range(target["planned"]):
        child, metrics, code, error = None, None, None, None
        try:
            child = subprocess.Popen(command(args, executable, url, limit, timeout),
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            target["started_child_attempts"] += 1
            stdout, _stderr = child.communicate(timeout=timeout + 3)
            metrics, code = core.parse_metrics(stdout), child.returncode
        except subprocess.TimeoutExpired:
            error = "outer_timeout"
        except KeyboardInterrupt:
            error = "cancelled"
        except OSError:
            error = "curl_launch_failed"
        finally:
            if child is not None:
                core.stop_processes([child])
                if code is None:
                    code = child.returncode
        row = result(metrics, code, target["expected_bytes"], error)
        append(target, row)
        if row["classification"] in ("cancelled", "launch_failed", "http_rejected", "body_limit", "object_size_mismatch"):
            return row["classification"]
        if target["expected_bytes"] is not None and row["classification"] == "http_unexpected":
            break
    return None


def finalize(data):
    rows = data["probe"]["attempts"] + (data["download"]["attempts"] if data["download"] else [])
    data["classifications"] = dict(sorted(Counter(row["classification"] for row in rows).items()))
    if data["mode"] == "demo":
        data["overall_status"] = "example_only"
    elif data["mode"] == "live":
        branches = [data["probe"]] + ([data["download"]] if data["download"] else [])
        data["started_child_attempts"] = sum(item["started_child_attempts"] for item in branches)
        data["network_requests"] = None if data["started_child_attempts"] else 0
        data["overall_status"] = "checks_passed" if all(item["complete"] == item["planned"] for item in branches) else "needs_attention"
        if data["cancelled"] or "cancelled" in data["classifications"]:
            data["cancelled"] = True
            data["overall_status"] = "cancelled"
    return data


def demonstration(args):
    data = report("demo", args)
    data["notes"].insert(0, "这是合成示例，不是实测；没有请求网络。部分下载保留失败分母且没有成功吞吐。")
    for seconds in (0.24, 0.31, 0.27):
        append(data["probe"], result(_example_metrics(0, seconds, 204), 0))
    data["download"] = branch(2, 1024 * 1024)
    data["budget"] = budget(data["download"]["expected_bytes"])
    append(data["download"], result(_example_metrics(1024 * 1024, 1.0, 200), 0, 1024 * 1024))
    append(data["download"], result(_example_metrics(262144, 15.0, 200), 28, 1024 * 1024))
    return finalize(data)


def _example_metrics(byte_count, seconds, status):
    return dict(http_status=status, received_bytes=byte_count, sent_bytes=0, total_seconds=seconds,
                first_byte_seconds=0.20, connect_seconds=0.05, tls_seconds=0.12,
                local_ipv4="", remote_ipv4="")


def render(data, as_json):
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))
        return
    labels = {"demo": "离线合成示例（非实测，无网络请求）", "plan": "离线计划（无网络请求）", "live": "客户端 IPv4 实测"}
    print("客户端入门诊断 · " + labels[data["mode"]])
    print("绑定方式：" + ("强制所选接口（名称不记录）" if data["binding_mode"] == "interface_forced" else "系统当前路由"))
    if data["mode"] == "plan":
        print(f"计划：小请求 {data['budget']['probe_requests']} 次；可选下载 {data['budget']['download_requests']} 次。")
    for key, label in (("probe", "HTTPS 小请求"), ("download", "固定对象下载")):
        item = data[key]
        if item is None:
            continue
        print(f"{label}：成功 {item['complete']}/{item['attempted']}，失败 {item['failed']}，未开始 {item['skipped']}。")
        for row in item["attempts"]:
            timing = row["metrics"]["total_seconds"] if row["metrics"] else None
            speed = row["task_goodput_mbps"]
            detail = (f"，总耗时 {timing:.3f}s" if timing is not None else "")
            if speed is not None:
                detail += f"，完整任务 {speed:.2f} Mbps"
            print(f"  第 {row['attempt']} 次：{row['classification']}{detail}")
    for kind in data["classifications"]:
        print(MESSAGES[kind])
    if data.get("setup_error"):
        print("环境检查未通过：" + data["setup_error"])
    print(f"结果：{data['overall_status']}；已启动请求任务 {data['started_child_attempts']} 个。")
    if data["network_requests"] is None:
        print("实际发送的网络/HTTP 请求次数未知；启动 curl 任务不代表 HTTP 请求已到达目标。")
    for note in data["notes"]:
        print(note)


def main(argv=None):
    args = arguments(argv)
    if not args.execute and not args.plan:
        render(demonstration(args), args.json)
        return 0
    data = report("live" if args.execute else "plan", args)
    if args.plan:
        render(data, args.json)
        return 0
    try:
        core.install_cancel_handlers()
        executable = core.checked_curl()
    except KeyboardInterrupt:
        data["cancelled"] = True
        data["overall_status"] = "cancelled"
        render(data, args.json)
        return 130
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        data["overall_status"] = "setup_failed"
        known = ("curl_not_installed", "curl_8_4_or_newer_required")
        data["setup_error"] = str(error) if isinstance(error, RuntimeError) and str(error) in known else "curl_setup_failed"
        render(data, args.json)
        return 2
    try:
        stopped = run_branch(data["probe"], args, executable, PROBE_URL, PROBE_BYTES, PROBE_SECONDS)
        if data["download"] and stopped not in ("cancelled", "launch_failed"):
            run_branch(data["download"], args, executable, args.download_url, args.byte_count, DOWNLOAD_SECONDS)
    except KeyboardInterrupt:
        # Covers cancellation between branches, where no curl child is active.
        data["cancelled"] = True
    finalize(data)
    render(data, args.json)
    return 130 if data["overall_status"] == "cancelled" else (0 if data["overall_status"] == "checks_passed" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
