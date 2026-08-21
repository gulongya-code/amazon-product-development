# ORGANIC BUYER NEED DISCOVERY PILOT V0.1

Status: **COMPLETE**

- Baseline commit: `c25d9eebf74cf0c80f99c3202666f57eee3b13eb`
- Run ID: `organic-buyer-need-discovery-pilot:d3590e265b4c424b12773dd7b44bf2d7dd40a9ff5663032a469b0afac03e77b3`
- Marketplace: `US`
- Cohort: Pet Supplies > Dog Travel Water Bottles
- Discovery origin: `ASIN_REVERSE_RETURNED`
- Discovery role: `DISCOVERED_CANDIDATE`
- Human seeded: `false`

## 1. ASIN 样本

确定性策略：keyword cohort page 1, provider traffic descending, response order。Provider cohort total=662。
TASK-SP-031 报告只保存了 cohort 规则和统计，没有保存200个 ASIN identity 列表；因此本次按相同 `dog water bottle / last7days / traffic desc` 合同重新获取当前 Top 20。Provider total 已从 SP-031 的658变为本次的662，本样本不是历史响应的 byte-for-byte 子集。

| # | ASIN |
|---:|---|
| 1 | `B09F5ZYV7M` |
| 2 | `B0GTQZG7J3` |
| 3 | `B098KBJNMH` |
| 4 | `B07GKRKT33` |
| 5 | `B09CH9W2XS` |
| 6 | `B0BZR44DQF` |
| 7 | `B07Q56TTD4` |
| 8 | `B089W25KG3` |
| 9 | `B07C79KZLL` |
| 10 | `B0DP3MMNFM` |
| 11 | `B0F6MS3VGK` |
| 12 | `B0H48MWCQL` |
| 13 | `B07GKP62WV` |
| 14 | `B0H33P63FW` |
| 15 | `B0CJ29S8PG` |
| 16 | `B07DFX3Q79` |
| 17 | `B08MBDK747` |
| 18 | `B0DBJCDR4W` |
| 19 | `B0B497MVR1` |
| 20 | `B0FN8B96G8` |

## 2. API 调用与 Credits

调用前预计 credits：**22**；gate：**30**。
完成执行请求：**22**；前置失败执行请求：**2**；任务累计请求：**24**。
完成执行已知 credits：**23**；前置计入 credits：**2**；任务累计 accounted credits：**25**；完成执行中 credit 未回传调用：**0**。
前置执行说明：首次执行完成1次cohort和1次reverse后被本地deterministic-ID校验阻断；未继续其余ASIN或keyword_info。两次均按接口计费规则计入1 credit，X-Cost-Credits未持久化。

| # | Operation | ASIN | Page | Returned | Provider total | X-Cost-Credits | Status |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | `keyword_asin_analysis` | UNKNOWN | 1 | 20 | 662 | 1 | SUCCEEDED |
| 2 | `asin_keywords` | B09F5ZYV7M | 1 | 20 | 1096 | 1 | SUCCEEDED |
| 3 | `asin_keywords` | B0GTQZG7J3 | 1 | 20 | 627 | 1 | SUCCEEDED |
| 4 | `asin_keywords` | B098KBJNMH | 1 | 20 | 320 | 1 | SUCCEEDED |
| 5 | `asin_keywords` | B07GKRKT33 | 1 | 20 | 204 | 1 | SUCCEEDED |
| 6 | `asin_keywords` | B09CH9W2XS | 1 | 20 | 167 | 1 | SUCCEEDED |
| 7 | `asin_keywords` | B0BZR44DQF | 1 | 20 | 734 | 1 | SUCCEEDED |
| 8 | `asin_keywords` | B07Q56TTD4 | 1 | 20 | 323 | 1 | SUCCEEDED |
| 9 | `asin_keywords` | B089W25KG3 | 1 | 20 | 358 | 1 | SUCCEEDED |
| 10 | `asin_keywords` | B07C79KZLL | 1 | 20 | 312 | 1 | SUCCEEDED |
| 11 | `asin_keywords` | B0DP3MMNFM | 1 | 20 | 443 | 1 | SUCCEEDED |
| 12 | `asin_keywords` | B0F6MS3VGK | 1 | 20 | 348 | 1 | SUCCEEDED |
| 13 | `asin_keywords` | B0H48MWCQL | 1 | 20 | 232 | 1 | SUCCEEDED |
| 14 | `asin_keywords` | B07GKP62WV | 1 | 20 | 31 | 1 | SUCCEEDED |
| 15 | `asin_keywords` | B0H33P63FW | 1 | 20 | 155 | 1 | SUCCEEDED |
| 16 | `asin_keywords` | B0CJ29S8PG | 1 | 20 | 138 | 1 | SUCCEEDED |
| 17 | `asin_keywords` | B07DFX3Q79 | 1 | 15 | 15 | 1 | SUCCEEDED |
| 18 | `asin_keywords` | B08MBDK747 | 1 | 20 | 181 | 1 | SUCCEEDED |
| 19 | `asin_keywords` | B0DBJCDR4W | 1 | 20 | 237 | 1 | SUCCEEDED |
| 20 | `asin_keywords` | B0B497MVR1 | 1 | 20 | 141 | 1 | SUCCEEDED |
| 21 | `asin_keywords` | B0FN8B96G8 | 1 | 20 | 656 | 1 | SUCCEEDED |
| 22 | `keyword_info` | UNKNOWN | UNKNOWN | 20 | 20 | 2 | SUCCEEDED |

