# Enterprise AI Support Agent

面向 AI 企业的客户支持与售前技术咨询 Agent。项目使用智谱 GLM 提供模型推理，基于 OpenAI Agents SDK、ChatKit、FastAPI 和 Next.js 实现多 Agent 路由、工具调用、上下文共享、安全护栏和执行轨迹可视化。

## Agent 团队

- **Triage Agent**：识别意图并路由到专业 Agent。
- **Product Knowledge Agent**：基于受控知识库回答产品、能力与集成问题。
- **Solution Architect Agent**：收集需求，输出初步架构，并在确认后创建销售商机。
- **Technical Support Agent**：诊断 API、Agent、检索、延迟及部署问题，并在确认后创建工单。
- **Account and Billing Agent**：处理套餐、用量、账单、续费和账单复核。
- **Security and Compliance Agent**：处理安全、隐私、部署控制和合规问题。

## 当前能力

- 专业 Agent 之间的自动 handoff。
- 企业客户上下文跨 Agent 共享，并过滤租户 ID、内部备注等敏感字段。
- 产品知识、技术诊断、方案设计、账户用量、账单与合规查询工具。
- 工单、商机和账单案例在创建前要求用户明确确认，并返回审计 ID。
- 相关性、提示词注入、跨租户数据三类输入护栏。
- 独立客户前台 `/support` 与企业管理后台 `/admin`。
- 客户前台不展示 Agent 路由、工具调用、护栏和内部上下文。
- 客户前台使用原生欢迎态、任务入口和首条消息输入框，发送后切换到 ChatKit 会话态。
- 客户前台提供当前用户专属的历史会话抽屉和新建会话流程。
- 实时 Agent 执行工作台，以及按角色显示的后台导航。
- 两组模拟客户与模拟业务数据，便于无外部系统时演示完整流程。
- 开发令牌或 OIDC 身份认证，可信 `tenant_id` 和角色从服务端身份获得。
- 租户感知的线程、消息、Agent context、知识、缺口、审批和审计持久化。
- 企业知识中心：新建、上传、发布、下线和检索测试。
- 支持 PDF、DOCX、Markdown、TXT 和 HTML 文档解析，单文件上限 20 MB。
- 知识未命中返回 `insufficient_evidence`，并进入知识缺口处理队列。
- 工单、商机和账单案例使用服务端审批状态机，模型只能创建待审批提案。
- 所有外部写意图统一生成加密动作草稿；批准后仍只进入人工执行队列。
- HubSpot CRM、Jira、通用用量 API 和 Confluence 的真实只读连接器框架。
- 连接器只读 Scope 校验、密钥引用、健康检查、灰度用户和一键禁用。
- PostgreSQL 持久化、多实例兼容连接层和真实 PostgreSQL 集成测试。
- S3 兼容对象存储、恶意文件扫描、异步文档队列和独立 worker。
- OIDC 授权码 + PKCE、HttpOnly 会话、组角色映射和成员停用。
- 平台自有脱敏 Trace、Prometheus 指标、生产 readiness gate 和告警规则。
- 200 条对话评测集、50 条红队集、规则 grader 和可选智谱语义 grader。
- 知识缺口和审批中心管理界面。
- 租户品牌配置：企业名称、助手名称、Logo、主色、欢迎语、服务声明和建议问题。
- 建议问题支持可配置图标，门户服务状态由后端提供。

本地默认仍使用演示数据和 SQLite，便于无外部凭据时开发。将 `CONNECTOR_MODE` 设置为 `live` 并在管理后台配置只读连接器后，Agent 才会读取真实系统；生产模式绝不回退到演示数据。真实连接器只实现读取，动作草稿批准后也不会向外部系统发送写请求。

生产代码路径已支持 PostgreSQL、S3 兼容对象存储、异步文档 worker 和正式 OIDC 登录。当前检索已提供权限感知的本地混合召回基线：词法重合、短语命中和确定性向量特征共同排序；真实企业语料上的 Recall@5 正式验收、生产向量库和重排模型仍未完成，因此当前版本不能仅凭本地测试结果标记为生产上线。

## 本地运行

需要 Python 3.11+、Node.js 20+ 和智谱 API Key。

