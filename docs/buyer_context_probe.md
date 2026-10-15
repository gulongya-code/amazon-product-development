# YPS 同条件购买页面核验试点

## 后续补齐及 PDS 项目复核（2026-10-13 13:37 北京时间）

项目现在会在同一隔离访客会话中读取两款商品的公开报价明细，并展开只读的报价说明；不点击购物车。新品判断来自明确的 `New` 报价行，并核对 ASIN、邮编、标价和卖家 ID，不能仅凭请求里的 `condition=new` 升级品相。

本次两款均得到 `NEW_EXPLICIT_OFFER_ROW`：YPS 为 USD 23.99，DERNORD 为 USD 24.99。币种来自商品购买区域的明确 USD 字段。PDS 使用其 10 月 12 日留存 `ad_auth_shops` 回执，将 YPS 卖家 `A3P7S91DQ4RKU4` 与美国 sid 9226 精确绑定；这是留存账户身份匹配，没有刷新店铺授权或写入正式身份库。

展开报价明细后仍只有满 USD 35 或 Prime 的免邮条件。**单包普通买家运费、优惠适用、税费和到手总价仍未知**；本次没有完整到手价比较能力，也没有把未知运费补零。两款在库及可见按钮仅作页面观察，不证明最终订单成功。

新证据位于 `C:/amazon_private/yps_market_evidence_preparation_20261013/01a132e0-df6c-7581-88d4-e436e1cb0700/offer_completion_20261013/live_final/result.json`。每款目录另有 `page.html/png`、`offers.html/png` 和快照，全部带哈希。`live_1` 是展开明细前的真实采集，保留不覆盖。

PDS 新入口 `tools/run_yps_market_offer_review.py` 消费这些文件，复用 PDS 原市场交接校验、严格 JSON、不可变记录和既有 Provider 通道，完成一次真实模型复核。`output/pds/yps_market_offer_review_002/run_3/review.json` 状态为 `ANALYSIS_COMPLETED`、来源为 `PROJECT_PROVIDER_ANALYSIS`，HTTP 200、调用一次。M2 和 M4 修正为当前明确新品报价及页面可购买证据；M1、M3、M5 保留样本、规格资格及历史窗口限制。建议仍是不因单一样本降价，不宣称到手价优势。

市场项目通过 `python -m amazon_product_intelligence.pds_market_readback --receipt <PDS回执> --receipt-sha256 <SHA> --market-result <本次result.json> --output <新JSON>` 实际回读该回执，并再次校验全部来源引用。`offer_completion_20261013/market_readback.json` 确认分析消费完成，不代表业务验收。

没有调用 Sorftime、充值、加入购物车、下单或启用调度；SP-043B 继续待验收。以下保留首次可行性验证记录，其中尚未确认的新品、币种和卖家字段，以本节的新证据及日期补充；原始结果不改写。

2026 年 10 月 13 日，项目通过自有 Python 入口实际读取 YPS `B0H5BWL6J2` 和 DERNORD `B07XFCSRL5`，确认两款页面均显示 `Los Angeles 90001`，使用独立、未登录的访客会话。页面采集来自项目程序，没有使用 Codex 浏览器代查。当前完成的是采集来源与配送条件的可行性验证，完整新品到手价比较仍未完成。

## 真实运行结果

最终采集时间为北京时间 2026 年 10 月 13 日 13:25:28—13:25:35。

| 项目 | YPS | DERNORD |
|---|---|---|
| ASIN | B0H5BWL6J2 | B07XFCSRL5 |
| 页面报价 | $23.99 | $24.99 |
| 页面包装声明 | 2 Pack | Pack of 2 |
| 显示卖家 | Schuyler Stainless Steel Valve Fittings | denuodianqiyouxiangongsi |
| 发货方 | Amazon | Amazon |
| 配送地 | Los Angeles 90001 | Los Angeles 90001 |
| 页面库存文字 | In Stock | In Stock |
| 加入购物车按钮 | 显示且可用，未点击 | 显示且可用，未点击 |
| 普通访客单包运费 | 未知 | 未知 |

页面免费配送条款要求 Amazon 发货订单满 $35，或加入 Prime。两款的单包价格都低于该门槛，因此不能把运费补成零，不能把标价差直接解释为到手价优势。优惠资格、税费和结算总价也未确认。

