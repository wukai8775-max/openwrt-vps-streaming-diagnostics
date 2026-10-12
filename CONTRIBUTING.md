# 贡献与复现

先给出症状、测试方向、目标对象大小、成功/失败分母、超时和真实业务表现。将“观察到的结果”“机制假设”“已验证的原因”分别写清楚。相同名称的配置不代表相同连接实际使用它，应附脱敏后的活动发送 socket 信息。

新增工具保持显式目标、绑定来源、流量预算、停止条件和回滚边界。默认不做生产修改；任何新配置建议都需要证据和独立验收。

提交前执行：

```sh
python3 -m unittest discover -s tests -v
sh -n tools/snapshot.sh
sh -n tools/sample.sh
python3 tools/check-publication.py
git diff --check
```

CI 使用合成数据与假命令，不会接入路由器、VPS 或公共测速接口。支持范围是 Python 3.10+、常规 curl，以及 Linux/OpenWrt POSIX shell。其他平台请附脱敏复现，避免为兼容性而取消源绑定、证书验证或时间预算。

公开检查扫描 Git 暂存区里的 blob，发布前先将计划公开的文件加入暂存区；它不会扫描未暂存的工作副本。提交前仍需人工检查内容与差异，不能靠检查脚本证明任意文件都已脱敏。
