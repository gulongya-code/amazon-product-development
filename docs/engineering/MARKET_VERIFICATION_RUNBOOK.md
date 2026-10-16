# Market 回归与报告再生成说明

本说明对应 `TASK_MARKET_VERIFICATION_PORTABILITY_001`。单仓库回归、跨仓库合成验收和真实报告使用验收分别记录，不互相代替。

## 单仓库回归

在 Market 仓库根目录和独立 Python >=3.12 虚拟环境执行：

```powershell
python -m pip install -e '.[test]'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:OPENPYXL_LXML = 'True'
python -B -m pytest -q -p no:cacheprovider
```

`pyproject.toml` 提供 `src` 导入路径和测试目录。普通回归不查找 PDS 目录，不导入 PDS 的测试模块。12 项 `native_integration` 用例默认取消选择，终端明确输出 `integration NOT RUN`，不能把该结果当作跨项目完成链通过。只指定这个测试文件而不启用集成时，全部取消选择并返回 pytest 的无测试退出码 5。

临时目录使用仓库外的 OS Temp；如自行传 `--basetemp`，也必须放在仓库外，以免触发正确的私有输入/输出保护。

旧 V0.1 XLSX 冻结指纹依赖 openpyxl 3.1.5 的 lxml 序列化路径。测试依赖固定 openpyxl 3.1.5 与 lxml 6.1.3；生产依赖、交付算法及原预期哈希不变。`OPENPYXL_LXML=False` 会复现历史 `84e5aed6…` 差异，启用 lxml 得到原预期 `89ffe16d…`。不要修改预期值来适应另一后端。

## 显式跨仓库合成验收

准备两个非链接、完整且干净的 Git checkout。ADS 必须位于 PDS 的同一父目录下，目录名为 `amazon_ads_optimizer`，这是现有生产 transport 的路径约束。不要改动带有未提交工作的现有 checkout；可创建独立副本并检出所需精确版本。不要复制凭据、私有输出或未提交业务数据。

在本机忽略目录（例如 `outputs/`）保存 manifest，替换以下占位符；此 JSON 是测试装配配置，不是新的业务合同：

```json
{
  "schema": "market-native-integration/v1",
  "pds": {
    "root": "<非链接的PDS绝对根目录>",
    "commit": "<40位小写Git提交SHA>"
  },
  "ads": {
    "root": "<同父目录下amazon_ads_optimizer的绝对根目录>",
    "commit": "<40位小写Git提交SHA>"
  }
}
```

Windows JSON 路径可使用 `/`，也可将反斜杠写为 `\\`。安装集成依赖后显式运行：

```powershell
python -m pip install -e '.[native-test]'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m pytest tests/test_native_research_completion.py -q -p no:cacheprovider `
  --run-native-integration --native-integration-manifest outputs/native-integration.local.json
```

缺少任一参数、manifest 无效、源码缺失、版本不匹配、checkout 有受控改动或未忽略的未跟踪文件、目录为链接、ADS 位置不符均失败，不跳过。缺 Python 依赖也不能算通过。原 12 项测试使用 Market 自有合成输入和离线 Provider 替身，实际执行 PDS/Market 的进程交接、证据绑定和回读；合成通过不代表真实模型或业务价值验收。

## 报告交付运行时

V0.3 XLSX 集成测试还需要主机提供的 Node 与 `@oai/artifact-tool`。通过 `load_workspace_dependencies` 获取路径，在本轮可写目录建立 `node_modules` 指向其包目录的 junction/symlink，避免向依赖目录写临时文件。

```powershell
$env:SP043B_NODE = '<主机提供的Node可执行文件>'
$env:SP043B_RUNTIME = '<本轮可写运行目录，内含node_modules链接>'
$env:MARKET_REPORT_NODE_EXECUTABLE = $env:SP043B_NODE
$env:MARKET_REPORT_NODE_MODULES = '<主机提供的node_modules目录>'
```

不提供时，对应测试按现有约定跳过，必须在交付记录中说明；Python 逻辑测试不能代替 XLSX 渲染和回读。

既有“无环境配置时发现运行时”测试在自己的作用域将上述两个 `MARKET_REPORT_*` 值置空，因此与为其余交付测试配置真实运行时兼容。

## 原报告丢失后的再生成

2026-10-17 用户确认 SP-043B 原报告与原始数据均已丢失。历史验收文档保存了样本数量与指纹，但不包含原始 Listing，不能从哈希恢复原数据。状态为 **SOURCE INPUT MISSING / 原报告重建未完成 / 业务价值人审待验收**。历史技术交付仍按其原时间和版本保留。

再生成需要先取得一份真实、适用的导出或可验证 Canonical 证据，明确站点、品类、样本范围、数据观察日期/窗口和来源性质。来源未知的日期不得用抓取/生成时间替代。新取数形成新报告、新指纹和独立使用验收，不能沿用旧报告的技术与业务结论。费用或 Provider 取数权限按具体任务确定，本 TASK 不启动新采集。

已有离线入口为 `scripts/run_sp_043b_private_market_reports.py`，其输入 manifest 包含 `categories`，每项要求：

| 字段 | 含义 |
|---|---|
| `category_key` | 唯一输出目录键，仅大写字母、数字和下划线 |
| `input`, `sheet` | 真实原始导出绝对路径和工作表 |
| `marketplace`, `category` | 对象与品类，须与语义/路线配置匹配 |
| `observed_date`, `imported_at`, `generated_at` | 观察日期、导入时间和报告时间，按真实来源分别填写 |
| `profile`, `route_config` | 仓库相对配置路径；不因覆盖不足改变已发布分类规则 |

现有匹配配置包括 shower caddies 和 air fryers；后者语义配置文件名为 `air_fryer_accessories.v1_1.json`，其实际 scope 为 `air fryers`，应核对内容而不是按文件名猜测。原始输入、manifest、报告及 QA 输出均放仓库外。以下仅为有合格输入后的调用形式，本轮未执行：

```powershell
python -B scripts/run_sp_043b_private_market_reports.py `
  --manifest '<仓库外输入manifest>' --output-root '<仓库外新输出目录>' `
  --node $env:SP043B_NODE --renderer-runtime $env:SP043B_RUNTIME
```

再生成后按一个具体使用问题验收，例如“哪些产品结构值得继续研究，证据和限制是什么”。先核对 JSON、中文 Markdown、XLSX 一致性、源版本与指纹，再由人工审阅：

1. 样本、已分类子集和全市场是否区分，低覆盖是否限制了强结论？
2. 主要结构/机制、价格、评论门槛和新品贡献能否定位到支持数据及分母？
3. 来源估计、时间、未知与真实零是否清楚？
4. 缺 Buyer Need、成本或利润时是否明确限制产品方向，而没有补造？
5. 这份报告支持或反对哪个具体选择，还缺什么最小验证？

人审结果引用精确报告指纹，另记有用、无用或需补充及理由。保留报告快照和其空白人审字段，不把人工反馈补写成模型原结论。没有实际人审，不宣布 BUSINESS VALUE PASS；没有新的明确问题，不进入下一项功能开发。
