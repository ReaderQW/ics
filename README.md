# 校园消费生态智能访谈系统

一个基于 Streamlit 的访谈系统，用于围绕校园商铺（食堂、便利店、干洗店）进行结构化调研。

- 学生端：仅通过商家传播的专属链接进入并完成访谈
- 商家端：生成链接/二维码、管理报告、预览与导出

## 功能特性

### 1. 双端分工
- 学生端：无店铺选择、无链接生成、无报告导出、无历史恢复入口
- 商家端：负责生成专属链接和二维码，并查看/管理报告

### 2. URL 直达访谈
系统支持以下链接参数：
- `mode`：页面模式（`interview` / `owner`）
- `scenario`：访谈场景（`canteen` / `convenience_store` / `dry_cleaner`）
- `shop`：具体商铺名称（可选）

示例：
- `http://localhost:8501?mode=interview&scenario=canteen&shop=一食堂`
- `http://localhost:8501?mode=owner`

说明：当前项目是单页 Streamlit 应用，仅支持在根地址后追加查询参数（`?mode=...`）。

### 3. 二维码分享
- 可为当前访谈会话生成可分享链接
- 自动生成二维码并支持下载 PNG 文件

### 4. 商家报告后台
- 左侧支持筛选与批量操作，右侧支持列表与预览切换
- 报告列表支持分页（每页条目数可配置，0 表示不分页）
- 右侧列表为表格化展示：勾选 / 标题 / 类型 / 场景 / 店铺
- 单选模式：通过勾选框选择当前操作条目，右上角统一执行改名 / 预览 / 导出 / 删除
- 支持重命名（默认 `b#xxxxxxx` 或 `s#xxxxxxx`，可编辑且限长）
- 支持按名称搜索、按类型/场景/店铺筛选
- 批量操作：
  - 批量导出（单击即下载 ZIP）
  - 批量删除
  - AI 生成总结报告（新条目类型为总结报告）

### 5. 店铺定制问题生成
- 每个场景支持店铺选项（如一食堂、7-Eleven、蓝鲸干洗等）
- 问题模板自动注入具体店铺名称，生成更有针对性的提问

### 6. 结束前观点确认摘要
- 在访谈结束前自动生成“观点确认摘要”
- 用户可回复“确认”完成访谈
- 用户可回复“需要修改”补充观点，系统会更新摘要并再次确认

### 7. 无效文本自动过滤
- 自动过滤辱骂词、刷屏字符、空洞无效输入
- 被过滤内容不会进入有效槽位采集
- 系统会提示用户文明、具体地重新回答
- 过滤次数会计入会话统计与报告

### 8. 报告导出
- 支持 Markdown、PDF、Word 导出
- 单条导出与批量导出均走浏览器下载，不依赖用户手动找本地目录
- 报告包含：
  - 调研场景与具体店铺
  - 槽位反馈详情
  - 观点确认摘要
  - 用户补充说明
  - 无效输入过滤次数
  - AI 分析建议（会话完成后）

### 9. 访谈流程优化
- 新会话会先发送开场白，再发送首个正式问题（不再跳过第一问）
- 跑题时会拉回主线；对过短回答最多补充追问一次，避免无限卡在同一问题
- 学生端发送消息后显示“AI 正在思考”，处理中禁用输入，避免重复提交

### 10. 会话清理
- 系统会周期性清理长时间未完成且无报告的会话记录（默认 24 小时）
- 用于减少学生重复刷新链接造成的冗余会话文件

## 项目结构

```text
app.py
requirements.txt
config/
  interview_outline.json
  scenarios/
    canteen.json
    convenience_store.json
    dry_cleaner.json
data/
  reports/
  sessions/
reports/
src/
  analyzer.py
  config_loader.py
  controller.py
  data_manager.py
  generator.py
  llm_client.py
  models.py
  prompts.py
  report.py
  report_exporter.py
  report_repository.py
  session_persistence.py
```

## 环境要求
- Python 3.10+
- 可用网络（如需启用 LLM 能力）

## 安装与运行

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 配置环境变量（可选）
在项目根目录创建 `.env`，可配置：
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_TIMEOUT_SECONDS`（可选，默认 30）
- `APP_BASE_URL`（用于生成分享链接，默认 `http://localhost:8501`）

3. 启动应用
```bash
streamlit run app.py
```

## 数据说明

### 会话数据
- 路径：`data/sessions/*.json`
- 保存字段包括：会话状态、已采集槽位、对话历史、店铺名称、无效输入次数、确认摘要与补充说明、关联报告 ID

### 报告数据
- 路径：`data/reports/*.json`
- 报告类型：
  - `base`（普通报告，命名前缀 `b#`）
  - `summary`（总结报告，命名前缀 `s#`）

### 场景配置
- 路径：`config/scenarios/*.json`
- 每个场景包含：
  - `greeting` / `farewell`
  - `shop_options`
  - `slots`（问题、追问触发词、追问问题）

## 技术栈
- Streamlit：交互界面
- Pydantic：数据模型与校验
- OpenAI SDK：LLM 调用
- ReportLab / python-docx：报告导出
- qrcode：二维码生成

## 后续可扩展方向
- 增加后台图表（店铺趋势、问题热力图）
- 增加更精细的内容审核策略
- 支持多角色权限（访谈员/经营者/管理员）
- 对接数据库替代本地 JSON 存储

## 常见问题排查

### 1) LLM 调用失败（如 `Connection error`）
请依次检查：
- `LLM_BASE_URL` 是否可达
- `LLM_API_KEY` 是否有效
- `LLM_MODEL` 是否为当前服务可用模型
- 本机网络/代理/防火墙是否允许访问对应 API

可通过设置 `LLM_TIMEOUT_SECONDS` 适当放宽超时。