```bash
cd python-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

编辑 `python-backend/.env`，设置 `ZAI_API_KEY`。Key 仅保存在本地，不要提交到 Git。然后安装前端依赖并启动：

```bash
cd ../ui
npm install
cp .env.local.example .env.local
npm run dev
```

客户前台地址为 [http://localhost:3000/support](http://localhost:3000/support)，企业管理后台为 [http://localhost:3000/admin](http://localhost:3000/admin)，后端健康检查为 [http://localhost:8000/health](http://localhost:8000/health)。根路径默认跳转到客户前台。

也可以分别启动：

```bash
cd python-backend
.venv/bin/uvicorn main:app --reload --port 8000
```

```bash
cd ui
npm run dev:next
```

## 配置

| 变量 | 用途 | 默认值 |
| --- | --- | --- |
| `ZAI_API_KEY` | 智谱 API 认证 | 必填 |
| `ZAI_BASE_URL` | 智谱 OpenAI 兼容端点 | `https://open.bigmodel.cn/api/paas/v4/` |
| `ZAI_AGENT_MODEL` | 业务 Agent 模型 | `glm-5.2` |
| `ZAI_GUARDRAIL_MODEL` | 护栏分类模型 | `glm-5.2` |
| `OPENAI_TRACING_DISABLED` | 禁用 OpenAI tracing，避免使用智谱 Key 上传 trace | `1` |
| `CORS_ORIGINS` | 允许的前端来源，逗号分隔 | `http://localhost:3000` |
| `NEXT_PUBLIC_CHATKIT_DOMAIN_KEY` | ChatKit 域名密钥 | 本地开发占位值 |
| `AUTH_MODE` | 身份模式：`dev`、`oidc` 或 RoboAge 服务端调用模式 `roboage` | `dev` |
| `DEV_AUTH_TOKEN` | 本地开发令牌 | `local-dev-token` |
| `ROBOAGE_INTERNAL_TOKEN` | `AUTH_MODE=roboage` 时校验 RoboAge 服务端调用；需与 RoboAge `ENTERPRISE_SUPPORT_AGENT_INTERNAL_TOKEN` 一致 | 空 |
| `DEV_TENANT_ID` / `DEV_USER_ID` | 本地开发租户与用户 | `tenant_acme_cn` / `local-admin` |
| `DEV_USER_ROLES` | 本地开发角色，逗号分隔 | 管理员、编辑、审核、客服、终端用户 |
| `OIDC_ISSUER` / `OIDC_AUDIENCE` / `OIDC_JWKS_URL` | 正式 OIDC 验证配置 | OIDC 模式必填 |
| `DATABASE_PATH` | 本地 SQLite 数据库路径 | `./data/enterprise_agent.db` |
| `APP_ENV` | `development` 或 `production` | `development` |
| `DATABASE_URL` | 生产 PostgreSQL URL | 生产必填 |
| `DATA_ENCRYPTION_KEY` | 动作草稿 Fernet 加密密钥 | 生产必填 |
| `CONNECTOR_MODE` / `CONNECTOR_ENV` | 演示或真实连接器及环境 | `demo` / `sandbox` |
| `OBJECT_STORAGE_BACKEND` / `S3_BUCKET` | 文档原文件存储 | 本地 `local`，生产 `s3` |
| `DOCUMENT_PROCESSING_MODE` | 同步或异步文档处理 | 本地 `sync`，生产 `async` |
| `SESSION_SIGNING_KEY` | OIDC 流程和 HttpOnly 会话签名 | 生产必填 |
| `NEXT_PUBLIC_DEV_AUTH_TOKEN` | 前端本地令牌，需与后端一致 | `local-dev-token` |
| `NEXT_PUBLIC_AUTH_MODE` | 前端认证模式：`dev` 或 `oidc` | `dev` |
| `NEXT_PUBLIC_API_BASE_URL` | 前端直连后端根地址；为空时使用 Next.js rewrite | 空 |
| `NEXT_PUBLIC_DEFAULT_APP_SURFACE` | 根路径默认入口：`support` 或 `admin` | `support` |

模型调用通过智谱的 OpenAI 兼容 Chat Completions 接口完成。业务 Agent 使用流式响应与 Function Calling；护栏使用智谱 JSON 模式并在本地执行 Pydantic 校验。若护栏输出无法解析，系统会默认拦截而不是放行。

## RoboAge 服务端集成

RoboAge 工作台通过服务端调用本后端，不直接暴露模型 Key 或 Agent 服务地址到浏览器。生产建议为 RoboAge 单独部署或配置 `AUTH_MODE=roboage`，并设置 `ROBOAGE_INTERNAL_TOKEN`，该值需与 RoboAge 的 `ENTERPRISE_SUPPORT_AGENT_INTERNAL_TOKEN` 一致。

RoboAge 知识源同步使用：

```http
POST /v1/knowledge/documents
```

RoboAge 工作台对话使用：

```http
POST /v1/roboage/chat
```

请求头由 RoboAge 服务端注入：

```http
Authorization: Bearer <ROBOAGE_INTERNAL_TOKEN>
X-RoboAge-Tenant-Id: <enterprise id>
X-RoboAge-User-Id: <user id>
X-RoboAge-Roles: tenant_admin,support_agent
```

响应格式为 `{ answer, thread_id, current_agent, context, citations }`。

## 演示对话

1. `我们的 API 持续出现 429 和超时，请帮我诊断并创建工单。`
2. `我们想为 2 万名员工建设有权限控制的知识库 Agent，请给出初步架构。`
3. `请介绍私有化部署、数据留存和 SOC 2 相关能力。`
4. `请查询 Acme Intelligence 当前套餐、用量和续费日期。`

涉及创建工单、商机或账单案例时，Agent 应先说明将要执行的动作并等待明确确认。

## 接入真实企业系统

Agent 工具边界集中在 `python-backend/enterprise_support/tools.py`，厂商适配器集中在 `python-backend/enterprise_support/connectors.py`：