页面符号为 `$`；此次解析没有取得独立、明确的币种代码，所以程序保留符号并将币种代码标为未知。访客会话不等于已验证的登录后非 Prime 账户。主购买区域没有取得明确的新品品相文字；卖家显示名称也尚未与 PDS 店铺身份建立正式对应。这些缺口不妨碍确认页面采集可行，但阻止完整报价资格验收。

## 项目入口与复用

新增模块 `src/amazon_product_intelligence/buyer_context_probe.py` 与命令 `amazon-buyer-probe`。仅绑定上述两款和 90001，不放开旧 Sorftime 生产入口的其他 ASIN，也不触发完整市场报告流水线。复用项目 `APIResponse` 和 `SnapshotWriter` 保存结构化页面观察；HTML 与截图另存引用和 SHA256。

可选依赖为 `buyer-probe`，包含 Playwright；常规项目依赖不强制安装它。实际试点使用 Playwright 1.63.0 和本机 Microsoft Edge，通过全新临时会话运行，没有读取个人浏览器配置、登录账户、导出 Cookie、加入购物车或下单。浏览器在运行结束后关闭，没有自动调度或重试循环。

安装和显式执行示例：

```powershell
python -m pip install -e ".[buyer-probe]"
amazon-buyer-probe --output C:/amazon_private/yps_buyer_probe_NEW
```

也可使用同一 Python 环境执行：

```powershell
python -B -X utf8 -m amazon_product_intelligence.buyer_context_probe --output C:/amazon_private/yps_buyer_probe_NEW
```

输出必须是新目录；不覆盖历史结果。默认使用已安装 Edge，可用 `--channel chrome` 显式选择 Chrome。当前运行环境存放在仓库外 `native_probe_20261013/runtime`，没有改变系统 Python 的安装包。

退出码 0 仅表示两款配送及访客条件已观察到，结果状态仍为 `CONTEXT_FEASIBILITY_OBSERVED_OFFER_VALIDATION_REQUIRED`；不是完整新品报价或业务验收通过。退出码 1 表示未能证明来源能力；2 表示依赖或输出参数不满足启动条件。

## 验证与证据

30 项测试通过：

```powershell
python -B -X utf8 -m pytest tests/test_buyer_context_probe.py tests/test_snapshot_writer.py -q -p no:cacheprovider
```

测试覆盖 HTTP 失败、验证码、错误 ASIN、错误配送地、已有登录状态、混合新旧报价、外币、每只单价、条件免邮及旧输出保护。构造测试不是商品实证。

实际调试保留 `live_1`—`live_4` 和 `live_final`：最初页面显示香港和港币，程序拒绝采用。修正邮编更新后的异步确认，并区分隐藏模板与可见 Continue 按钮后，`live_4` 和最终运行均核对到 90001。没有以手工改 Cookie、伪造邮编字段或绕过验证码获得成功状态。

证据根目录：`C:/amazon_private/yps_market_evidence_preparation_20261013/01a132e0-df6c-7581-88d4-e436e1cb0700/native_probe_20261013`。

- `live_final/result.json`：两款原生程序结果、部分报价和缺口。
- `live_final/<ASIN>/`：原始页面、截图、结构化快照。
- `validation.json`：测试、范围与引用校验。
- `method/`：最终执行代码与项目配置副本。
- `baseline.json`：本次开始前的分支、HEAD 和既有改动哈希。

本轮 Sorftime 产品 Request 消耗为 0，项目模型调用为 0。浏览器页面读取不计作 Sorftime Request。未充值、提交或推送；保留既有需求文档和 `src/tests/` 改动。SP-043B 继续 `BUSINESS VALUE HUMAN REVIEW PENDING`。

## 能力边界和下一步

Sorftime 当前已接入的商品、变体及关键词接口不能表达本次买家条件；其文档中的关键词邮编监控不能替代报价核验。普通实时商品更新是否有其他可用能力尚不能据此作供应商全局否定。此次改用项目自有浏览器证明了页面与邮编条件采集路径。

下一步在同一入口补齐可审计的报价资格：明确品相、币种、卖家绑定，以及不依赖满额免邮或 Prime 的单包运费。页面不提供的字段继续未知，不自动进入购物车或结账补数。取得足够证据后，再建立新版本交接并让 PDS 做适用性与经营复核。当前 `business_evidence_eligible=false`、`pds_submission=false`，没有把这批部分观察塞入固定绑定旧版本的 PDS 回执。

参考实现说明：[Playwright Python](https://playwright.dev/python/docs/library)、[浏览器支持](https://playwright.dev/python/docs/browsers)。