## 3. Keyword Corpus

- Raw ASIN-keyword relations: **395**
- Unique keywords: **107**
- Cross-relation duplicates: **288**
- ASINs with returned keyword evidence: **20/20**
- First-page-only ASINs: **19**
- Traffic availability: `{'AVAILABLE': 395}`

> Keyword frequency and ASIN coverage are discovery coverage only. They are not Search Demand Share. Provider traffic is not Search Volume.

## 4. Top 50 discovered search terms

| # | Search term | ASIN coverage | Coverage share | Provider traffic support | Best organic rank |
|---:|---|---:|---:|---:|---:|
| 1 | dog water bottle | 20 | 1 | 118942 | 1 |
| 2 | dog water bottle portable | 18 | 0.9 | 78309 | 1 |
| 3 | portable dog water bottle | 18 | 0.9 | 23110 | 1 |
| 4 | dog travel water bottle | 18 | 0.9 | 16789 | 1 |
| 5 | water bottle for dogs | 17 | 0.85 | 11413 | 1 |
| 6 | travel dog water bottle | 17 | 0.85 | 10144 | 1 |
| 7 | portable dog water bowl | 16 | 0.8 | 31275 | 2 |
| 8 | portable water bowl for dog | 14 | 0.7 | 11130 | 1 |
| 9 | dog portable water bottle | 14 | 0.7 | 6816 | 1 |
| 10 | travel water bowl for dogs | 13 | 0.65 | 8197 | 2 |
| 11 | dog water bottles | 12 | 0.6 | 1805 | 2 |
| 12 | pet water bottle | 10 | 0.5 | 4156 | 2 |
| 13 | dog water bottle with built-in bowl | 9 | 0.45 | 5700 | 1 |
| 14 | portable water bottle for dogs | 9 | 0.45 | 3065 | 1 |
| 15 | dog travel water bowl | 8 | 0.4 | 3112 | 2 |
| 16 | water bottle for dogs on walks | 8 | 0.4 | 2739 | 1 |
| 17 | travel dog bowls | 7 | 0.35 | 3587 | 11 |
| 18 | dog water bowl travel | 7 | 0.35 | 2066 | 2 |
| 19 | collapsible dog bowls | 6 | 0.3 | 2756 | 82 |
| 20 | travel dog water bowl | 6 | 0.3 | 1854 | 4 |
| 21 | dog water | 5 | 0.25 | 3274 | 14 |
| 22 | rover and oak dog water bottle | 5 | 0.25 | 2120 | 1 |
| 23 | trailhound dog water bottle | 5 | 0.25 | 1650 | 1 |
| 24 | portable dog bowl | 5 | 0.25 | 1460 | 10 |
| 25 | dog bottle water dispenser | 5 | 0.25 | 943 | 4 |
| 26 | dog travel accessories | 4 | 0.2 | 4355 | 1 |
| 27 | insulated dog water bottle | 4 | 0.2 | 705 | 2 |
| 28 | water bottle for dog | 4 | 0.2 | 213 | 21 |
| 29 | pupflask | 3 | 0.15 | 787 | 1 |
| 30 | botella de agua para perros | 3 | 0.15 | 696 | 7 |
| 31 | portable dog water | 3 | 0.15 | 623 | 5 |
| 32 | dog water bowl | 3 | 0.15 | 581 | 112 |
| 33 | stainless steel dog water bottle | 3 | 0.15 | 547 | 1 |
| 34 | portable dog water bottle with bowl | 3 | 0.15 | 500 | 15 |
| 35 | poop bags for dogs | 3 | 0.15 | 0 | UNKNOWN |
| 36 | dog accessories | 2 | 0.1 | 4814 | 14 |
| 37 | collapsible water bottles | 2 | 0.1 | 4657 | 73 |
| 38 | dog walking accessories | 2 | 0.1 | 1165 | 8 |
| 39 | dog water dispenser | 2 | 0.1 | 953 | 72 |
| 40 | collapsible dog water bowl | 2 | 0.1 | 586 | 34 |
| 41 | dog travel bowls | 2 | 0.1 | 578 | 32 |
| 42 | trailhound insulated dog water bottle | 2 | 0.1 | 528 | 1 |
| 43 | dog beach essentials | 2 | 0.1 | 427 | 46 |
| 44 | dog portable water bowl | 2 | 0.1 | 378 | 6 |
| 45 | water bottle dog | 2 | 0.1 | 342 | 6 |
| 46 | springer dog water bottle | 2 | 0.1 | 217 | 2 |
| 47 | dog water bowl dispenser | 2 | 0.1 | 216 | 130 |
| 48 | travel water bottle for dogs | 2 | 0.1 | 195 | 18 |
| 49 | pupflask dog water bottle | 2 | 0.1 | 133 | 4 |
| 50 | dog bottle | 2 | 0.1 | 128 | 26 |

