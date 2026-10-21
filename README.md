<p align="center">
  <img src="assets/banner.svg" alt="OpenWrt / VPS 网络排障工具箱：分层观察接入、路由器、代理与目标服务的原创流程示意" width="100%">
</p>

<p align="center">
  <strong>简体中文</strong> · <a href="README.en.md">English</a> ·
  <a href="docs/quick-start.md">15 分钟入门</a> ·
  <a href="docs/decision-tree.md">排障路径</a> ·
  <a href="docs/latest-progress.md">最新证据</a> ·
  <a href="docs/share-kit.md">分享与 Agent 交接</a>
</p>

<p align="center">
  <a href="https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml"><img src="https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/actions/workflows/ci.yml/badge.svg" alt="Offline verification"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB.svg" alt="Python 3.10 or newer">
</p>

# OpenWrt / VPS 直播网络排障工具箱

面向 **OpenWrt/Kwrt → PassWall/Xray → Linux VPS → 目标服务** 的网络慢、连接超时与直播卡顿。先找到受影响的层，保留每次成功和失败，再决定是否需要一项可恢复的改动。

**从你的症状开始：**

| 你遇到的问题 | 第一份有用的证据 | 入口 |
|---|---|---|
| Wi-Fi 能连接，但代理网站打不开 | 接入、DHCP、DNS、本地代理入口与防火墙分别检查 | [快速定位](docs/decision-tree.md) |
| 已启用 BBR，下载仍然慢 | 固定完整对象、实际发送 socket、两端资源与路径 | [采集与测量](docs/measurement-guide.md) |
| 测速能完成，直播还是卡顿 | 负载下小请求、重连与真实业务持续会话 | [验收与恢复](docs/acceptance-and-rollback.md) |

工具提供只读快照、有预算的传输测试和保留失败分母的离线汇总。它不会自动修改 sysctl、队列、路由或防火墙；实际测速会产生流量，应安排在合适的业务时段。

## 先运行一个离线示例

需要 **Python 3.10+**，不用安装 pip 依赖；实际传输另需 **curl 8.4+**。

```sh
git clone https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics.git
cd openwrt-vps-streaming-diagnostics
python3 tools/summarize.py examples/synthetic-downloads.jsonl
```

预期结果为 **3 次尝试、2 次完整、1 次部分超时**。汇总只读本地合成文件，不联系路由器、VPS 或测速端点；部分下载继续保留为失败。

先预览计划，再准备自己的测试对象：

```sh
python3 tools/download-test.py \
  --url https://download.example.invalid/fixed-10mb.bin \
  --source 192.0.2.10 --bytes 10000000 --repeat 5 --timeout 90 \
  --object-id demo-10MB --group demo-A0 --dry-run
```

这个 dry-run 的 `network_requests` 应为 **0**。域名与来源是文档保留示例，不能直接去掉 `--dry-run` 进行实测。

**下一步：[15 分钟入门](docs/quick-start.md)**，核对设备角色、实际来源、现有 SSH 入口和恢复方法。15 分钟是入门预算，根因定位的时间取决于现有证据。

## 一次调查怎样走完

| 阶段 | 要得到的结果 | 对应资料 |
|---|---|---|
| 观察 | 知道测的是哪条连接、哪个方向，有当前快照 | [采集与测量](docs/measurement-guide.md) |
| 定位 | 把本地接入、代理、跨境 TCP 和目标服务分开 | [决策树](docs/decision-tree.md) |
| 实验 | 一项假设、一项改动、明确生效证据与恢复方法 | [实验卡](docs/experiment-card.md) |
| 验收 | 同条件复测、真实业务回归、清理与交接 | [验收规则](docs/acceptance-and-rollback.md) |

有半天时间时，按 [八小时手册](docs/eight-hour-playbook.md) 完成一条主线路的一次调查。没有合理候选改动，就保留现状，继续收集能够区分原因的证据。

## 最新复查 · 2026-10-21 AU-group-12 下载

**保留原生产配置，当前短测未复现超时，尚未确认根因。** 历史下载负载 27 次超时散布 12/13 个访问，group-12 与邻组归一化配置一致。白天交错 Wi-Fi 下载 **4/4** 完整，负载准入 HTTPS **10/10**；但末次低于下一轮 192 MiB 入口线，未通过完整稳定性验收。全量 socket 观察日志占 tmpfs 约 21.5 MB，已校验归档后回收；随后直接输出到测试机的原 SOCKS 批下载 **3/3**、AU / US-new 小请求各 **8/8**，资源守护通过。没有新增限速、TCP 参数或重启服务；旧超时、采集缺陷及出口后检缺口均保留。

