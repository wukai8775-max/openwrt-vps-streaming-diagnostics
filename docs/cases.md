# 案例与历史记录

这里集中保存已发表的排查记录。**每一批的成功、失败、回滚和未验收项都保留；后一次成功不会覆盖前一次失败。** 本页不是实时监控。首次使用请先看 [新手诊断入口](beginner-check.md) 和 [结果怎么读](result-examples.md)，再选择与你的症状相符的案例。

公开名称 `AU-main`、`AU-group-N`、`US-main`、`US-new` 都是匿名角色，不是设备上的真实网络名称。**US-main 是旧美国线路，US-new 是另一台 VPS 的新线路，两者不能套用同一结论。** 十五个 AU 分组共享同一上游、出口与带宽，增加接入分组不等于增加十五条独立带宽。

## 先看两个容易误判的结果

| 看到什么 | 能说明什么 | 先看哪份记录 |
|---|---|---|
| HTTP 429 / `Retry-After` | 目标服务明确拒绝或限流；应尊重等待要求，不能直接定性为 TCP 参数错误 | [六组测速原记录](latest-progress.md)中的 CF 拒绝与独立 OVH 复核；[AU 扩展失败账本](au-expansion-2026-10-21.md) |
| HTTP 200，但超时且只收到部分字节 | 请求收到响应，却没有完成固定任务；不能把部分下载速度记为完整任务成功 | [结果示例](result-examples.md)；[AU-group-12 旧超时复核](au-group-12-followup-2026-10-21.md) |

另一目标测试成功，可以支持继续区分目标相关性，不能抹掉原来的 429 或超时。小请求通过不代表容量、手机直播或晚高峰稳定性通过。

## AU：按阶段阅读

| 测量阶段，Asia/Shanghai | 报告与数据 | 最终决定、失败与证据边界 |
|---|---|---|
| 2026-10-21：group-12 下载复查 | [报告](au-group-12-followup-2026-10-21.md) · [JSON](../examples/2026-10-21-au-group-12-followup.json) | **原配置保留，未证明卡顿修复。** group-12 实际 Wi-Fi 下载 2/2，主组交错参照 2/2；原 SOCKS 独立批次 3/3。后续测试入口因内存不足停止；本轮无界 socket 日志约 21.5 MB 的采集缺陷与清理均保留。逐次出口后检存在缺口，短测不覆盖旧失败。 |
| 2026-10-20 至 21：扩展至十五 AU 分组 | [报告](au-expansion-2026-10-21.md) · [JSON](../examples/2026-10-21-au-expansion-summary.json) | **分组配置保留，额外 Xray 池拒绝并回滚。** 新十组最终下载 28/30、上传 30/30；含主组参照的下载负载探针 116/143。短候选改善未通过扩展资源保护；原路径清理前也曾越线，不能把额外池认定为唯一内存或网络根因。应用期间的短时重关联继续保留。 |
| 2026-10-13：早期五 AU 分组与隔离 | [分组验收](segmented-au-acceptance.md) · [六组数据](../examples/2026-10-13-six-group-speed-summary.json) | 独立网段和指定功能/隔离检查通过；应用时旧 US 的五台设备短时重关联后恢复。后续六组 CF 对象流 73/84，独立 OVH 复核 42/42、旧 US 单独上传 7/7；分开统计，不能拼成原批全通过。 |
| 2026-10-13 前后：接入恢复、BBR 与受限负载 | [原始案例](case-study.md) · [早期摘要](../examples/case-summary.json) · [上午测速](../examples/2026-10-13-speed-summary.json) | 修复必要本地输入放行，历史 AU/旧 US 保留已核验的 BBR；AU 刷新旧连接状态。固定任务由部分超时变为完成，但不宣称固定提速倍数。受限合成上传和手机直播验收分开，旧 US 的结论不外推到 US-new。 |

本机在扩展结束时已用满所报告的 5 GHz 16-AP 配额；这是该设备的读回，不能推广为所有 OpenWrt 路由器的上限。硬件、固件及读回日期见 [环境记录](environment.md)。

## US-new：新线路，2026-10-19

统一入口：[接入、三轮排查与最终决定](us-new-2026-10-19/index.md) · [机器交接摘要](../examples/2026-10-19-us-new-handoff.json)。