## 5. Buyer Need 分类

- Matched Buyer Need objects: **207**
- Matched keyword relations: **207**
- UNKNOWN keyword relations: **188**
- UNKNOWN ratio: **0.4759493670886075949367088608**
- Need type distribution: `{'ATTRIBUTE_NEED': 102, 'AUDIENCE': 2, 'SPECIFICATION_PREFERENCE': 3, 'USE_CASE': 100}`

Taxonomy 未识别的 provider-returned term 保持 UNKNOWN；本任务没有修改 Taxonomy 或规则以提高 Recall。

## 6. Semantic Clusters / Top Organic Buyer Needs

| # | Cluster | Member count | Keyword relations | Source ASINs | ASIN coverage share |
|---:|---|---:|---:|---:|---:|
| 1 | Outdoor Portability | 191 | 191 | 19 | 0.95 |
| 2 | Walking Need | 11 | 11 | 10 | 0.5 |
| 3 | Stainless Steel Need | 3 | 3 | 3 | 0.15 |
| 4 | Large Dogs Need | 2 | 2 | 2 | 0.1 |

每个 cluster 的 `need_id` 均通过 `buyer_need_links` 回溯到 discovery record；record 继续回溯到 source ASIN、query execution、raw response 和 `searchTerm`。

## 7. Buyer Need Map

- Map ID: `buyer-need-map:290f0eedb105290f0e8760a2845577c8373790c9f293060406d20d452a180792`
- Cluster count: **4**
- Source evidence count: **399**
- Search Demand Share: **UNKNOWN**（没有完整 search population denominator）
- Review Mention Share: **UNKNOWN**
- Sales/Revenue associated shares: **UNKNOWN**

本报告仅额外发布 Discovered Keyword Count、ASIN Coverage Count/Share、Cluster Member Count 与流量证据可用性。

## 8. keyword_info validation enrichment

Top 20 由 ASIN coverage、provider traffic support、organic rank 和稳定文本排序确定。`keyword_info` 只做 enrichment，不改变 `query_origin=ASIN_REVERSE_RETURNED`。