[本轮复查、资源处理与限制](docs/au-group-12-followup-2026-10-21.md) · [机器摘要](examples/2026-10-21-au-group-12-followup.json) · **[最新 AU Agent 提示词](docs/au-agent-prompt.md)**

## 前阶段证据 · 2026-10-21 AU 扩展

**新增 AU-group-6 至 AU-group-15 已保存应用；最终保留原 AU 代理路径，额外独立 Xray 池因资源保护回滚并移除。** 测量窗口为 10 月 20–21 日。新十组最终下载 **28/30**、上传 **30/30**；group-12 下载仅 1/3。包含 AU-main 三个参照的全批下载 35/39、上传 39/39；下载负载小请求 **116/143**、上传 **44/44**，不能称全面稳定。

十五组指定 IPv4 TCP 隔离矩阵 225/225，其中跨组拒绝 210/210；5 GHz 已达本机驱动 16 AP 上限。分组共享 AU 出口和带宽。独立池短测虽改善，扩展未过内存门槛；原路径清理前也触发过资源保护。校验归档后回收约 23.39 MB 诊断 tmpfs 是资源贡献处理，未证明唯一网络根因。真实手机直播、高峰、并发及重启仍待验收，应用阶段短时重关联历史保留。

[完整配置、逐组测速与回滚记录](docs/au-expansion-2026-10-21.md) · [机器可读摘要](examples/2026-10-21-au-expansion-summary.json) · **[给接手 Agent 的完整提示词](docs/au-agent-prompt.md)** · [最新进度](docs/latest-progress.md)

## 前阶段证据 · 2026-10-19 US-new

**新美国线路US-new已接入；三轮性能实验均未保留新参数。** 第一轮拒绝BBR监听和强制接收缓存；第二轮原生16MiB上限虽使CF更快，Google中位数却从34.511降至16.706Mbps，未过多目标门槛。第三轮同Wi-Fi公网请求12/12完成，本地LAN3/3达到535–612Mbps，但Mac独立客户端新连接更慢，不能宣称通用提速。

AU第三轮旁路16/16，测试入口已撤，原配置保留；初次接入曾导致AU组短时重关联的历史也完整保留。真实手机直播、Claude登录后长会话、晚高峰和实际200Mbps容量仍未验收。US-new与下方旧US-main是不同VPS，新VPS保留CUBIC，路由器原默认BBR；不要混用节点结论。

[Agent交接与已试实验表](docs/us-new-2026-10-19/index.md) · [机器可读交接](examples/2026-10-19-us-new-handoff.json) · [第三轮完整报告](docs/us-new-2026-10-19/round3-bottlenecks.md) · [最新进度](docs/latest-progress.md)

**让其他Agent继续排查：[复制完整提示词](docs/us-new-agent-prompt.md)**。先读最新记录，避免无依据重试已拒绝优化，稳定优先并保护AU。

## 历史证据 · 2026-10-14 US-main

**最新决定：保留生产配置，拒绝 MSS 1200。** 后续五对复核中，原条件完成 **4/5**、候选 **3/5**，共同完成对照的候选中位耗时反而慢约 **18.45%**。裸 TCP 单流在 15 Mbps 测试预算下，下行接收约 **4.194 Mbps**、上行约 **14.670 Mbps**；一次约 11 秒的启动已同步观察到外层 TCP 建连与回复恢复迟滞，具体公网位置仍未确定。

实际客户端单流与三流各持续约 **54 秒**，上传 **4/4** 完整，组级有效吞吐约 **4.969 / 14.915 Mbps**。严格负载请求 HTTPS **91/91**、STUN **97/97**，但最大响应仍有 **2.037 / 1.379 秒**，手机直播和晚高峰尚未验收。5 Mbps/流是测试预算，生产改动 **0**。AU 旁路观察 **72/72**、MSS 对照期间 **30/30** 成功，失败历史继续保留。

[后续 TCP 与负载诊断](docs/us-transport-and-load-2026-10-14.md) · [该历史阶段机器结果](examples/2026-10-14-us-transport-load-summary.json) · [最新进度](docs/latest-progress.md)

### 前阶段：顺序分层测量

下面是分别保存的测量快照，仓库不实时监控设备。

| 独立批次 | 完整 / 尝试 | 保留的结论 |
|---|---:|---|
| US VPS 直接下载，两个目标 | **6/6** | 中位数约 54.6 / 86.0 Mbps，服务器到目标较快 |
| 路由器经同一 US 节点直接下载 | **6/6** | 中位数约 4.3 / 8.4 Mbps；绕开 Wi-Fi 后仍偏慢 |
| US 实际接入，两目标下载及 CF 上传 | **9/9** | 下载中位数约 8.5 / 10.4 Mbps，上传约 19.2 Mbps，单次最高 22.7 Mbps |

