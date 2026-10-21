# 多伦多，吃什么？

手机优先、纯静态的私人食单 MVP。Python 标准库负责本机数据流程，原生 HTML/CSS/JS 负责筛选；无需数据库、账号或前端框架。

**当前状态：代码已完成，真实店铺尚未导入。** `data/raw/places.csv` 目前是仅含表头的模板。不要把空清单的 needs_review=0 / unresolved=0 读成“所有店已匹配”。用户后续要求已移除“只看我去过的”。未完成事项见 [QUESTIONS.md](QUESTIONS.md)。

## 环境与安全

需要 Python 3.10+、Node.js 22+（跑前端测试）、本机 `gh`（部署）。本机可用 Python 为 `/opt/homebrew/bin/python3`；若 `python3 --version` 是旧版，请换用该路径或建立 venv。

```sh
python3 -m venv .venv
source .venv/bin/activate
# 不安装任何 Python 第三方依赖
```

API key **只读环境变量** `GOOGLE_PLACES_API_KEY`；前端不调用 Places、不持有 key。`.env.example` 仅示意变量名，脚本不会自动加载 `.env`。可以隐藏输入：

```sh
read -s GOOGLE_PLACES_API_KEY
export GOOGLE_PLACES_API_KEY
```

`.gitignore` 排除 `.env*`（示例除外）、真实原始清单、人工评价、匹配输出、API 缓存和 `site/data.json`。代码仓库公开时只发布代码；网页上使用的人工内容本身仍是公开的。不要把私人信息写进备注。

在 Google Cloud 限制 key 仅能使用 Places API（New）；按需限制调用来源。**设预算与预警，并配置每日请求配额。Cloud Budget 是预警，不是自动断电的硬预算上限。** 真正约束调用量还需 API quota、脚本 `--max-calls` 和必要时停用 key。脚本没有隐藏重试。

## 完整流程

### 1. parse：先看真实格式，再解析

把原始文件放到 `data/raw/places.csv`。模板见 `data/raw/places.example.csv`：

```csv
name,address,maps_url,owner_note
```

```sh
python3 scripts/parse_input.py
```

脚本首先打印实际表头和前 5 行，随后解析。支持 UTF-8 BOM、逗号/分号/制表符、CSV 引号内换行；容许表头大小写和首尾空格。列数错乱、缺店名/地址、重复输入会报错并要求修正，绝不猜哪段是地址。`owner_note` 不 trim、不翻译、不润色，原样保留。输出 `data/places_raw.json`。没真实数据时只创建空清单，不添加示例店。

### 2. match：先 dry run，再确认调用数

```sh
python3 scripts/match.py
# 先阅读“预计 API 调用次数”，确认后才运行下行；N 改为批准数量
python3 scripts/match.py --execute --max-calls N
```

每个未处理的输入调用 1 次 Text Search（New），使用 name + address。field mask 为 `places.id,places.displayName,places.formattedAddress,nextPageToken`，每次最多 20 个候选。仅当**唯一候选、名称严格规范化后相等、完整地址规范化后相等**才确认。地址只做常见街道缩写规范化；地址省略国家/邮编也会进入人工复核，宁可多复核也不误认分店。

多个候选、地址不等、名称不等、还有下一页均 `needs_review: true`。不自动选择最像的店；不自动翻页。零候选进入 `data/unresolved.csv`。候选名称/地址只在终端短暂显示，持久化的候选清单只保留 ID 和匹配结果，不把 Google 候选文案当成自己的数据库。匹配记录可复用，重复运行不会重复请求已完成的输入；修改 name/address 后才重新匹配。流程中途 API 失败即停止，已完成的记录保留。

### 3. 人工确认

打开 `data/match_review.csv`，逐行核对原始输入和 Google Maps 候选：

- `selected_place_id`：填你确认的 ID。无结果的行也可填你手工找到的 ID。
- `confirm_name_and_address`：同时确认名称和完整地址后填 `yes`。
- 候选可用 `https://www.google.com/maps/search/?api=1&query=店名&query_place_id=候选ID` 查看。

```sh
python3 scripts/confirm.py
```

不调用 API。不确定的行留空，保持待复核，不进入前端。不准把不相干店铺的 ID 填进来。

### 4. enrich：补充客观字段

```sh
python3 scripts/enrich.py
# 阅读计划，确认后：
python3 scripts/enrich.py --execute --max-calls M
```

每个唯一已确认 ID 最多调用 1 次 Details，缓存有效则跳过；默认每次请求间隔至少 0.3 秒。field mask 不使用 `*`。

**标准条款下的默认模式只请求 `id,location`**，坐标存于 `data/cache/coordinates/`，30 天后清除。该模式不为不会使用的高价字段付费。

完整 Details 适配器已经实现以下 mask：

```text
id,formattedAddress,location,regularOpeningHours,currentOpeningHours,priceLevel,rating,userRatingCount,types,addressComponents,attributions,businessStatus
```

