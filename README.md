# OpenWrt / VPS 直播网络排障工具箱

面向 **OpenWrt/Kwrt → PassWall/Xray → Linux VPS → 目标服务** 的慢速、卡顿、超时与高延迟问题。把接入、转发、跨境 TCP、代理处理和目标服务分开验证，再决定保留、修改或回滚。

仓库包含 AU/US 双线路的脱敏案例、可执行的受限测试工具和验收模板。优先目标是直播稳定：**一次只主测一条线，最多做一项有证据的生产改动；没有合理候选时保留现状。**

## 最新进度：2026-10-13 上午

今天 09:44–09:59（北京时间）完成两条实际 Wi-Fi 路径的不限速固定对象测速，**28/28 条传输完整成功，新增生产参数改动 0**。

| 实测项目 | AU | US |
|---|---:|---:|
| 单连接下载，三次中位数 | 21.1 Mbps | 18.3 Mbps |
| 单连接上传，三次中位数 | 29.3 Mbps | 36.8 Mbps |
| 四连接下载总速度，单组 | 29.8 Mbps | 39.2 Mbps |
| 四连接上传总速度，单组 | 57.0 Mbps | 71.3 Mbps |

两条线仍观察到少量秒级 HTTPS 长尾；手机直播、高峰表现及最高容量待验收。完整测试条件、波动范围、响应时间、清理状态与证据限制见 **[最新进度](docs/latest-progress.md)**；Agent 可直接读取 **[机器可读测速摘要](examples/2026-10-13-speed-summary.json)**。这是测量快照，不是实时状态或全天速度保证；原夜间三条 5 Mbps 的限速负载记录仍单独保留。

## 从这里开始

| 你的问题 | 先看哪里 |
|---|---|
| 想知道最新测速、保留状态和待验收项 | [最新进度](docs/latest-progress.md) |
| Wi-Fi 能连接，但国外网站打不开 | [快速定位与误判清单](docs/decision-tree.md) |
| 能打开，下载很慢或小请求突然卡住 | 按下面四步采集，再查 [案例](docs/case-study.md) |
| 想复现之前做了哪些修复和参数优化 | [AU/US 历史案例](docs/case-study.md) |
| 有半天时间，想做一次有效定位 | [八小时执行手册](docs/eight-hour-playbook.md) |
| 准备改参数 | 先填 [单项实验卡](docs/experiment-card.md) |
| 准备宣布直播问题解决 | [验收与恢复](docs/acceptance-and-rollback.md) |

## 快速开始：先获得可比较的证据

客户端需要 **Python 3.10+、curl 8.4+**，不需要 pip 安装依赖。Linux/OpenWrt 两端快照只需要 POSIX shell；`ss`、`tc` 等缺少时会明确标为不可用。旧 curl 不会静默取消大小保护。

```sh
git clone https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics.git
cd openwrt-vps-streaming-diagnostics
python3 -m unittest discover -s tests -v
python3 tools/summarize.py examples/synthetic-downloads.jsonl
umask 077
mkdir -p results
```

合成示例应显示 3 次尝试、2 次完整、1 次部分超时。它只演示失败分母与完整样本统计，没有发起网络请求。[机器可读历史案例](examples/case-summary.json) 则是独立格式的人工脱敏摘要，不是新工具的输出。

**示例中的 SSH 别名、源地址、端点和端口都要换成自己的。** `192.0.2.10` / `203.0.113.20` 是文档保留地址，不能用于真实测试。SSH 使用已经正常工作的系统认证，不向脚本提供密码或私钥内容。

### 1. 确认对象，保存两端只读快照

通过系统网络设置或现有接入工具，确认测试设备连接的是目标 SSID/网段。记录它实际获得的 IPv4，沿用可登录的 SSH 别名。业务端口与 SSH 端口不同。

```sh
ROUTER='your-router-alias'
VPS='your-vps-alias'

ssh "$ROUTER" 'sh -s -- --port 8443' < tools/snapshot.sh > results/router-before.txt
ssh "$VPS" 'sh -s -- --port 8443' < tools/snapshot.sh > results/vps-before.txt
```

以上 `8443` 是示例业务端口，要在所有相关 SSH 命令中替换为实际端口。

同步下载期间，另开两个终端采样。各终端重新设置对应的 SSH 别名：

