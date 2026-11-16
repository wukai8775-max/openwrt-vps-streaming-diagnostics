# VPS 与路由器分流

从一台电脑开始。先用电脑的代理客户端验证 VPS，再让路由器只给一台设备分流。有多台设备需要按 Wi-Fi 选线路时，再加专用 Wi-Fi。

## 配置并验证 VPS

下面以一台新的 Linux VPS 和 Xray 的 VLESS + REALITY 为例。已有节点可以直接做第 4 步。若 VPS 已有业务，先确认云控制台能登录并私下备份原配置，在独立的测试服务上验证。

1. 按 [Xray 官方 Linux 安装说明](https://xtls.github.io/document/install.html#linux-安装方式) 安装服务端。用 `systemctl cat xray` 查看服务实际加载哪个配置。准备一个空闲的入站端口，确认云安全组和 VPS 防火墙允许该协议入站，保留原 SSH 规则。
2. 对照官方的 [服务端示例](https://github.com/XTLS/Xray-examples/blob/main/VLESS-TCP-XTLS-Vision-REALITY/config_server.jsonc) 和 [客户端示例](https://github.com/XTLS/Xray-examples/blob/main/VLESS-TCP-XTLS-Vision-REALITY/config_client.jsonc) 填写自己的配置。用 `xray uuid` 生成用户 ID，用 `xray x25519` 生成匹配的密钥。`PrivateKey` 留在服务端，新版输出的 `Password (PublicKey)` 是客户端用的 REALITY 公钥，部分版本把这一行简写为 `Password`。

   服务端填入能从 VPS 访问、支持 TLS 1.3 和 HTTP/2 的目标站，以及目标站证书覆盖的 Server Name。另选一组 16 位十六进制字符作为 Short ID。客户端填写 VPS 地址、入站端口、相同的 UUID 和流控方式 `xtls-rprx-vision`、匹配的 REALITY 公钥、服务端允许的 Server Name 和 Short ID。常见界面把此例的传输显示为 TCP 或 RAW。配置和完整分享链接保存在本地，公开记录只写脱敏结果。
3. 在 VPS 上先校验配置，再启动新服务。以下命令适用于 [官方安装器](https://github.com/XTLS/Xray-install) 的默认二进制、配置路径和服务名。若 `systemctl cat xray` 显示别的路径，按实际配置执行 [Xray 的配置测试](https://xtls.github.io/document/command.html#xray-run)。

   ```sh
   sudo /usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json
   ```

   确认配置测试通过后，才执行下列命令。确认服务显示 `active`，并从日志检查启动错误。

   ```sh
   sudo systemctl restart xray
   systemctl is-active xray
   sudo journalctl -u xray -n 30 --no-pager
   ```

4. 电脑接入一个直连网络，用支持相同协议的代理客户端添加节点。确认浏览器实际通过该客户端代理，再访问公网 IP 查询页和要使用的目标站点。核对公网出口与 VPS 的预期出口一致，并能重复打开目标站点。若服务已启动但电脑连不通，从监听端口、云安全组和主机防火墙查起。能到端口却无法握手时，逐项核对客户端参数和服务日志。

## 在路由器上配置分流

先登录 LuCI，导出路由器配置，留一台接原 LAN 的设备管理路由器，记下管理页地址和默认网络当前的出口。若还没有 PassWall 或 Xray 核心，按 [PassWall 发布页](https://github.com/Openwrt-Passwall/openwrt-passwall/releases) 的说明，选择匹配 OpenWrt 版本和路由器 CPU 架构的软件包。界面选项随固件和插件版本变化。

1. 打开「服务 → PassWall → 节点列表」，添加刚在电脑上验通的节点。沿用 VPS 部分的例子，选择 Xray 和 VLESS，填写 VPS 地址、端口和 UUID，传输选 RAW（部分版本显示 TCP），开启 TLS 与 REALITY，再按电脑配置填写 SNI、流控和 Short ID。将 VPS 部分生成的 REALITY 公钥填入 `Public Key`。
2. 打开「访问控制」页的主开关，添加并启用一条规则，把来源限定为一台测试设备的当前 IPv4 地址。需要长期使用时，先为它设置 DHCP 静态租约。规则内关闭「使用全局配置」，选择新节点，确认该设备所需流量的代理方式已启用。保留「基本设置」中已有的默认节点和策略。全新安装时可以关闭全局的「客户端代理」，由访问控制匹配这台测试设备。「访问控制」页的开关单独控制这些定向规则。应用前检查规则顺序，确保测试设备能命中新规则。
3. 在测试设备上关掉第 1 部分使用的代理客户端、VPN 或系统代理，再通过路由器打开目标站点并核对公网出口。同时从原 LAN 管理设备检查 LuCI、默认网络上网及其原有出口。若测试设备能用 IPv6，也用 IPv6 单独核对出口。测试结果成立后，再增加一台设备或扩展规则。
4. 若要让多台设备通过 Wi-Fi 名称选择线路，按 [OpenWrt 独立 Wi-Fi 配置指南](https://openwrt.org/docs/guide-user/network/wifi/guestwifi/configuration_webinterface) 新建空网桥、独立接口和 DHCP，选一个与现有网络不重叠的子网。将新 SSID 绑定到该接口并设好无线密码。在 PassWall 访问控制中用新接口或子网匹配，选择已验通的节点。若要求代理断开后专用 Wi-Fi 不直连外网，防火墙使用独立区域，只开放必要的 DHCP、DNS 和本地代理访问。这时跳过官方访客网络示例里的直接转发至 WAN，并在受控测试中临时停用该测试节点，分别检查 IPv4、IPv6 是否会绕过代理。

测试设备出口偏离预期、DNS 连续失败、默认网络受影响或 LuCI 无法访问时，从保留的管理设备禁用刚新增的规则或专用 Wi-Fi，恢复受影响的原配置，再重新检查管理页、默认网络和测试设备的出口。详见 [恢复与清理](acceptance-and-rollback.md#恢复与清理)。

分流验证通过后，在准备开播的 Wi-Fi 上做[小请求检查](beginner-check.md#2-对自己的网络做一次小检查)、[完整下载](measurement-guide.md#2-固定对象完整测五次)和[持续上传](measurement-guide.md#4-受限持续上传与小请求回归)。
