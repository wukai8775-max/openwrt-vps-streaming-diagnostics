# 八小时执行手册

目标是完成**一条主线路、一次有效定位、最多一项配置实验、一次完整验收与交接**。八小时是上限安排，不是必须运行测试八小时。若已有配置满足需求且没有候选改动，就保留现状，提前转入稳定性验收。

本仓库工具用于采集和受限测试，不自动写入 sysctl、替换 qdisc、修改防火墙或调整 Xray 配置。配置实验由执行者在已有授权及可恢复条件下单独完成。

## 时间安排

| 时间 | 工作 | 退出条件 |
| --- | --- | --- |
| 00:00–00:45 | 确认入口、私有备份和两端快照 | 明确设备、方向与路径，能恢复 |
| 00:45–02:00 | 固定对象和当前业务基线 | 至少五次，成功和失败全记录 |
| 02:00–03:30 | 分开测试本地、受控跨境 TCP、VPS 到目标、完整代理 | 主要限制缩小到一层；记录无法执行的分支 |
| 03:30–04:00 | 选一个有证据的假设 | 填完实验卡；没有候选则保留当前配置 |
| 04:00–05:30 | 最多执行一项小范围实验 | 确认目标流量实际使用候选状态，具备回滚证据 |
| 05:30–07:15 | 对照复测、持续负载和真实业务 | 决定保留、回滚或不确定；5.5 小时后不开始新改动 |
| 07:15–08:00 | 清理、结束快照、交接 | 系统可用，临时入口处理完，恢复步骤可执行 |

## 1. 确认对象并保存现场

先使用已经能登录的 SSH 别名，保留路由器本地管理和 VPS 控制台。不要猜管理地址、账户或端口。备份可能含节点与无线凭据，放在私有目录，限制访问；它不属于普通诊断附件或 GitHub issue。

在本地建立独立结果目录，后续使用新文件名保存每组，避免覆盖：

```sh
umask 077
mkdir -p results/session
chmod 700 results results/session
ROUTER='your-existing-router-ssh-alias'
VPS='your-existing-vps-ssh-alias'
```

填写实际代理业务端口后采集两端快照，不安装缺失工具。以下 `BUSINESS_PORT` 必须替换为数值端口；它是待观察的业务端口，不是 SSH 管理端口：

```sh
BUSINESS_PORT='replace-with-node-business-port'
ssh "$ROUTER" sh -s -- --port "$BUSINESS_PORT" \
  < tools/snapshot.sh > results/session/router-before.txt
ssh "$VPS" sh -s -- --port "$BUSINESS_PORT" \
  < tools/snapshot.sh > results/session/vps-before.txt
```

快照读取内核、拥塞控制、实际队列、计数器和工具版本。缺少工具应记录为缺失，不是零错误或零丢包。字段说明与可选接口筛选见 [README](../README.md)。