```sh
ssh "$ROUTER" 'sh -s -- --port 8443 --count 300 --interval 2' \
  < tools/sample.sh > results/router-sample.txt
ssh "$VPS" 'sh -s -- --port 8443 --count 300 --interval 2' \
  < tools/sample.sh > results/vps-sample.txt
```

核对目标业务连接及其流量变化。**默认 BBR、监听 socket 或出口 IP，单独都不足以证明实际下载发送连接正在使用 BBR。** 查看活动发送 socket 的算法、RTT、cwnd、重传与队列。完整配置备份另走你已有的管理流程，保存在私密位置；快照工具不会备份配置。

采样的 600 秒上限是 `count × interval` 配置预算，采集命令会增加耗时，不是进程硬截止时间。完整结束标记仅说明采集流程走完；缺失指标仍属不可用。系统 counters 需要增量比较，不能直接换算成某条代理连接的丢包率。

### 2. 固定对象，完整测五次

优先使用自己控制的、已知精确大小的 HTTPS 文件。没有自控对象时，可用下面的公共接口初筛；限流、挑战页、非 200 或大小不符都要记录，换对象后重建基线。

```sh
SOURCE='192.0.2.10'
TEST_URL='https://speed.cloudflare.com/__down?bytes=10000000'

python3 tools/download-test.py --url "$TEST_URL" --bytes 10000000 \
  --source "$SOURCE" --repeat 5 --object-id fixed-10MB --group A0 --dry-run

# 确认计划和流量预算后，去掉 --dry-run 实际执行。
python3 tools/download-test.py --url "$TEST_URL" --bytes 10000000 \
  --source "$SOURCE" --repeat 5 --object-id fixed-10MB --group A0 > results/A0.jsonl
python3 tools/summarize.py results/A0.jsonl > results/A0-summary.json
```

每次最大 90 秒，IPv4、HTTP/1.1、TLS 验证、没有重试和重定向。只有 **curl 退出 0 + HTTP 200 + 精确完成全部字节 + 源地址核对通过** 才算完成。失败分母不会被丢掉，部分下载不冒充完整任务吞吐。

`--object-id` 是人工设定的安全对象标签；只有实际 URL/查询、大小和服务语义相同才能沿用它。汇总按对象标签、大小、超时、绑定、目标与限速条件分组；工具不保存完整 URL，也不能替你证明不同 URL 内容一致。没有固定 `--resolve` 时，远端地址变化会提示重建固定目标基线。

