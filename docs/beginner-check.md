# 新手诊断：先检查自己的电脑

[首页](../README.md) · [结果怎么读](result-examples.md) · [进阶准备](advanced-start.md) · [案例与历史](cases.md) · [本轮验证](beginner-entry-validation-2026-10-21.md)

这里可以做一次小检查，判断请求在哪一步失败。买来的云服务器和路由器都无需登录。只想先了解报告的人，可以直接打开 [带解释的示例](result-examples.md)。

| 要做什么 | 需要什么 |
|---|---|
| 看示例报告 | macOS 或 Linux 终端，Python 3.10+ |
| 发起轻量网络检查 | 上述环境，另需 curl 8.4+ |
| 获取仓库 | GitHub 的 **Code → Download ZIP**，或已安装的 Git |

在终端运行 `python3 --version` 或 `curl --version` 查看版本。用 ZIP 的读者应先解压。在终端输入 `cd `，保留末尾空格，填入包含 `README.md` 和 `tools/` 的文件夹路径后按回车。使用 Mac 时，可以把文件夹拖进终端来填入路径。

## 1. 先运行离线示例

用 Git 获取仓库时，先执行下面两行。用 ZIP 的读者可以直接跳到运行示例。

```sh
git clone https://github.com/wukai8775-max/openwrt-vps-streaming-diagnostics.git
cd openwrt-vps-streaming-diagnostics
```

```sh
python3 tools/quick-check.py
```

第一行会显示「离线合成示例」。这份报告为你展示如何识别完整任务和部分超时。三次小请求都成功，两次下载只有一次完整，另一轮超时后保留为失败。运行这一步使用的是项目内的演示数据。[结果解释](result-examples.md) · [合成 JSON](../examples/quick-check-demo.json)

## 2. 对自己的网络做一次小检查

先用 `--plan` 查看请求次数和预算。准备就绪后，用 `--execute` 发起请求。

```sh
python3 tools/quick-check.py --plan
```

```sh
python3 tools/quick-check.py --execute
```

默认访问 Google 的公开 HTTPS 地址 `https://www.gstatic.com/generate_204`。这个地址正常返回 HTTP **204**，表示请求完成且响应体为空。若它失败，先按报告定位，并用你能访问的目标做对照。某些网络会限制该地址。

| 默认检查预算 | 数值 |
|---|---:|
| 请求任务 | 最多 3 个，顺序执行，无自动重试 |
| 协议 | IPv4、HTTPS、HTTP/1.1，保留证书校验 |
| 单次请求时间上限 | 5 秒 |
| 单次响应体预算 | 64 KiB，触及时中止该分支 |
| 请求时间预算 | 最多 15 秒；环境检查和进程回收另计 |
| 下载测速文件 | 默认 0 个 |

响应头、加密协商和传输重传使用的流量另计。若检查期间现有业务受到影响，按 `Ctrl+C` 停止。

## 3. 确认检查的是哪条路径

不填接口时，系统选择当前 IPv4 路由。工具禁用 curl 的显式代理和 `.curlrc`；**如果你平时依靠应用里的显式代理，本次路径可能与该应用不同**。透明代理、策略路由和 VPN 仍可能影响请求。

只有确认接口后才指定它，例如在 macOS 常见的 Wi-Fi 接口上：

```sh
python3 tools/quick-check.py --execute --interface en0
```

`en0` 只是示例，先核对自己的接口；不存在时应失败，不应悄悄换到别的接口。报告区分系统自动路由与强制接口，但不保存实际接口名。**接口绑定不等于已证明经过某个 AU / US 节点**；出口、分流和逐连接归属需进阶检查。

## 4. 保存或交给别人分析

中文报告和 JSON 是同一份结果的两种表示。离线示例也可以用 `--json` 查看：

```sh
python3 tools/quick-check.py --json
```

需要保存真实检查时，下面会发起一轮新的小请求，而非读取上次结果：

```sh
umask 077
mkdir -p results
chmod 700 results
python3 tools/quick-check.py --execute --json > results/quick-check.json
```

`results/` 被 Git 忽略。入门报告只保留计数、阶段耗时、字节数、HTTP 状态及错误类别，不记录真实 URL/域名、IP、接口名、正文、头部或 curl 错误原文。仍应人工检查将要公开的内容，不附原始配置或凭据。

退出码：`0` 表示离线演示/计划正常完成，或本轮实际检查全部符合条件；`1` 表示实际检查有失败或未完成；`2` 表示参数/环境问题；`130` 表示取消。终端返回非零仍应阅读保存的报告，不能只挑成功的一轮。

## 5. 可选：检查一个已知大小的下载文件

只有需要验证完整下载时再做这一步。准备自己可控制的、无凭据的 HTTPS 固定文件及精确字节数。不要使用私有签名 URL、分享节点链接、会动态变化的网页或大小未知的对象。

先用文档保留域名看计划，**该地址不是可实测下载源**：

```sh
python3 tools/quick-check.py --plan \
  --download-url https://download.example.invalid/fixed-1MiB.bin \
  --bytes 1048576
```

换成自己的真实对象 URL，核对文件大小和预算后，把 `--plan` 改成 `--execute`。两个参数必须同时提供；单个对象最多 **8 MiB**，固定最多 **2 次、每次 15 秒**。一轮另含前面的轻量探针。示例 1 MiB 对象的下载预算为 2 MiB；响应头、TLS 和重传另计。

只有 curl 成功、HTTP 200、收到的字节与约定完全相等且耗时有效，才算完整任务。部分超时不给成功吞吐；403/429、大小异常或响应超限会停止对应分支，余下请求列为“未开始”。不要使用放宽超时、换目标或测试限速的结果冒充生产修复。

要精确绑定源地址、固定目标 IP、增加重复样本或采集两端指标，请用 [进阶准备](advanced-start.md) 和 [测量指南](measurement-guide.md)。小请求通过和两次小文件完整，都不能替代长时间负载、手机直播、高峰或并发验收。

实现复用已有固定对象检查核心；curl 的时限和大小保护语义见 [官方手册](https://curl.se/docs/manpage.html)。Windows 的原生命令行与接口绑定仍需独立环境验证，本轮文档不把 macOS / Linux 的执行记录扩展到其他平台。