测试前核对客户端接入和来源。可将出口检查用作辅助，但必须同时核对下载时的连接和字节变化。`curl --noproxy '*'` 只禁用 curl 的显式代理，透明代理仍可能接管流量。`--interface` 可限制传输使用的接口/地址，但不会单独保证 DNS 的来源路径。[curl 官方说明](https://curl.se/docs/manpage.html)。

## 2. 固定一个对象，建立完整业务基线

优先选自己控制的固定大小 HTTPS 对象。下面域名和来源是必须替换的占位符，下载对象需要返回 200 和精确的预期字节数：

```sh
TEST_URL='https://download.example.test/fixed-10mb.bin'
SOURCE_IP='replace-with-test-interface-ipv4'

python3 tools/download-test.py \
  --url "$TEST_URL" --bytes 10000000 --source "$SOURCE_IP" \
  --object-id fixed-10mb-v1 --group A0 --repeat 5 --timeout 90 --dry-run

python3 tools/download-test.py \
  --url "$TEST_URL" --bytes 10000000 --source "$SOURCE_IP" \
  --object-id fixed-10mb-v1 --group A0 --repeat 5 --timeout 90 \
  > results/session/A0-download.jsonl
```

绑定接口的方式和可选目标 IPv4 固定方法见 README。实际执行前检查 dry-run 输出、流量预算和目的地。`--object-id` 是执行者为精确对象填写的安全标签；只有相同对象和 URL 查询参数才沿用同一标签，分组用 `A0` / `B0` 等区分配置。公共测速接口只能作为初筛：限流、目标变化、异常页面都可能影响结果，不能作为唯一证据。

超时收到了一部分，属于失败。若大对象全部超时，保留原组，再建立较小对象组。后续比较沿用相同大小和期限，不能把 1 MB 与 10 MB 的任务时间混在一起。

同时在另外两个终端开启两端采样，变量需要在每个终端重新设置：

```sh
# 路由器终端：2 秒一次，共 300 次，配置预算约 10 分钟，命令开销另计。
ssh "$ROUTER" sh -s -- --port "$BUSINESS_PORT" --count 300 --interval 2 \
  < tools/sample.sh > results/session/router-A0-sample.txt

# VPS 终端：相同条件。
ssh "$VPS" sh -s -- --port "$BUSINESS_PORT" --count 300 --interval 2 \
  < tools/sample.sh > results/session/vps-A0-sample.txt
```

采样期间不叠加其他大流量。先看任务完成率和完整任务时间，再看 socket、资源和计数增量。系统重传计数不能直接变成某条代理连接的重传率。

## 3. 将几层分别测量

| 测试 | 主要目的 | 判读限制 |
| --- | --- | --- |
| 客户端 ↔ 路由器 | 核对本地接入和端点处理 | ICMP 拒绝不能当成无线丢包 |
| 路由器 ↔ VPS 的受控 TCP | 观察两端间不经实际代理业务处理的传输 | 端口/策略不同，不自动等于代理路径 |
| VPS → 同一个固定对象 | 复核目标和 VPS 出口 | 单一目标快慢都需第二对象补证 |
| 客户端经代理 → 同一个对象 | 检查完整业务 | 与前几项交叉解释，不平均成一个速度 |

受控 TCP 分支需要双方已有 iperf3，以及精确允许测试源的临时入口。准备超过约 20 分钟仍不可行，就标注缺失并跳过，不关闭整个防火墙，也不占用生产业务端口。

以下是通用的手工 iperf3 示例，`VPS_TEST_ADDRESS` 需要替换，TCP 5201 仅作临时测试端口。服务端前台运行 `iperf3 -s -1 -p 5201`；每次 `-1` 服务退出后，下一次需要重新启动。客户端例子：

```sh
# 在测试客户端设置自己的 VPS 测试地址。
VPS_TEST_ADDRESS='replace-with-vps-test-address'

# 下载方向，测试目标上限 20 Mbps。
iperf3 -4 -c "$VPS_TEST_ADDRESS" -p 5201 \
  -P 1 -b 20M -O 5 -t 30 --connect-timeout 5000 -R -J \
  > results/session/iperf-down-1.json

# 服务端重新启动一次性测试入口后，再测上传。
iperf3 -4 -c "$VPS_TEST_ADDRESS" -p 5201 \
  -P 1 -b 20M -O 5 -t 30 --connect-timeout 5000 -J \
  > results/session/iperf-up-1.json
```

执行前核对本机版本和帮助；不同版本可能缺少选项。`-O 5` 的预热仍产生流量，所以该单流示例约 35 秒，按目标速率估计约 87.5 MB 数据另加开销。`--connect-timeout` 只限制初始连接，执行者还应设置独立的总体截止时间并能停止两端进程。20 Mbps 是此测试的目标限制，达到它不能说明线路容量只有 20 Mbps。[iperf3 官方参数](https://software.es.net/iperf/invoking.html)。

## 4. 第四小时之前决定是否做一项实验

填写 [实验记录卡](experiment-card.md)。每项实验都写清怀疑机制、现有证据、唯一变化、实际生效验证和精确恢复步骤。

| 证据方向 | 可选择的一项动作 |
| --- | --- |
| 测试设备走错节点/规则 | 只修正该设备分流，并重建基线 |
| 明确资源竞争 | 只处理一个已识别竞争因素 |
| 需要复核拥塞控制 | 测试 socket 显式比较 `-C cubic` / `-C bbr`，核实实际发送连接 |
| 怀疑包尺寸相关 | 相同 iperf 条件中单独试 `-M 1200`，作为诊断 |
| 只有队列/缓冲区猜测 | 保留现有配置，继续证据采集 |

测试连接的 `-C` / `-M` 不会自动修改 Xray 业务。MSS 降低后改善也不能独自证明 PMTU 黑洞。生产根队列涉及整个接口，默认保留；要将其作为唯一实验，需要已确认真实出口、队列层次、影响流量和精确恢复办法。

不在本轮安排升级内核、换 BBR 版本、切换传输、批量调缓冲区或安装整套监控。抓包只在前面数据无法分类时补证：双端每端最多两分钟或 20,000 包，先到者停止；保留采集丢弃统计，不把它当成链路丢包。

## 5. 验证收益和稳定性

能安全切换时做交错对照，例如 `AB → BA → AB → BA → AB`；每次使用新结果文件，核对实际数据连接。接口级改动影响正在运行的业务时，使用维护窗口一次验证，明确证据限制。

先看失败有没有增加，再看同一对象的完成时间及波动。实验卡中可预先采用 20% 中位数改善等操作门槛，但小样本不等于统计显著。如果没有改善或结果不确定，恢复 A，或保留原配置继续调查。

如有自己控制且能接收 POST 数据的 HTTPS 测试端点，可先执行 upload dry-run，再按真实业务预算运行受限上传：

```sh
UPLOAD_URL='https://upload.example.test/receive'

python3 tools/upload-test.py \
  --url "$UPLOAD_URL" --source "$SOURCE_IP" \
  --object-id upload-receiver-v1 --group selected \
  --flows 3 --duration 600 --mbps 5 --dry-run

python3 tools/upload-test.py \
  --url "$UPLOAD_URL" --source "$SOURCE_IP" \
  --object-id upload-receiver-v1 --group selected \
  --flows 3 --duration 600 --mbps 5 > results/session/selected-upload.jsonl
```

示例合计目标速率约 15 Mbps、流量约 1.1 GB，TLS/TCP 开销另计；它用于测试稳定传输，不测最高容量。自己的上行容量、计费预算或当前业务无法承受时，降低并发、速率与持续时间。影响真实会话时立即停止。

选定配置后再做十次固定对象任务，并测试真实平台的页面、上传、下载与持续会话。没有直播手机时，可以完成合成任务，但把“真实手机/平台直播、目标并发、原故障时段”列为待验收，不能替代宣布通过。

本地汇总保留失败分母：

```sh
python3 tools/summarize.py results/session/*.jsonl \
  > results/session/summary.json
```

汇总输出 JSON；字段说明见 README。成功样本的完成时间和任务有效吞吐单列，不用失败任务的部分速度填进完成样本比较。

## 6. 留足收尾时间

停止本轮的测试、采样和抓包进程，删除仅为本轮新增的精确临时放行规则，再保存结束快照。确认管理和业务仍可用、服务实际配置和持久化状态一致、客户端恢复原来的接入网络。仅由本轮启动的进程才属于清理目标。

交接至少包括：

| 项目 | 写清楚 |
| --- | --- |
| 当前保留状态 | 保留原配置，还是保留哪一项变化；读取核对结果 |
| 实际收益 | 任务完成率、完成时间、有效吞吐和失败分母 |
| 证据范围 | 配置有效、机制旁证或已经独立定位根因 |
| 未确定事项 | 缺少哪段数据、容量或真实业务验收 |
| 恢复方法 | 精确恢复操作、管理入口和验证步骤，敏感详情私有保存 |
| 清理状态 | 测试服务、端口、临时数据、采样、客户端网络 |

公开讨论只分享脱敏摘要。原始 socket、地址、快照、抓包和备份留在私有结果目录，先检查后再决定是否提供个别字段。
