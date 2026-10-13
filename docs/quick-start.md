# 15 分钟入门：先得到一份可信的排查计划

[中文首页](../README.md) · [English](../README.en.md) · [最新进度](latest-progress.md)

这 15 分钟用于理解输出、确认测试对象和准备只读采集，**不是保证 15 分钟定位根因**。按一条主线路开始；暂时没有真实手机时，把手机直播明确留为待验收。

| 预算 | 完成什么 |
|---|---|
| 0–3 分钟 | 获取仓库，离线看一次包含失败的合成结果 |
| 3–6 分钟 | 预览测试计划，理解完整对象与预算 |
| 6–10 分钟 | 核对接入、来源、SSH 别名、目标与恢复入口 |
| 10–15 分钟 | 准备两端只读快照，判断是否具备实际测试条件 |

## 1. 先看输出，不给网络加负载

需要 Python 3.10+。下载测试实际执行时另需 curl 8.4+；不需要安装 pip 依赖。

```sh
git clone https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics.git
cd openwrt-vps-streaming-diagnostics
python3 tools/summarize.py examples/synthetic-downloads.jsonl
```

预期看到：**3 次尝试、2 次完整、1 次部分超时**。中位完成时间与任务 goodput 只使用完整对象；失败仍在尝试分母中。这个例子只读本地合成文件，没有发出测速请求。

成功不是“收到了几 MB”或“显示一个很快的速率”。实际固定对象测试要求 curl 退出 0、HTTP 200、精确字节数匹配，以及所要求的来源核对通过。超时下载了一部分仍是失败。

## 2. 预览计划，确认没有真的测速

以下地址和域名是文档保留示例，**只可用于这个 dry-run**：

```sh
python3 tools/download-test.py \
  --url https://download.example.invalid/fixed-10mb.bin \
  --source 192.0.2.10 --bytes 10000000 --repeat 5 --timeout 90 \
  --object-id demo-10MB --group demo-A0 --dry-run

sh tools/snapshot.sh --port 8443 --dry-run
```

下载计划的对象预算为 5 × 10,000,000 字节，单次最大 90 秒；协议与重传开销另计。`--dry-run` 的 `network_requests` 应为 0。它不会发请求、读取实时设备指标或测出速度；快照 dry-run 也只是列出将读取的项目。

**不要直接删掉上述命令的 `--dry-run`。** 示例域名、来源地址和 8443 业务端口都没有代表你的环境。

## 3. 写清楚这次测的是哪条连接

先核对下面五项；已经能从设备和配置中查到的信息，不必重复猜测：

- **测试角色**：哪台客户端、哪个接入组、预期走哪条节点。
- **实际来源**：目标接口当前取得的 IPv4；不要把管理网段地址当作测试网段来源。
- **目标对象**：优先使用自己控制的无凭据 HTTPS 文件，精确大小已知且预期返回 200；公共接口只用于初筛。
- **两端管理**：沿用已经能登录的路由器和 VPS SSH 别名；另有本地管理或云控制台恢复入口。
- **当前业务**：知道是否有直播或下载正在进行，避免叠加未知负载。

业务端口与 SSH 端口是两件事。系统默认 BBR、一次出口查询或服务进程运行，都不足以证明测试连接的发送端算法和精确代理映射。源绑定也不会自动证明 DNS 同路；需要结合实际连接及字节变化复核。

## 4. 建立私有结果目录，准备只读快照

```sh
umask 077
mkdir -p results/session-A0
chmod 700 results results/session-A0
```

`results/` 已被 Git 忽略。原始快照可能含地址、进程与 socket 标识，只保存在这个私有目录；完整配置备份可能含密码和节点凭据，使用原有管理流程另存私密位置，不能作为 GitHub 附件。

下面的空值刻意使片段在发起 SSH 前停止。**填写你已经验证的别名和实际业务端口后再执行**，不猜地址、不安装缺失工具：

```sh
(
  set -e
  ROUTER=''
  VPS=''
  BUSINESS_PORT=''
  : "${ROUTER:?填写已能登录的路由器 SSH 别名}"
  : "${VPS:?填写已能登录的 VPS SSH 别名}"
  : "${BUSINESS_PORT:?填写实际代理业务端口}"
  case "$BUSINESS_PORT" in
    *[!0-9]*) printf '%s\n' '业务端口必须为数值' >&2; exit 2 ;;
  esac
  [ "$BUSINESS_PORT" -ge 1 ] && [ "$BUSINESS_PORT" -le 65535 ] || exit 2
  ssh "$ROUTER" sh -s -- --port "$BUSINESS_PORT" \
    < tools/snapshot.sh > results/session-A0/router-before.txt
  ssh "$VPS" sh -s -- --port "$BUSINESS_PORT" \
    < tools/snapshot.sh > results/session-A0/vps-before.txt
)
```

快照不调整 sysctl、队列、防火墙或代理配置，不会保存完整配置备份。缺少 `ss`、`tc` 等项目会显示不可用；缺测不能当作零错误。结束标记说明采集流程结束，不保证每项指标都可用。

## 5. 入门之后，再建立真实基线

以下片段仍只打印计划。空值需要替换为实际来源和自己的固定对象 URL；对象大小示例是 10,000,000 字节，若你的文件不同，要同时修改 `--bytes` 和对象标签：

```sh
(
  SOURCE_IP=''
  TEST_URL=''
  : "${SOURCE_IP:?填写测试接口当前的 IPv4}"
  : "${TEST_URL:?填写无凭据的固定 HTTPS 对象 URL}"
  python3 tools/download-test.py \
    --url "$TEST_URL" --source "$SOURCE_IP" --bytes 10000000 \
    --repeat 5 --timeout 90 --object-id fixed-10MB-v1 --group A0 --dry-run
)
```

确认对象、来源、流量预算和业务时段后，按 [采集与测量指南](measurement-guide.md) 去掉**自己填写后的命令**的 `--dry-run`，将输出重定向到 `results/session-A0/A0-download.jsonl`；不要执行上面的文档保留示例。使用新文件名保留每组成功与失败，再离线汇总：

```sh
python3 tools/summarize.py results/session-A0/A0-download.jsonl \
  > results/session-A0/A0-summary.json
```

工具没有默认给生产线路设置 20 Mbps 限速。受限上传工具的 `--mbps` 是每条测试流的目标上限，不能当作线路最大能力。HTTP 403、429、挑战页、大小不符和超时分别记录；遇到限流遵守服务响应，不连续重试来“找一个成功样本”。

## 接下来该读哪一页

| 当前需要 | 入口 |
|---|---|
| 连通性与慢速分层定位 | [决策树](decision-tree.md) |
| 用半天完成一项有证据的调查 | [八小时手册](eight-hour-playbook.md) |
| 已有明确候选改动 | [单项实验卡](experiment-card.md) |
| 准备宣布业务稳定 | [验收与恢复](acceptance-and-rollback.md) |
| 给其他 Agent 交接 | [最新进度](latest-progress.md) + [机器可读摘要](../examples/2026-10-13-six-group-speed-summary.json) |

最新记录中 CF 六组为 **73/84**，独立 OVH 下载 **42/42**，US 单独上传复核 **7/7**；这些不同批次各自保留。后续完成不抹掉前面的拒绝和间歇超时，US 延迟问题及真实手机直播仍待验收。新节点应重建自己的基线，不能照搬历史速度或参数。

公开反馈只提交人工脱敏的症状、计数、条件和结论。密码、私钥、完整分享链接、真实地址、SSID、MAC、完整配置与原始日志继续留在本地；详见 [公开边界](../SECURITY.md)。
