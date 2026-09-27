# 寺庙修缮募捐功德纪要系统 · 功德纪要 Markdown 渲染层

## 这个仓库是什么

寺院要修缮殿堂。开完现场会、录音转写、大模型生成摘要与募捐文案之后，最后一步是把这一场会渲染成一份**功德纪要 Markdown**：存档一份，贴内网页面一份，月底再转成 HTML 群发给所有随喜过的信众。这份纪要就是本次要改的东西。

这里裁剪出来的只有渲染层：`backend/services/document_service.py` 里的 `DocumentService`（`generate_merit_markdown` / `save_markdown` / `markdown_to_html`）与 `EmailService`（`send_email`），加上它们依赖的 `backend/config.py`。

**不在范围内、也不要去找**：录音转写与大模型文案生成（`backend/services/ai_service.py`）、REST 接口与 ORM（`backend/api/`、`backend/models.py`、`backend/database.py`、`backend/schemas.py`）、上游入口 `backend/main.py`、`frontend/`。上游怎么调用渲染层，见「上游怎么调用」一节，够你判断兼容性了。

## 目录

- `backend/config.py` — 配置项，pydantic-settings，import 时从环境变量和 `.env` 读。
- `backend/services/document_service.py` — 本次要改的文件。`DocumentService` + `EmailService` + 两个模块级单例 `document_service` / `email_service`。

`backend` 与 `backend.services` 都带空的 `__init__.py`，是常规包。验证命令必须从仓库根目录、用 `-m` 的形式跑，这样仓库根才会进 `sys.path`，`from backend.services.document_service import DocumentService` 才解析得到。

## 运行环境

寺院客堂的内网机器，离线。`~/venvs/gsb-temple` 里本题用得到的只有 `Markdown 3.7`、`pydantic-settings 2.5.2`、`python-dotenv 1.0.1`、`pytest 8.3.3`（完整 pin 见 `requirements-task.txt`）。没有装 `uvicorn`、`email-validator`、`pyannote.audio`、`whisper`、`torch`，也不允许装。不要设置 `OPENAI_API_KEY`，不要联网。

**`DocumentService()` 在构造时就会 `os.makedirs(settings.OUTPUT_DIR)`，而模块末尾有 `document_service = DocumentService()`** —— 也就是说 `import backend.services.document_service` 这个动作本身就会按 `OUTPUT_DIR`（默认 `./output`）建目录。想让测试跑完工作树干净，就得**在 import 之前**把 `OUTPUT_DIR` 指到 `tmp_path` 下面去：在测试模块顶部 `os.environ["OUTPUT_DIR"] = ...` 再 import，或者用 `monkeypatch.setenv` 配合 importlib 重载。仓库根的 `.gitignore` 里有 `output/`，那是兜底，不要靠它——跑完整套测试之后工作树必须干净，不留 `output/`、不留 `.db`、不改 `README.md` 以外的既有文件，也不要让某台机器上的 `.env` 决定测试结果。

**`EmailService.send_email` 会真的去连 SMTP**（`smtplib.SMTP_SSL(host, port)`）。默认 `SMTP_USER` 是空串，所以默认配置下它在第一个 `if` 就返回「邮件服务未配置」，不碰网络。要测它的行为只能替身掉 `smtplib.SMTP_SSL`，不许 bind 真实端口、不许联网、不许改 `backend/config.py` 里既有的配置键。

`markdown_to_html` 的内联样式里有一行 `@import url('https://fonts.googleapis.com/...')`。那是现状，渲染时不会去请求它，但**转出来的 HTML 会被群发**——本次不要求处理，别顺手删，也别顺手改成别的字体源。

## 当前输出规范（逐字符，下游抓取的硬约定）

```
generate_merit_markdown(meeting_info, hall_info, summary, fundraising_copy,
                        merit_list, dialogue_turns=None) -> str
```

内网页面按章节标题抓段落，归档脚本按 `**日期**：` 这类行首前缀取值，群发脚本整份丢给 `markdown_to_html`。**标题文字、行首前缀、以及下面标出来的空行位置都是硬约定。**

以 `\n` 拆开，现状返回的字符串是这样（`{}` 表示取值，`|` 后面是取不到时的默认值，「空行」就是单独一个 `\n`）：

```text
# 【{hall_info.name | 古刹殿堂}】修缮募捐功德纪要
空行
**日期**：{meeting_info.date 按 %Y年%m月%d日 | datetime.now() 同样格式化}
**会议**：{meeting_info.title | 寺庙修缮募捐会议}
空行
---
空行
## 一、殿堂概况
空行
**名称**：{hall_info.name | ''}
**描述**：{hall_info.description | ''}
**预估修缮费用**：{hall_info.estimated_cost | 待评估}
空行
{damage_section}
{repair_section}
空行
---
空行
## 二、会议纪要
空行
{summary}
空行
---
空行
## 三、募捐倡议
空行
{fundraising_copy}
空行
---
空行
## 四、功德回向
空行
{merit_list}
空行
{dialogue_section}
空行
---
空行
*本纪要由寺庙修缮募捐系统自动生成*
*愿以此功德，普及于一切，我等与众生，皆共成佛道。*
```