`--source` 绑定地址，`--interface` 可替代它强制指定接口；只用接口时，结果的 `local_ipv4` 仍需核实。`--resolve` 可选固定目标 IPv4，同时保留原域名的证书验证。源绑定不保证 DNS 走相同接口；固定 `--resolve` 可减少 DNS/目标变化，但透明代理策略仍要核对。`--noproxy '*'` 只禁用 curl 显式代理。[curl 官方选项说明](https://curl.se/docs/manpage.html#--interface)

### 3. 把本地、跨境、目标侧和完整代理分开

| 独立测试 | 主要检查 |
|---|---|
| 客户端 ↔ 路由器 | 接入质量、接口与本地处理；先核实 ICMP 是否允许 |
| 路由器 ↔ VPS | 两端 TCP 传输；有现成 iperf3 才进入受控测试 |
| VPS → 同一个固定对象 | 目标服务及 VPS 出口是否也慢 |
| 客户端经代理 → 同一对象 | 完整业务路径；与前三层交叉解释 |

不要把四段的速率混成一个平均值。裸 TCP 与 Xray 端口、分流及处理不同；详细 iperf、短抓包和单项实验边界见 [八小时手册](docs/eight-hour-playbook.md)。

### 4. 受限持续上传与小请求回归

选择自己控制、支持 POST 请求体并返回 HTTP 200 的接收端。公共测速接收端可能有限流或使用条款。先从短时间和低负载开始，业务受影响就停止。

```sh
UPLOAD_URL='https://your-controlled-endpoint.example/upload'

python3 tools/upload-test.py --url "$UPLOAD_URL" --source "$SOURCE" \
  --flows 3 --duration 60 --mbps 5 --object-id upload-zero --group load0 --dry-run

python3 tools/upload-test.py --url "$UPLOAD_URL" --source "$SOURCE" \
  --flows 3 --duration 60 --mbps 5 --object-id upload-zero --group load0 > results/load0.jsonl
```

这里的 **5 Mbps 是每条测试流的目标上限**；三条合计约 15 Mbps。工具不会给生产线路设置 15/20 Mbps 限速，也不测线路最大能力。`--duration` 上限 600 秒，启动和收尾开销另计，单组 payload 最多 2 GiB；协议、响应和重传开销另计。`Ctrl-C` 会清理本工具创建的 curl 子进程及临时负载文件。

在另一个终端运行小请求探针。必须替换实际目标 IPv4 和正确的 HTTPS 域名；默认 `/generate_204` 与状态 204 也应与接收端契约一致：

```sh
python3 tools/probe.py https --source "$SOURCE" \
  --server-ip 203.0.113.20 --host your-probe-host.example \
  --path /generate_204 --status 204 --samples 120 --dry-run

python3 tools/probe.py stun --source "$SOURCE" \
  --server-ip 203.0.113.20 --port 3478 --samples 120 --timeout 2.5 --dry-run
```

去掉 `--dry-run` 并分别重定向到私密结果文件才会发起探测。HTTPS 使用固定 IPv4、证书验证、持久连接和整个请求的截止时间，报告冷连接/重连；STUN 为每次请求生成独立事务 ID，忽略过期回复，可用 `--expect-exit` 核对该探针出口。探针超时率是请求指标，不能替代视频包丢失率。[STUN 协议](https://www.rfc-editor.org/rfc/rfc8489.html)

## 这次案例做到哪一步

- AU、US 的 VPS 发送端由 CUBIC 改为 BBR；保留原代理传输与 `fq_codel`。AU 还刷新了旧连接池，确认新发送连接实际使用 BBR。
- 此前修复了隔离网段对路由器本地代理/DNS 重定向端口的阻断。它恢复连通性，与后续 BBR 的吞吐改善分阶段记录。
- 原来 32 MiB 对象在 45 秒预算内超时，调整后的同对象能够完成。案例保留部分失败与完整成功的差别，没有宣称永久固定倍数提速。
- 夜间在保留配置上完成三组约十分钟、三条约 5 Mbps 上行测试，9/9 完成；负载稳态准入窗口的小 HTTPS 1721/1721 成功，STUN 1741/1743 响应。夜间新增生产参数改动 **0**。
- 小流长尾与部分代理 TCP 重传恢复相关；具体损伤位置、全部超时原因、实际手机直播及高峰表现仍未证明。

上述是 **2026-10-13 上午测速前的历史阶段记录**，完整数值及当时决定见 [脱敏案例](docs/case-study.md)。后续不限速测速、最新清理状态和当前证据缺口见 [最新进度](docs/latest-progress.md)；仓库不会实时读取设备，后续状态变化需要重新采集。

## 工具与验证范围

| 文件 | 用途 | 会修改生产配置吗 |
|---|---|---|
| `tools/snapshot.sh` | 两端只读快照，缺工具明确报告 | 否 |
| `tools/sample.sh` | 受限时间采样原始 counters、CPU 与目标 socket | 否 |
| `tools/download-test.py` | 精确固定对象完成测试 | 否；会产生受限流量 |
| `tools/upload-test.py` | 有预算的并行 POST 流 | 否；会产生受限流量 |
| `tools/probe.py` | HTTPS / STUN 小请求延迟、超时与重连 | 否；会产生少量流量 |
| `tools/summarize.py` | 离线汇总，完整样本时间与全部失败分母 | 否 |
| `tools/check-publication.py` | 检查已跟踪文件中的常见误提交 | 否；不能替代人工脱敏 |

新工具箱由历史测试逻辑整理、通用化，通用验证使用**离线合成数据、假 curl、假 Linux 命令与 dry-run**；GitHub Actions 仅执行离线测试。上午不限速吞吐由本地专用测速程序测量，仓库 `tools/probe.py` 的 HTTPS 子功能参与了实际小请求测试。这不代表其他公开工具或模式均已生产实测；各项覆盖范围见 [最新进度](docs/latest-progress.md)。

原始配置、SSH 密钥、密码、节点凭据、实际 IP/SSID/MAC、本机路径和完整抓包没有纳入仓库。真实日志也可能含网络标识，请阅读 [公开边界](SECURITY.md)。许可证为 [MIT](LICENSE)。
