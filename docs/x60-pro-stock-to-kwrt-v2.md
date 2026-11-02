# RG-X60 PRO V2.00：原厂系统到 Kwrt 107 MiB 实测流程

[中文首页](../README.md) · [文件准备与固定校验值](x60-pro-firmware-preparation.md) · [验收与恢复边界](acceptance-and-rollback.md)

**记录日期：2026-11-02（Asia/Shanghai）。** 本例已完成目标固件写入、正常启动和最终重启后的版本、管理页、SSH、有线及无线接口读回。真实手机逐个 Wi-Fi 关联尚未完成验收，直播尚未真实开播，失败恢复和原厂回退尚未验证。

## 1. 本例适用范围与文件

| 项目 | 实际记录 |
|---|---|
| 设备 | RG-X60 PRO，铭牌硬件 V2.00 |
| 原厂系统 | ReyeeOS 1.226.2120；Linux 5.4.171、aarch64 |
| 原厂 UBI | 起点 `0x680000`，长度 `0x3f00000`，63 MiB |
| 新引导 | hanwckf/bl-mt798x，release `20241115`，U-Boot 2023.07 |
| 临时 RAM 系统 | OpenWrt 25.12.6 对应目标的 `initramfs-kernel.bin`，9,166,140 bytes；实际运行内核 6.12.112 |
| 目标系统 | Kwrt 25.12-SNAPSHOT，revision `10.28.2026`，kernel 6.12.112，board `ruijie,rg-x60-pro` |
| 最终 UBI | 起点 `0x680000`，长度 `0x6b00000`，107 MiB；布局标签 `ubi-107m` |