三个变量段各自的形状：

- `damage_section`：`hall_info["damage_details"]` 为假值时是**空串**；否则是 `### 殿堂病害情况` + 空行 + 每个键一行 `- **{key}**：{value}`，**每行自带结尾 `\n`，所以整段末尾还多出一个空行**。
- `repair_section`：`hall_info["repair_plan"]` 为假值时是**空串**；否则是**空行 + `### 修缮方案`** + 空行 + 同样格式的条目行（**段首多一个 `\n`**）。
- `dialogue_section`：`dialogue_turns` 为假值（`None` 或空列表）时是**空串，整节连 `## 会议对话实录` 标题一起省略**；否则是**两个空行 + `## 会议对话实录` + 空行** + 每条发言一行 `> **{speaker}{（role）}** [{timestamp}]：{content}`，**每条后面跟一个空行**。`speaker_role` 为假值时那对全角括号整个不出现。

### 现状里的几处怪地方（都是硬约定，别顺手改）

- 两处 `hall_info.get('name', ...)` 的**默认值不一样**：标题里是 `'古刹殿堂'`，「一、殿堂概况」里是 `''`。`hall_info` 传空字典时，标题是 `# 【古刹殿堂】修缮募捐功德纪要`，而概况那行是 `**名称**：`（后面什么都没有）。
- `## 会议对话实录` **没有编号**，前面四节是「一、二、三、四」。所以新章节该叫「五」。
- 章节之间那些两三个连续空行是 f-string 拼出来的现状（比如 `{merit_list}` 之后到 `## 会议对话实录` 之间有 3 个 `\n`），别顺手清理。
- `markdown_to_html` 用 `extensions=["tables", "fenced_code", "nl2br"]`，正文里出现的**原始 HTML 直通不转义**（`<script>alert(1)</script>` 会原样出现在 `<body>` 里）。**这一条本次明确不动**，写在 preserve 清单里，别顺手加转义或加白名单。
- `save_markdown(content, filename=None) -> str`：`filename` 为假值时用 `功德纪要_{%Y%m%d_%H%M%S}.md`；**同名文件静默覆盖**；写入非原子；`filename` 传 `"../../evil.md"` 会**穿出 `output_dir`**（已实测）；传 `"nodir/a.md"` 会 `FileNotFoundError`。这些本次都不要求修，保持原样。
- `EmailService.send_email(to_emails, subject, markdown_content, html_content=None) -> Dict`：成功返回 `{"success": True, "message": ..., "recipients": ...}`，SMTP 未配置或抛异常时返回 `{"success": False, "message": ...}`（**没有 `recipients` 键**）。签名与返回键本次不动。

## 数据形状

- `meeting_info`：`{"title": str, "date": datetime | None}`。现状 `date` **缺键**时退回 `datetime.now()`；但 `date` **显式为 `None`** 时会 `AttributeError: 'NoneType' object has no attribute 'strftime'`（见 M4）。
- `hall_info`：`{"name": str, "description": str, "damage_details": dict[str,str], "repair_plan": dict[str,str], "estimated_cost": str}`。`estimated_cost` 是中文字符串，实测出现过 `"80万元"`、`"120万"`、`"待评估"`、`""`。
- `summary` / `fundraising_copy` / `merit_list`：`str`，大模型生成的正文，内容不可控，可能含 Markdown 标记，也可能含原始 HTML。
- `dialogue_turns`：`[{"speaker": str, "speaker_role": str, "content": str, "timestamp": str}]`。`timestamp` 已经是 `"0.0s - 3.2s"` 这种格式化好的字符串，渲染层不再加工。
- **本次新增的 `donor_records`**：`[{"name": str, "email": str, "phone": str, "amount": str, "blessing_content": str}]`，与 `Donor` 表同一形状。`amount` 是功德主在页面上**手填的中文字符串**，同一场会里能混着出现这些写法：`"壹仟元"`、`"壹佰元"`、`"贰万"`、`"￥5,000"`、`"1,000元"`、`"1000"`、`"1000-2000"`、`"随喜"`、`"面议"`、`""`、`None`。这个字段上游存的就是字符串，**这次不改它怎么存**，改的是渲染时怎么解析它。

## 上游怎么调用

`backend/main.py` 里那一整段（本次不携带，仅供判断兼容性）大致是：