| # | Keyword | Search volume | ABA rank | CPC | Difficulty | Status |
|---:|---|---:|---:|---:|---:|---|
| 1 | dog water bottle | 10968 | 14765 | 0.97 | 63 | AVAILABLE |
| 2 | dog water bottle portable | 8106 | 22644 | 0.87 | 64 | AVAILABLE |
| 3 | portable dog water bottle | 2630 | 84907 | 0.89 | 64 | AVAILABLE |
| 4 | dog travel water bottle | 1861 | 104103 | 0.83 | 64 | AVAILABLE |
| 5 | water bottle for dogs | 1324 | 143899 | 0.73 | 53 | AVAILABLE |
| 6 | travel dog water bottle | 1125 | 168176 | 0.86 | 62 | AVAILABLE |
| 7 | portable dog water bowl | 4862 | 46553 | 0.98 | 65 | AVAILABLE |
| 8 | portable water bowl for dog | 1643 | 117137 | 0.89 | 58 | AVAILABLE |
| 9 | dog portable water bottle | 803 | 232819 | 0.78 | 63 | AVAILABLE |
| 10 | travel water bowl for dogs | 1522 | 126010 | 0.89 | 57 | AVAILABLE |
| 11 | dog water bottles | 377 | 482891 | 0.88 | 62 | AVAILABLE |
| 12 | pet water bottle | 1008 | 186927 | 0.83 | 57 | AVAILABLE |
| 13 | dog water bottle with built-in bowl | 881 | 212867 | 1.01 | 54 | AVAILABLE |
| 14 | portable water bottle for dogs | 583 | 317193 | 0.78 | 62 | AVAILABLE |
| 15 | dog travel water bowl | 821 | 227905 | 0.93 | 59 | AVAILABLE |
| 16 | water bottle for dogs on walks | 372 | 489834 | 0.8 | 61 | AVAILABLE |
| 17 | travel dog bowls | 3559 | 66257 | 1.01 | 64 | AVAILABLE |
| 18 | dog water bowl travel | 589 | 314188 | 0.84 | 60 | AVAILABLE |
| 19 | collapsible dog bowls | 9350 | 18452 | 0.8 | 64 | AVAILABLE |
| 20 | travel dog water bowl | 613 | 302481 | 0.86 | 59 | AVAILABLE |

## 9. 新发现需求表达

- `dog hiking gear`
- `dog portable water bottle`
- `dog portable water bowl`
- `dog travel`
- `dog travel accessories`
- `dog travel bag`
- `dog travel bowls`
- `dog travel water bottle`
- `dog travel water bowl`
- `dog walking accessories`
- `dog water bottle for walks`
- `dog water bottle portable`
- `dog water bowl travel`
- `dog water travel`
- `large dog water bottle`
- `pet travel water bottle`
- `portable dog bowl`
- `portable dog water`
- `portable dog water bottle with bowl`
- `portable dog water bowl`

## 10. Provenance 与成功标准

| Criterion | Result |
|---|---|
| Discovery Query 不是 HUMAN_PRESET | PASS |
| 至少一个 Provider-returned keyword | PASS |
| ASIN → request → response → searchTerm | PASS |
| Cluster → need_id → discovered keyword | PASS |
| 至少一个新需求表达 | PASS |

Organic Buyer Need Discovery success: **YES**

## 11. 数据限制

- 样本是 `dog water bottle` keyword cohort 的 top-traffic 20 ASIN，不是 Browse Node census。
- SP-031 未持久化原200个 ASIN identity；本次为相同合同的当前确定性重建，Provider total 由658变为662。
- 每个 ASIN 仅获取 reverse keyword 第一页、最多20条；不能代表完整 ASIN keyword population。
- Provider traffic 单位、方法和精确窗口未确认，不能替代 Search Volume。
- `keyword_info` 只覆盖 Top 20 discovered terms，不能作为完整 denominator。
- Taxonomy Recall 未在本任务校准；UNKNOWN 不代表没有 Buyer Need。
- 未使用 Review、Bullet、Q&A 或 AI/LLM/Embedding。

## 12. 下一阶段建议

1. 先复核本次 Top UNKNOWN search terms，再单独立项做 Taxonomy coverage audit；不要在本任务内改规则。
2. 若 lineage 和 credits 稳定，再扩大到100 ASIN；继续设置明确 credits gate。
3. 增加 Review/Bullet evidence 后进行 source-mixed discovery，但保持 source origin 分离。
4. 获得 Browse Node/category cohort denominator 后，再讨论类目覆盖和 Demand Share。