系统镜像、官方 RAM 镜像及 U-Boot 的下载链接、SHA256 和验签方式沿用 [2026-11-01 固定准备记录](x60-pro-firmware-preparation.md#2-下载来源与固定核验记录)。本例使用：

- Kwrt：`kwrt-10.28.2026-mediatek-filogic-ruijie_rg-x60-pro-squashfs-sysupgrade.bin`，45,947,151 bytes；SHA256 `f67cbe51c08ffb72a74e41178612457a913c320f882cba9855425b7e64a0103b`。
- FIP：release archive 顶层 `mt7986_ruijie_rg-x60-pro-fip-fixed-parts-multi-layout.bin`，834,121 bytes；SHA256 `8552cbeeb395f59c5f522a021557117f7aa8a08fe52e6ccc33c168bac4e54e02`。

以下流程以本机的已读分区和这些精确文件为依据。其他原厂版本、硬件或构建需要重建相应证据。

## 2. 取得原厂管理权限并保全原机数据

原厂网页的正常本地升级入口有 30 MiB 前端限制。本次选择 45,947,151-byte Kwrt 时即被拒绝，没有上传；没有通过改后缀、压缩或绕过前端限制把它当成原厂升级包。

本例先在原厂页面确认开启开发者模式，再正常完成 SSH 认证。网页管理密码不能直接视为 SSH 密码。本次使用的是针对本人设备标识、在本机离线计算的凭据，依据 [RuijieDecrypt 固定提交](https://github.com/RuijieNetworksCommunity/RuijieDecrypt/tree/b2f7581baec8674d02700de37f9c4acba89d2414)；不涉及云命令重放或添加账户。设备标识、实际口令、初始口令及口令哈希不随本文发布。

写入前读取 `/proc/mtd` 和各分区的实际 offset。本例原厂布局如下；编号只对这个阶段的读回成立：

| 原厂 MTD | 名称 | 起点 | 长度 |
|---|---|---|---|
| mtd0 | whole | `0x0` | `0x8000000`，128 MiB |
| mtd1 | BL2 | `0x0` | `0x100000` |
| mtd2 | u-boot-env | `0x100000` | `0x80000`，512 KiB |
| mtd3 | Factory | `0x180000` | `0x200000` |
| mtd4 | FIP | `0x380000` | `0x200000`，2 MiB |
| mtd5 | product_info | `0x580000` | `0x80000` |
| mtd6 | kdump | `0x600000` | `0x80000` |
| mtd7 | ubi | `0x680000` | `0x3f00000`，63 MiB |

已取得完整 134,217,728-byte 读出文件，并按实际 offset 提取七个分区；完整文件和各分区均与设备端独立 SHA256 一致。该读出是 **NAND 经 ECC 校正的 main data，不含 OOB**，不能当成已验证的外置编程器全片恢复镜像。原厂配置导出另行保留，不能代替这些分区备份。

本次没有做恢复试验，也没有把运行中 UBI 的读出认证为文件系统一致性快照。备份、校验记录和配置只存于私有位置，不能作为公开附件。

## 3. 写入 FIP，并准备可用的 Web 启动环境

本例的引导调整只改写 **FIP 和 u-boot-env**，没有改写 BL2、Factory、product_info 或 kdump；后续系统镜像写入在第 5 节单独记录。写入前后都核对受保护分区，FIP 上传至设备后的长度和 SHA256 与准备文件一致，写后分区再次读出核对。

先将已校验 FIP 放到设备的临时目录，再在设备上确认文件；传输方式需按当前可用的连接单独确认：

```sh
FIP_FILE='/tmp/mt7986_ruijie_rg-x60-pro-fip-fixed-parts-multi-layout.bin'
wc -c "$FIP_FILE"
sha256sum "$FIP_FILE"
cat /proc/mtd
```

长度应为 834,121，SHA256 应与第 1 节一致。**只有已再次确认命名分区 `FIP` 就是上表的 2 MiB 区域后**，本例原厂阶段的写入和验证命令才是：

```sh
mtd write "$FIP_FILE" FIP
mtd verify "$FIP_FILE" FIP
```

写后读取整个命名分区所对应的设备。本例原厂阶段它是 `/dev/mtd4`，换系统后不得沿用这个编号：

```sh
dd if=/dev/mtd4 of=/tmp/fip-readback.bin bs=131072 count=16
wc -c /tmp/fip-readback.bin
head -c 834121 /tmp/fip-readback.bin | sha256sum
sha256sum /tmp/fip-readback.bin
```

整个读回应为 2,097,152 bytes；前 834,121 bytes 的 SHA256 应与候选 FIP 一致。整个 2 MiB 的 hash 另作私有读回记录，它包含候选文件之外的区域，不能拿它直接与 834,121-byte 文件 hash 比较。任何长度、分区或校验异常都应停在本阶段，不继续重启。

候选 FIP 小于实际 2 MiB FIP 分区；它与原机 FIP 的两个 payload 身份、ToC flags 相同，分区前缀和 SPI-NAND 描述也已对照。原机 ATF 2.6／U-Boot 2022.01 与候选 ATF 2.9／U-Boot 2023.07 的版本差异没有被当成必须先更换 BL2 的理由。

本机 RESET 的 GPIO9 active-low 信号已确认，但两次按住 RESET 断电上电均未进入 Web。因此，**本文不把 RESET 长按写成这台设备已成功的进入方法**；本例使用的是下面的软件菜单路径。

原厂阶段曾读到“CRC 有效、数据区却主要为 FF、没有有效键值”的环境内容。CRC 通过不等于环境变量可用，不能对这种内容盲用 `fw_setenv`，也不能只因命令退出成功就认定引导配置已保存。

本次从精确候选 FIP 的编译默认环境中提取并保留六个字段，值如下；这些是这个构建的引导默认值，不是后续业务网络设置：

```text
bootdelay=2
baudrate=115200
ipaddr=192.168.110.1
serverip=192.168.110.2
netmask=255.255.255.0
loadaddr=0x46000000
```

为进入 Web，另加入：

```text
bootmenu_default=6
bootmenu_delay=1
```

生成的是与实际环境区域匹配的 **524,288-byte 有效环境镜像**，包括正确 CRC 和可解析的 NUL 分隔键值。本例格式为前 4 bytes 保存数据区 CRC32 的小端值；其余数据区保存 NUL 分隔键值、双 NUL 结束符和 FF 填充，CRC 覆盖整个数据区。写后再次读回，核对 CRC、字段和整个区域；不能把普通文本文件直接写进环境分区，也不能把这一格式推广到冗余环境或其他区域大小。

下面仅在电脑的私有准备目录中离线生成文件，**不连接设备、不刷写分区，已有同名文件时拒绝覆盖**。它只适用于上述精确 FIP 与本例非冗余 512 KiB 环境格式：

```sh
python3 - <<'PY'
from pathlib import Path
import os
import struct
import zlib

fields = {
    "bootdelay": "2",
    "baudrate": "115200",
    "ipaddr": "192.168.110.1",
    "serverip": "192.168.110.2",
    "netmask": "255.255.255.0",
    "loadaddr": "0x46000000",
    "bootmenu_default": "6",
    "bootmenu_delay": "1",
}
size = 0x80000
payload = b"\0".join(f"{k}={v}".encode("ascii") for k, v in fields.items()) + b"\0\0"
if len(payload) > size - 4:
    raise ValueError("Environment exceeds the verified region size")
data = payload + b"\xff" * (size - 4 - len(payload))
image = struct.pack("<I", zlib.crc32(data) & 0xffffffff) + data
output = Path("uboot-env-web-20241115.bin")
fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "wb") as stream:
    stream.write(image)
print(f"Created {output.name}: {len(image)} bytes")
PY
```

生成文件仍需按本例已确认的环境分区写入途径处理，并再次读回核验；生成成功不代表设备环境已经更新。生成文件不作为公开仓库附件。

在这个构建中菜单项 6 是 `Start Web failsafe`；正数 `bootmenu_delay=1` 与 `bootmenu_default=6` 共同使本次上电进入 Web。**这两个变量是持久设置，不是一次性启动开关**，必须在系统写入后清理，否则仍会返回 Web。

U-Boot Web 的本例默认管理地址为 `192.168.110.1`，`/version` 读回 `2023.07`，`/getmtdlayout` 初始为 `default`。这些读回也用于区分新 U-Boot Web 与原厂 LuCI；仅见到原厂页面不能推断 FIP 写入失败。

## 4. 先启动官方 RAM 系统，实测后续环境清理能力

本次在写 Kwrt 前，先用官方 initramfs 启动临时系统，实际检查能否读取并修改、恢复引导环境。上传与执行是两个不同阶段：

```text
POST /upload
multipart 文件字段：initramfs
文件：已校验的官方 initramfs-kernel.bin
```

不能把 initramfs 放进 `firmware` 字段后仍称为 RAM 启动。此处是本次独立的 initramfs 流程，没有提交新的布局标签；它没有写入系统镜像。源码中的环境保存分支独立于 INITRD 判断，不能把所有 RAM 启动操作笼统称为“绝不写闪存”。

上传响应的长度须为 **9,166,140**，MD5 须与本地完整文件一致。本例为 `3688f4f78904206034cd921327fdfaa1`。确认后仅发起一次 `GET /result`；它是执行动作，INITRD 分支随后从内存启动。`success` 响应不代替 RAM 系统实际上线和版本读回。

### RAM 内核、MTD 编号及写权限

RAM 系统的实际内核为 `6.12.112`，其 `u-boot-env` 变成 **mtd1**，不是原厂阶段的 mtd2，而且默认只读。每次换系统都应重新按名称、offset 和长度定位，不能沿用编号。

只读检查可以先运行：

```sh
uname -r
cat /proc/mtd
```

本次为 RAM 内核准备的官方模块为：

- 包：`kmod-mtd-rw-6.12.112.2021.02.28~e8776739-r1.apk`，2,107 bytes。
- 官方 ABI 目录：`6.12.112-1-f0a7348f9cb959e1bf4d0447669b031e`；相同内核版本号本身不足以代替 ABI 匹配。
- [官方包下载](https://downloads.openwrt.org/releases/25.12.6/targets/mediatek/filogic/kmods/6.12.112-1-f0a7348f9cb959e1bf4d0447669b031e/kmod-mtd-rw-6.12.112.2021.02.28~e8776739-r1.apk)。SHA256：`2de1d61b4dace51e760a464c13d2f2ddca8434413ddc33e08e1a90616f4b9734`。

RAM 系统当时的 APK keyring 不信任该包的内嵌签名，普通安装返回 `UNTRUSTED signature`。本次先独立验证 OpenWrt 官方 `sha256sums` 的 Ed25519 签名，再核对其中该精确包的 SHA256、下载内容和 RAM 内核 ABI；只对这一份已认证的本地包使用 `--allow-untrusted`。这不是忽略校验，也不表示其他包可以这样安装；本例没有将该内嵌 APK 签名单独验证为可信。

在上述独立认证及 ABI 核对全部通过之后，本例 RAM 阶段采用的本地包安装与加载方式为：

```sh
APK_FILE='/tmp/kmod-mtd-rw-6.12.112.2021.02.28~e8776739-r1.apk'
sha256sum "$APK_FILE"
apk add --no-network --force-non-repository --allow-untrusted "$APK_FILE"
insmod "/lib/modules/$(uname -r)/mtd-rw.ko" i_want_a_brick=1
```

`--force-non-repository` 用于这次 RAM 环境中的本地 APK 安装；它与 `--allow-untrusted` 都不提供来源认证，认证来自前面的已验签官方清单和精确内容核对。RAM 重启后需重新准备，不能据此改变常规系统的软件源或全局信任策略。

`mtd-rw` 的 `i_want_a_brick=1` 参数会解除 MTD 分区的只读标志，范围并不限于环境分区。加载模块不等于写入数据；本次实际写操作只针对已核对的环境区域，并完成修改、读回、恢复测试，为后面的菜单清理建立了可用路径。不得用不同 ABI 的模块或依赖强制选项代替这一步。

再次按名称、offset、长度及擦除块大小确认 RAM 中 `u-boot-env` 确为 mtd1 后，本例真实使用的临时 `fw_env.config` 是以下**四字段**格式：

```sh
printf '/dev/mtd1 0x0 0x80000 0x20000\n' > /tmp/fw_env.config
fw_printenv -c /tmp/fw_env.config bootdelay baudrate
```

四项分别是设备、设备内偏移、环境大小和擦除块大小。本例没有第五个 sector-count 字段。这里只读取已知引导字段；CRC 错误、分区不匹配或解析不到预期字段时，不能继续写环境。

## 5. 选择 107 MiB 布局并写入 Kwrt

回到 U-Boot Web 后，选择系统固件上传，并在**同一次上传**中提交布局：

```text
POST /upload
multipart 文件字段：firmware
mtd_layout：ubi-107m
文件：已校验的 Kwrt sysupgrade.bin
```

本次上传响应为以下三项：

```text
45947151 50c976d84ce5691ed7167aaf38be5885 ubi-107m
```

逐项核对 **字节数、完整 MD5、布局标签** 后，才执行一次 `GET /result`。不要把布局标签仅放到 `/result` 的查询参数里；处理器使用的是上传时保存的标签，并在写入系统镜像前保存相应环境项。

**`GET /result` 不是状态轮询接口，不配置自动重试。** 本例只触发一次，返回 `success`。若请求超时或响应丢失，应先观察设备及已有状态，不能把再次调用当成无副作用的重查。上传长度／MD5 一致只证明收到的内容相符，真正的启动结果仍要通过新系统读回确认。

## 6. 清理临时菜单，保留 107 MiB 布局

写入成功后，本次设备因临时菜单设置再次进入 Web。这是尚未清理的持久启动配置，不是仅凭该现象就能判断系统写入失败。

再次按第 4 节的 **initramfs 字段**启动官方 RAM 系统，重新确认内核、实际环境分区及权限；RAM 安装的工具不会因为上一次装过就自动保留。使用前述已认证、匹配 ABI 的模块，修改环境时仅删除：

```text
bootmenu_default
bootmenu_delay
```

同时保留并读回：

```text
mtd_layout_label=ubi-107m
```

每次进入 RAM 都重新创建第 4 节的临时配置并核对真实分区。先确认布局值为 `ubi-107m`，再执行本例实际使用的删除操作；`fw_setenv` 不带值表示删除键：

```sh
printf '/dev/mtd1 0x0 0x80000 0x20000\n' > /tmp/fw_env.config
fw_printenv -c /tmp/fw_env.config bootmenu_default bootmenu_delay mtd_layout_label
fw_setenv -c /tmp/fw_env.config bootmenu_default
fw_setenv -c /tmp/fw_env.config bootmenu_delay
fw_printenv -c /tmp/fw_env.config mtd_layout_label
rmmod mtd_rw
```

还应核对删除结果、原始环境区域读回及卸载后的只读标志恢复，不能只看某一条命令退出成功。

核对有效 CRC、六个默认字段和布局，再读回整个环境区域；本次随后卸载临时写权限模块。**不能为了退出 Web 把整个环境重新清空成 FF，也不能把 `mtd_layout_label` 一起删除**，否则可能回落到与已写系统不匹配的 63 MiB 默认布局。

清理后正常重启，本例已进入 Kwrt，而不是再次被临时菜单送回 Web。

## 7. 电脑接线、初始认证与最终验收

U-Boot、官方 RAM 系统和 Kwrt 的默认地址、网口角色可能不同；原厂自动 WAN/LAN 角色也不能沿用。Mac 本次只对有线 USB 网卡临时设置手动 IPv4，不填网关，并在维护阶段关闭该接口的 IPv6，避免接线改变已有 Wi-Fi 的默认出口。USB 转换器重插后曾消失，需要先确认它重新枚举及实际接口名，不能继续使用旧接口或旧邻居记录。

官方 RAM 阶段需按对应 OpenWrt 的 LAN 口接线；初次 Kwrt 管理页在 `10.0.0.1` 实测可达。之后管理地址和业务网络属于私有配置，不在本文给出。维护结束应根据实际使用方式恢复电脑有线接口设置。

Kwrt 的精确 rootfs 中，`/etc/shadow` 初始 root 字段为空，但首次启动脚本会设置初始凭据，不能由静态空字段推断启动后 SSH 允许空口令。本例核对镜像初始化逻辑后正常完成认证；不试猜测口令，不公开初始凭据或哈希。

最终完成的读回包括：

- Kwrt `25.12-SNAPSHOT`，revision `10.28.2026`，kernel `6.12.112`，board `ruijie,rg-x60-pro`。
- 实际 UBI 为 `0x6b00000`，107 MiB，环境中保留 `ubi-107m`。
- 最终正常重启后管理页、SSH、有线和无线接口读回通过；结合重启后的运行时间确认已跨过重启，过早读到旧进程响应的一次轮询没有计为验收成功。

真实手机逐个 Wi-Fi 关联、高峰负载、失败恢复及原厂回退尚未完成验收，直播尚未真实开播。配置文件、接口存在和一般出口测试都不代替真实开播验收。

## 源码核对位置

- [精确构建的 Web 上传逻辑](https://github.com/hanwckf/bl-mt798x/blob/15ad0ed949043bcbbcb5ef501ba156b1f25e676f/uboot-mtk-20230718-09eda825/failsafe/fsdata/main.js#L74)：FormData 字段与布局。
- [服务端上传与执行处理](https://github.com/hanwckf/bl-mt798x/blob/15ad0ed949043bcbbcb5ef501ba156b1f25e676f/uboot-mtk-20230718-09eda825/failsafe/failsafe.c#L148)：类型校验、上传响应、布局保存、writer 与 RAM 启动分支。
- [执行页](https://github.com/hanwckf/bl-mt798x/blob/15ad0ed949043bcbbcb5ef501ba156b1f25e676f/uboot-mtk-20230718-09eda825/failsafe/fsdata/flashing.html#L12)：只发起一次 `/result`，不能改成轮询或自动重试。

源码解释与本例实测分别列明；本例没有把源码可支持的恢复功能写成已经做过的恢复试验。