| 当前工具 | 建议接入 |
| --- | --- |
| `search_product_knowledge` | 企业知识库、向量检索或文档权限服务 |
| `identify_customer_account` | SSO、CRM 与客户主数据 |
| `create_support_ticket` | Zendesk、Jira Service Management、ServiceNow |
| `create_sales_opportunity` | Salesforce、HubSpot |
| `get_billing_summary` / `open_billing_case` | 计量、账单与财务工单系统 |
| `lookup_security_compliance` | Trust Center、GRC 与合同条款库 |
| `request_human_escalation` | 值班、客服队列或企业 IM |

当前正式适配器选择为 HubSpot CRM、Jira、通用只读用量 API 和 Confluence。每个真实工具都从服务端身份中获取 `tenant_id`，不接受模型传入租户 ID。连接器传输层只暴露 `GET`；写操作使用加密草稿、幂等键、权限检查和追加式审计。

## 评测与生产验证

生成或刷新版本化评测集：

```bash
cd python-backend
.venv/bin/python scripts/generate_eval_dataset.py
```

对脱敏运行结果执行完整 grader：

```bash
.venv/bin/python scripts/run_trace_grader.py \
  --dataset ../evals/datasets/conversation-v1.jsonl \
  --results ../evals/results/conversation-results.jsonl \
  --output ../evals/results/conversation-report.json
```

默认要求数据集中每条用例都有结果，缺失用例会导致发布门禁失败。`--semantic` 可启用智谱语义评分；`--allow-partial` 仅用于本地调试。

先对知识召回基准集运行当前检索，再执行 Recall@K 门禁：

```bash
.venv/bin/python scripts/run_knowledge_retrieval.py \
  --dataset ../evals/datasets/knowledge-recall-v1.jsonl \
  --output ../evals/results/knowledge-recall-results.jsonl \
  --k 5

.venv/bin/python scripts/run_knowledge_recall.py \
  --dataset ../evals/datasets/knowledge-recall-v1.jsonl \
  --results ../evals/results/knowledge-recall-results.jsonl \
  --output ../evals/results/knowledge-recall-report.json \
  --k 5 \
  --threshold 0.85
```

生产 Compose 结构位于 `deploy/docker-compose.production.yml`。填写并由密钥管理服务注入生产配置后运行：

```bash
docker compose \
  --env-file deploy/.env.production \
  -f deploy/docker-compose.production.yml \
  up --build
```

生产 readiness 未通过时后端会拒绝启动。文档 worker 也可以独立运行：

```bash
cd python-backend
.venv/bin/python scripts/document_worker.py
```

## 企业知识与审批 API

主要管理接口：

| 接口 | 用途 |
| --- | --- |
| `GET /v1/me` | 当前可信用户、租户与角色 |
| `GET/POST /v1/knowledge/documents` | 文档列表与新建草稿 |
| `POST /v1/knowledge/documents/upload` | 上传并解析企业资料 |
| `POST /v1/knowledge/documents/{id}/publish` | 发布并建立检索切片 |
| `POST /v1/knowledge/documents/{id}/deprecate` | 下线文档 |
| `POST /v1/knowledge/search/test` | 权限感知检索测试 |
| `GET/PATCH /v1/knowledge/gaps` | 知识缺口处理 |
| `GET /v1/approvals` | 审批列表 |
| `POST /v1/approvals/{id}/decision` | 批准或拒绝待执行动作 |
| `GET /v1/audit-logs` | 租户审计日志 |

除 `/health` 外，业务和管理接口均要求可信身份。开发模式使用 Bearer Token；正式部署必须使用 `AUTH_MODE=oidc` 与 `NEXT_PUBLIC_AUTH_MODE=oidc`，不能使用浏览器可见的开发令牌。管理后台未登录时会引导到 `/admin/login`，并通过 `/auth/login` 发起企业 SSO；旧 `/login` 仅作为兼容重定向。

## 后续生产化清单

- 用 PostgreSQL、对象存储和异步任务替换本地 SQLite 与同步文档处理。
- 将 OIDC 接入企业 SSO，完善成员、角色与知识空间授权管理。
- 将本地混合召回基线替换或增强为生产向量库、全文索引、重排模型和正式 Recall@5 评测集。
- 为引用增加受权限保护的文档阅读和段落定位页面。
- 为路由准确率、事实正确性、工具选择、越权、提示词注入和高风险写操作建立 eval 数据集。
- 根据企业数据政策配置 tracing、日志留存、区域和零数据保留要求。
- 接入人工队列，定义 SEV-1、安全、法律和商业承诺的升级 SLA。

完整范围和验收标准见 [第二阶段开发需求文档](docs/phase-2-enterprise-pilot-requirements.md) 和 [第三阶段前后台分离需求文档](docs/phase-3-customer-portal-admin-console-requirements.md)。当前实现进度见 [第二阶段实现状态](docs/phase-2-implementation-status.md) 和 [第三阶段实现状态](docs/phase-3-implementation-status.md)。

## 验证

```bash
cd python-backend
.venv/bin/python -m pytest
```

```bash
cd ui
npm run build
```

## License

MIT，详见 [LICENSE](LICENSE)。