| 阶段 | 完整记录 | 最终决定与负结果 |
|---|---|---|
| 接入与有限验收 | [接入报告](us-new-2026-10-19/onboarding.md) · [JSON](../examples/2026-10-19-us-new-onboarding-summary.json) | 新线路接入保留。空桥导致初次 DHCP 失败，修复保留；应用曾使 AU 短时重关联。没有与旧 US 做同条件性能 A/B，不能声称改善比例。 |
| 第一轮：带宽、实际拥塞控制、强制接收缓存 | [最终报告](us-new-2026-10-19/round1-throughput.md) · [JSON](../examples/2026-10-19-us-new-round1-summary.json) | **BBR 监听与 `SO_RCVBUFFORCE` 均拒绝并恢复。** BBR 未形成一致收益，强制缓冲出现部分超时，且超时先于自动回滚。VPS 直传可超 100 Mbps，不证明端到端已达到套餐 200 Mbps。 |
| 第二轮：原生自动接收上限 | [最终报告](us-new-2026-10-19/round2-autotune.md) · [JSON](../examples/2026-10-19-us-new-round2-summary.json) · [中途被动快照](us-new-2026-10-19/round2-server-findings.md) | **16 MiB 候选拒绝并恢复。** CF 部分连续对象较快，但 Google 多目标验收恶化。中途快照的“待确认”不能覆盖最终拒绝决定。 |
| 第三轮：同 Wi-Fi 路径与本地下载 | [最终报告](us-new-2026-10-19/round3-bottlenecks.md) · [JSON](../examples/2026-10-19-us-new-round3-summary.json) · [VPS 被动证据](us-new-2026-10-19/round3-server-findings.md) | **保留原生产配置。** 公网请求 12/12、本地无线下载 3/3，535–612 Mbps；移到 Mac 的部分任务较快，但新连接较慢且有重传。没有留下通用 offload 或缓存修复。 |

US-new 保留新 VPS 的原 CUBIC，路由器保留原默认 BBR。未执行的发送缓存、pacing、MSS、qdisc 不能写成“已经试过无效”。手机直播、登录后的办公长会话、晚高峰和多设备持续业务仍待验收。

## US-main：旧美国线路，2026-10-14

| 阶段 | 报告与数据 | 最终决定与边界 |
|---|---|---|
| 三层相同对象诊断 | [报告](us-diagnosis-2026-10-14.md) · [JSON](../examples/2026-10-14-us-diagnosis-summary.json) | **保留配置，未做生产参数 A/B。** VPS、路由器与客户端分层测试共 21/21 完成，路由器路径明显较慢。放宽诊断连接期限扩大了观察范围，不是生产修复，也未定位公网损伤点。 |
| TCP 恢复与短时受限上传 | [报告](us-transport-and-load-2026-10-14.md) · [JSON](../examples/2026-10-14-us-transport-load-summary.json) | **MSS 1200 拒绝、不持久化。** 五对复核原条件 4/5、候选 3/5，候选没有稳定收益。两组约 54 秒的受限上传完成，小请求仍有秒级长尾；未验收真实手机直播。 |

这些记录属于旧节点，不作为新节点的现成参数表。测试中的 5 Mbps、15 Mbps、20 Mbps 等值是相应实验预算，不能直接读成生产线路限速或最高容量。

## Agent 接手与深入排查

接手时先记录当前 `main` 提交 SHA，再按下面顺序读取并核对设备**当前**状态；仓库里的“当时无直播”不代表现在可压测。

1. [最新进度](latest-progress.md)，区分当前快照、历史批次与尚未验收事项。
2. 按目标选 [AU 提示词](au-agent-prompt.md) 或 [US-new 提示词](us-new-agent-prompt.md)，以及该阶段 JSON。
3. [决策树](decision-tree.md) → [单项实验卡](experiment-card.md) → [验收与回滚](acceptance-and-rollback.md)。需要完整时间预算再看 [八小时手册](eight-hour-playbook.md)。

已拒绝候选需要新证据才能重新实验。AU 不重复相同资源预算的额外池、十五套测试端点或持续压已返回 429 的接口；US-new 不直接重复 BBR 监听、强制接收缓存与 16 MiB 上限。真实地址、凭据、完整配置、原始日志和抓包只保留私有材料，公开提交遵循 [SECURITY.md](../SECURITY.md)。
