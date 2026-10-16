# Market 验证可移植性 001 验收记录

- 日期：2026-10-17（北京时间）。
- TASK：[范围与授权](../engineering/TASK_MARKET_VERIFICATION_PORTABILITY_001.md)。
- 基线：`0d6e68c736495d820e06dfc8e7d536f9f296980c`；分支：`codex/market-verification-portability`。
- 使用说明：[Market 回归与报告再生成](../engineering/MARKET_VERIFICATION_RUNBOOK.md)。

## 实现范围

消除原生完成链测试在收集阶段对旧机器绝对路径和 PDS 测试模块的依赖。Market 持有自己的合成样本，仅在显式验收时加载经 Git 版本核对的 PDS 生产模块。原 12 项测试保留；普通回归明确取消选择并提示未运行集成，显式验收缺少参数、源码或精确版本时失败。

增加 `test` / `native-test` 可选依赖与 pytest 配置，隔离既有“无环境配置发现运行时”测试中的环境变量。无生产源码、语义配置、冻结合同或 XLSX 期望值修改。

## 实际验证

使用本轮独立 Python 3.14.7 虚拟环境；pytest 9.1.1、openpyxl 3.1.5、rapidfuzz 3.14.6、lxml 6.1.3。集成额外使用 cryptography 50.0.2、requests 2.34.2、tzdata 2026.5、pandas 3.0.6、numpy 2.5.4、pyarrow 26.0.0。其余依赖版本保存在本机冻结清单。

| 检查 | 结果与范围 |
|---|---|
| 初次定向检查 | 78 passed、1 skipped；跳过为当时尚未配置的 V0.3 Artifact XLSX 测试 |
| 原生完成链显式集成 | 12 passed，38.15 秒；实际运行独立进程交接与回读，输入和 Provider 全部为合成依赖，真实付费调用 0 |
| 初次完整回归 | 1773 passed、8 failed、12 deselected、550 subtests passed；186.10 秒。7 项失败为新虚拟环境遗漏 editable 安装导致子进程无法导入 Market；1 项为既有运行时发现测试被显式环境配置污染。此轮失败原样保留，不算通过 |
| 失败复核及冻结 XLSX 检查 | 9 passed，11.29 秒；补装项目并隔离测试环境后，8 项失败和原 XLSX 冻结指纹检查全部通过 |
| 最终完整回归 | 1781 passed、12 deselected、550 subtests passed；199.55 秒，退出码 0，无失败、错误或跳过。12 项为另行验收的原生完成链；V0.3 Artifact XLSX 集成及其余交付测试实际执行 |
| Python 源码解析 | 470 个文件，0 语法错误 |
| 生产树与边界 | `src` / `config` 对基线零差分；差分空白检查通过 |

集成使用独立、完整、非链接的干净依赖副本；没有将相邻仓库的未提交文件复制入验收，也没有修改相邻仓库。

- PDS：`436bcc4308db4fc5b59a10e549edcee04c580cdf`。
- ADS：`ef0ac6a3843b9648623e638b5b74fb1ce5056880`。

这些 SHA 是本轮实际装配版本，不声称其他仓库当前 main、业务能力或最新变更已全面验收。manifest 的实际绝对路径仅留本机忽略目录。

早期集成装配曾因缺少 cryptography、pandas 报错；补齐独立环境依赖后执行上述 12 项成功验收，没有通过跳过导入或替换生产模块绕过缺失。

## XLSX 指纹差异根因

同一版本的 openpyxl 3.1.5、同一合成输入和生产 renderer，只切换 `OPENPYXL_LXML`：

| XML 后端 | 包内容 SHA256 |
|---|---|
| 标准库后端，`False` | `84e5aed6de20ebf9373e8fbfb98cfd80be6aa663fe75cfcda9c0d4718e3c5e2b` |
| lxml 6.1.3，`True` | `89ffe16d58928ea3b00e0efac32980bb766a905e9ecbc9a524ba562fa1f6e6f5` |

前者精确复现历史失败值，后者精确恢复原冻结期望值。11 个 XML/relationships 成员的原始表示不同；按展开命名空间的 tag、无序属性、原样文本/tail 和子元素顺序比较全部 13 个成员，结构差异为 0。没有扩大指纹的归一化规则，也没有改写历史例外记录。这证明本样本的差异来自可选 XML 序列化后端，不能推广为所有 XLSX 字节差异都可忽略。

## 报告重建与使用验收

用户在本轮明确允许重新生成报告，并随后确认原报告与原始数据均已丢失。当前常用迁移目录未发现对应输入，历史哈希不能恢复其原始字节。本轮没有生成真实新报告，也没有以测试的合成输出替代原报告。

- 报告重建：`SOURCE INPUT MISSING`，需要新的真实导出或可核对原始证据及来源/窗口。
- 人工业务价值：继续为 `BUSINESS VALUE HUMAN REVIEW PENDING`。
- 具体使用问题：报告能否支持筛选值得继续研究的产品结构，并解释依据、限制与最小验证。
- 再生成入口、必需输入和人工核对清单已在操作说明记录。新输入生成新报告，独立验收，不套用 SP-043B 的旧样本数量、覆盖率或指纹。

没有采集、真实 Provider 调用、生产写入、预算、采购或广告动作。Buyer Need/KWS 适配与新增研究能力未启动。

## 本机原始证据

本轮日志、JUnit、依赖副本位置和 XML 后端对照保存在忽略目录 `outputs/verification_20261017/`。包括 `integration.xml`、`regression.log/xml`、`recheck.xml`、`regression-final.log/xml`、`xlsx-serializer-probe.json` 和 `requirements.freeze.txt`。原始输出中的本机路径不发布到公开仓库。初次失败、复核和最终运行各自保留，不能拼成一次无失败执行。

## 停止状态

工程验证状态：`ENGINEERING PASS`。使用说明中的单仓库与显式集成命令已在本轮实际执行；不据此声称用户已确认报告有用。

本 TASK 的工程修复与再生成说明已完成；原报告重建和人工业务验收仍待输入。本轮在此停止，不自动选择新 Provider、研究问题或下一阶段能力开发。