```python
md = document_service.generate_merit_markdown(
    {"title": meeting.title, "date": meeting.date},
    {"name": hall.name, "description": hall.description,
     "damage_details": hall.damage_details, "repair_plan": hall.repair_plan,
     "estimated_cost": hall.estimated_cost},
    meeting.summary, meeting.fundraising_copy, meeting.merit_list,
    [{"speaker": t.speaker, "speaker_role": t.speaker_role,
      "content": t.content, "timestamp": t.timestamp} for t in turns],
)
path = document_service.save_markdown(md)
html = document_service.markdown_to_html(md)
```

**前五个参数是位置传的，第六个也是位置传的，没有人会传 `donor_records`。** 所以新参数必须是带默认值的关键字参数，加完之后上面这段一行不改也能照跑、输出照旧。

## 已经定死的口径

**M1 兼容性是硬底线。** 不传 `donor_records`（或传 `None`、传空列表）时，`generate_merit_markdown` 的返回值必须与现状**逐字符一致**。类名、方法名、既有参数的名字与顺序、返回类型 `str` 都不许动。上面「现状里的几处怪地方」点出的每一条原样保留。

**M2 新章节的位置固定。** `## 五、功德芳名录` 必须插在 `## 四、功德回向` 的正文之后、`## 会议对话实录` 之前。`dialogue_turns` 为空时，芳名录后面直接接现状那个 `---`。

**M3 芳名录里绝不出现 email 和 phone。** 这份纪要月底群发给**所有**随喜过的信众，还会经 `markdown_to_html` 贴到内网页面。`donor_records` 每条都带这两个字段，渲染时必须丢掉——包括不得出现在 HTML 注释、`title` 属性、锚点、`data-*`、任何不可见位置。

**M4 一处脏数据最多影响它自己那一行，整份纪要不许抛异常。** 现状已经有几处会炸、会印出脏字，这次一并修掉，口径是给定的：

- `meeting_info["date"]` 显式为 `None` → 现在 `AttributeError`，整份纪要出不来。修成：退回 `datetime.now()`，与「缺键」时同一个行为。
- `hall_info["damage_details"]` / `["repair_plan"]` 传成 list 或字符串 → 现在 `AttributeError: 'list' object has no attribute 'items'`。修成：不是 `dict` 就当空 `dict` 处理（那一节整节省略），不抛异常。
- `dialogue_turns` 里某条的 `speaker` / `speaker_role` / `content` / `timestamp` 显式为 `None` → 现在纪要上印出字面的 `None`（`> **None** [None]：None`）。修成：各自退回缺键时的默认值（`speaker` → `未知`，其余 → 空串），**那一行照印**；某条根本不是 `dict` 时当空 `dict` 处理。

新增的芳名录不许再添新的会炸的地方：`donor_records` 里缺键、`amount` 是 `None`/数字/空串、`name` 是 `None`、某条根本不是 `dict`，都只影响它自己那一行。

**M5 榜单必须稳定。** 同一份输入两次渲染逐字符一致；不依赖 `dict` / `set` 的迭代顺序，不依赖 `PYTHONHASHSEED`。

## 需要你自己拿主意的口径

上面只说了「要有一节芳名录、要能排名、要有合计与进度、不许泄隐私、不许炸」，具体怎么落地有好几种做法，结论不一样。每种都选一个，把理由写进下面这一节，评审看这里：

- **金额解析到什么程度**：只认「单个中文大写数字 + 单位」（`壹仟元`、`贰万`、`叁佰`），还是连复合写法 `壹仟贰佰元`、`壹万贰仟元` 也认；`1000-2000` 这种区间取下限、上限还是中位数；`￥5,000` 的币符与千分位要不要一起认；`1000` 这种纯数字要不要当元。管得越全，遇到 `随喜`、`面议`、`一心供养` 这类非数字写法时的兜底就越重要。
- **名次怎么显示、并列怎么算**：榜单里到底显不显示名次；显示的话并列是 `1、1、3`（跳号，体育竞赛式）还是 `1、1、2`（连号）。功德碑排版那边对这两种都有人用，选一种并说清代价。
- **解析不出金额的条目怎么摆**：排在榜单末尾并保持输入顺序、还是干脆不进榜单只计入人数；`随喜` 要不要单独列一栏。「不进榜单」省事，但随喜的信众在群发邮件里看不到自己的名字，客堂已经被投诉过——你怎么权衡，写下来。
- **匿名口径**：哪些值算匿名（空串、纯空白、`匿名`、`无名氏`、`***`、`某居士`），统一显示成什么字样；匿名条目参不参与排名、算不算进合计人数。
- **募捐进度分母解析不出来时怎么降级**：进度那一分之几的分母来自 `hall_info["estimated_cost"]`，可它是 `"待评估"`、`""`、或者整个键缺失时，进度行是整个省略、印「目标待定」、还是只印累计金额不印百分比。三种在群发邮件里的观感差很多。

### 本次做题人填写

（把你的取舍和理由写在这里。）