区域只取 `neighborhood` / `sublocality_level_1` / `sublocality`，缺失就是未填。Google `types` 只保存到 Google 数据中，**不会生成细分菜系**。`currentOpeningHours` 用于未来七天特殊营业安排，`regularOpeningHours` 用于其他日期。`businessStatus` 避免永久/临时停业仍被判定营业。Google 第三方 attribution 随卡片展示。

### 重要：Places 条款与纯静态网站的矛盾

Google 的标准条款没有普遍允许把评分、价位、营业时间等 API 字段保存后作为静态 JSON 再分发。“只存一天”也不是自动获准。官方 [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies) 与 [Service Specific Terms §14](https://cloud.google.com/maps-platform/terms/maps-service-terms) 允许 place_id 长期保存、经纬度最多缓存 30 天；请结合你账户的适用条款核实。

因此默认不写入完整 Details，前端相应字段显示未填。若你实际拥有额外授权，才可在被 gitignore 排除的 `data/cache_permission.json` 中记录：

```json
{
  "reference": "实际适用的书面许可/合同依据，不能填随便一个 URL 冒充授权",
  "allows_static_places_content": true,
  "expires_at": "授权的实际失效时间，ISO-8601，含时区"
}
```

这个文件是授权依据记录，**不是通过填写文件创造许可**。只有确认该授权覆盖请求字段、缓存、静态发布及多用户展示后才能启用。完整详情缓存有效期取 24 小时和许可剩余时间的较小者；不会提交到 Git。未配置授权或授权过期时停止使用并清除本地完整缓存。

```sh
# 刷新：默认只打印计划；不暗中请求
python3 scripts/refresh.py
python3 scripts/refresh.py --execute --max-calls M
# 刷新后重新 merge 和部署；没有前端自动收费请求
```

每次 enrich/refresh/merge 会清理过期缓存；打包会剔除过期数据，浏览器也会检查 expiry，页面每 30 秒重判一次。GitHub Actions 每日重建以移除已发布的过期快照；工作流并非精确定时的合规删除保证。如果实际授权要求更严格的删除时点，应保持这些字段关闭，直到采用满足要求的服务结构。源 secret 中的快照要在到期时删除或替换；不要用 secret 当长期 Google 内容库。`place_id` 和自己输入的原始字段/人工评价可持久化。

### 5. 手填人工字段

```sh
python3 scripts/merge.py --init-human
```

生成/增量更新 `data/human_fields.csv`，每行一店，只预填确认的 `place_id`、原始 `name`、原始 `owner_note`。所有其余列初始为空：

| 列 | 填法 |
|---|---|
| owner_note | 只读，每次从原始输入原样恢复，勿编辑 |
| my_take | 自己的一句话评价 |
| best_dish | 必点菜 |
| cuisine_detail | 自己确认的细分菜系 |
| scenario | 一个人 / 约会 / 聚餐 / 赶时间 / 深夜，多选用 `|` 分隔 |
| spicy | 0、1、2、3；空白与 0 不同 |
| price_per_person_cad | 实际人均数字，不加货币符号 |
| skip | `yes` / `no`，空白代表未知；只有明确 yes 才默认隐藏 |

重复 `--init-human` 保留已填写内容，恢复只读原备注；删除输入时先备份人工表，脚本只保留当前确认店。未确认店不会变成空 ID 人工行。不同原始行指向同一个 ID 会要求人工去重，避免覆盖原备注。

### 6. merge 与本机预览

```sh
python3 scripts/merge.py
python3 -m http.server 8787 --bind 127.0.0.1 --directory site
# 浏览器打开 http://127.0.0.1:8787
```

输出 `site/data.json`。人工空白为 `null`，`scenario` 空白也为 `null`，不转换为 `[]`、0 或 false。页面在菜系/场景/辣度启用时，可用“包含未填”决定未知店是否参与；价位/区域/距离缺数据则在相应筛选启用时排除。未知营业时间有单独开关。搜索按原始店名、地址、必点、人工备注匹配，不发网络请求。

默认起点为 UofT St. George 近似中心 `43.6629,-79.3957`，可改坐标或使用浏览器定位。采用 Haversine 直线距离，无地图 SDK、无额外 geocoding 费用；不把直线距离称作步行距离。页面定位只留在内存。

默认时间为 Toronto 的现在。浏览器在其他时区也使用 `America/Toronto`；指定时间按该时区的墙上时间处理，拒绝春季夏令时跳过的不存在时间。秋季重复小时按同一墙上时间判断常规营业；不试图凭 API 周营业表判断店家是否在切换瞬间改变营业。

### 7. GoatCounter 两周统计

在 [GoatCounter](https://www.goatcounter.com/) 建立自己的站点，再编辑 `site/config.json`：

```json
{
  "source_url": "https://maps.app.goo.gl/imnqaBn4KQNFb7wD9",
  "source_author": "你确认的清单作者名",
  "goatcounter_code": "你的站点前缀",
  "test_start_date": "实际开始试用日期 YYYY-MM-DD",
  "test_days": 14
}
```

不配置账户/日期则统计完全不启用。计数脚本使用无 Cookie 的 GoatCounter，发送固定访问路径与固定事件名（例如 `filter-hours`、`filter-cuisine`），不发送搜索词、坐标、具体时间或筛选值；去除 SDK 自动 URL query / screen width，并清空 referrer。遵守 Do Not Track；本地预览默认不计数。测试窗口按 Toronto 日历日计算，到期停止加载统计。

看板可以比较访问总量、各筛选功能使用次数、筛选次数/访问量。无登录、无个人标识意味着**不能可靠识别每位朋友的复访率**，两周后结合参与者反馈。没有创建统计账户，也没有假称已经开始收集数据。

### 8. GitHub Pages 部署

本项目使用 GitHub Actions 发布 `artifacts/pages/`。`.github/workflows/pages.yml` 在 main 更新、手动触发和每天一次时运行测试、打包、发布。API key 不上传，不在 Actions 中运行 Places API。

首次设置：

```sh
gh auth login
# 如果尚无 remote，创建代码仓库；网站是公开静态页
# 本项目已创建 remote 时跳过 repo create
gh repo create toronto-table-mvp --public --source=. --remote=origin
# 首次提交与 push 后，在 Settings → Pages 将 Source 选为 GitHub Actions
# 或使用以下 API（将 OWNER/REPO 替换为实际值）
gh api --method POST repos/OWNER/REPO/pages -f build_type=workflow
git push -u origin main
```

**导入真实数据后**，先在本机完成 match/手填/merge/测试，再上传产物为 repository secret，避免人工备注与 API 快照进入 Git 历史：

```sh
gh secret set FOOD_DATA_JSON < site/data.json
gh workflow run pages.yml --ref main
gh run list --workflow pages.yml --limit 3
```

Actions 通过 `FOOD_DATA_JSON` 写出静态产物，不打印数据。没有 secret 就部署明确的空状态。secret 大小受 GitHub 限制（48 KB）；这是小规模 MVP，如超出限制不要截断数据，应另行决定发布产物方式。网页的 `data.json` 仍是公开资源。Google 字段仅在存在适用静态授权、未过期时进入产物；artifact 保留 1 天，代码仓库从不跟踪这些快照。

在 [GitHub Pages 文档](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) 查看工作流设置。页面 HTTPS 上浏览器定位可用；没有登录或访问白名单，知道链接的人都能访问，适合少量朋友试用但不适合私人资料。

## 脚本与预计调用次数

| 脚本 | 输出/作用 | API 调用 |
|---|---|---|
| parse_input.py | 原始数据 JSON，先打印表头/5行 | 0 |
| match.py | matches.json、match_review.csv、unresolved.csv | U：未缓存或输入改变的行数，每行1次 |
| confirm.py | 应用人工确认并更新 unresolved | 0 |
| enrich.py | 合规范围内的 Details 缓存 | M：确认的唯一 ID 中缺有效缓存的数量 |
| refresh.py | 强制重新 Details + 清过期缓存 | C：全部已确认唯一 ID 数 |
| merge.py | 空人工表 / 合并 site/data.json | 0 |
| build_site.py | 站点白名单文件与有效 JSON | 0 |
| xhs/summarize.py | 手工标签各类占比 | 0 |

新清单首次完整调用上界通常为 **U + C**；候选不会再收费翻页，也不自动重试。默认无额外数据授权时 enrich 仅取 ID/坐标；完整详情授权开启后，rating / price / hours 字段可能提升 SKU。金额不能仅从调用次数推算，按 [官方字段与计费说明](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing) 检查。用户提供的 key 此前仅单独做过 **1 次 Text Search ID 查询**，HTTP 200；未启动真实清单批量调用。

## 测试

```sh
python3 -m unittest discover -s tests -v
node --test tests/hours.test.mjs
```

覆盖：普通开/关边界、18:00–02:00、周六跨周日、休息日、无数据、全天营业、午休、缓存过期、多伦多冬夏时、DST 跳过小时、特殊日期营业优先；空字段、0 与 false 区分、原备注字节内容、输入容错、匹配保守性、小红书占比分母。所有测试使用虚构夹具，不调用 API，不给真实店填评价。

## 小红书标注辅助

独立目录 `xhs/`，不爬取、不自动判断标签。把 `labeling_template.csv` 复制后手工填写，标签仅为：探店合作 / 明显软广 / 素人真实 / 无法判断。

```sh
python3 xhs/summarize.py xhs/your_labels.csv --output xhs/summary.json
```

输出按 query 的各类数量和占比、总体占比。分母为已标注行数，“无法判断”参与分母；空标签单独记数，0 个标注时占比为 null。总体按帖子数加权，不对 query 百分比简单平均。便利样本只能描述这批标注，不能推论整个平台的广告比例。