本轮把主要调查范围缩小到路由器上游、US 代理连接及跨境段；共享 WAN 背景流量、具体公网位置与机制仍未确定。路由器速率采用 curl 全事务耗时，VPS/客户端采用独立墙钟，细微差异不作收益比较。三个层次顺序测试，未改生产参数，也不是参数 A/B。

**US 下载偏慢与秒级连接启动仍有记录；真实手机直播、多组同时直播和高峰表现待验收。** 本轮连接阶段预算为 15 秒，只是诊断条件。已有一次 TLS 启动超过旧 5 秒预算、随后完整下载，不能把放宽测试期限称为修复。2026-10-13 的 CF **73/84**、OVH **42/42**、单独 US 上传 **7/7** 及更早拒绝/超时继续保留，后续成功不抹掉原失败。

[本轮分层诊断](docs/us-diagnosis-2026-10-14.md) · [最新进度与历史结果](docs/latest-progress.md) · [本轮机器可读摘要](examples/2026-10-14-us-diagnosis-summary.json) · [AU 分组与隔离验收](docs/segmented-au-acceptance.md)

## 本案例的路由器与固件

2026-10-14 从设备读回：**锐捷 / Ruijie RG-X60 Pro**，运行 **Kwrt 25.12-SNAPSHOT**；构建标识 `10.08.2026`，Linux 内核 `6.12.112`。完整字段和核验来源见 [环境记录](docs/environment.md)。这是当前运行版本的核对，历史测速日期与结论继续分别保留。

## 工具和实际执行入口

| 工具 | 用途 | 配置修改 |
|---|---|---|
| `tools/snapshot.sh` | 两端只读快照；缺少指标明确报告 | 无 |
| `tools/sample.sh` | 有次数预算的 CPU、计数器、队列与 socket 采样 | 无 |
| `tools/download-test.py` | 固定 HTTPS 对象完成测试，绑定来源并核对精确字节 | 无；产生有预算的流量 |
| `tools/upload-test.py` | 声明负载与流量预算的并行 POST 测试 | 无；产生有预算的流量 |
| `tools/probe.py` | HTTPS / STUN 请求响应、超时与重连 | 无；产生探测流量 |
| `tools/summarize.py` | 离线汇总完整任务及全部失败分母 | 无 |
| `tools/check-publication.py` | 检查暂存文件的常见误提交 | 无；仍需人工脱敏 |

完整对象要求 **退出成功 + HTTP 200 + 精确字节 + 所要求的来源核对**。系统默认 BBR 不代表实际发送连接使用 BBR；一次出口查询也不能证明其他 socket 的精确代理映射。HTTPS 超时率不能替代视频包丢失率，公共端点的拒绝与限流必须单独记录。

### 实际采集与测速

SSH 快照、固定对象、受限上传及小请求的完整命令已集中在 **[采集与测量指南](docs/measurement-guide.md)**。所有实际地址、对象和别名都要换成自己的；原始结果保存在私有 `results/`。

通用验证使用合成数据、假 curl、假 Linux 命令和 dry-run。GitHub Actions 只跑离线检查；实际运行覆盖按工具与模式区分，见 [最新进度](docs/latest-progress.md)。

```sh
python3 -m unittest discover -s tests -v
sh -n tools/snapshot.sh
sh -n tools/sample.sh
python3 tools/check-publication.py
git diff --check
```

## 反馈、复用与分享

- **遇到同类问题：** 用 [脱敏故障表单](https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics/issues/new?template=diagnostic-report.yml) 提交版本、条件、完整成功与失败次数、已做改动和恢复状态。
- **交给其他 Agent：** 先读取本页、[最新进度](docs/latest-progress.md) 和机器可读摘要；核对自己的环境，重建基线，再决定是否干预。[复制交接提示](docs/share-kit.md#给其他-agent-的复制入口)
- **分享给社区：** [中文、英文与技术群分享草稿](docs/share-kit.md)，配 [原创分享封面](assets/social-preview.png)。
- **参与维护：** [贡献指南](CONTRIBUTING.md) · [公开边界](SECURITY.md) · [发布记录](CHANGELOG.md)。

只公开人工审核后的脱敏资料。密码、私钥、完整分享链接、真实地址、SSID、MAC、完整配置和原始日志留在私有位置。

首页参考高关注项目的信息层次和导航，图形与文案为本仓库原创；见 [排版参考与设计说明](docs/design-notes.md)。许可证为 [MIT](LICENSE)。
