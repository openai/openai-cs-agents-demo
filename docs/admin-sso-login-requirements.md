# 企业管理后台登录与 SSO 守卫开发需求文档

> 文档版本：V0.1（评审稿）  
> 文档日期：2026-07-13  
> 所属阶段：阶段 3B-UI-C / 阶段 4 生产化补齐  
> 当前状态：本地代码能力已实现，企业 IdP 联调待完成  
> 适用入口：`/admin`、`/admin/login`、`/auth/login`、`/auth/logout`

## 1. 文档目的

本文档定义企业管理后台的登录入口、未登录态、无权限态和退出登录流程。目标是在保留本地开发便利性的同时，让生产环境的 `/admin` 不再依赖浏览器可见的开发令牌，也不出现“无登录直进后台”的产品体验。

本次开发不建设平台自有账号密码系统。生产登录统一使用企业 SSO/OIDC，后台登录页只作为身份提供方跳转入口。

## 2. 当前基线

### 2.1 已具备能力

- 后端已有 OIDC Authorization Code + PKCE 登录入口：`GET /auth/login`。
- 后端已有 OIDC 回调、HttpOnly `enterprise_session` Cookie 和 `POST /auth/logout`。
- `AUTH_MODE=oidc` 时，业务 API 可从 Bearer Token 或 `enterprise_session` Cookie 解析身份。
- `/v1/me` 可返回可信 `tenant_id`、`user_id` 和角色。
- 管理后台已在客户端加载 `/v1/me`，并根据角色过滤导航。
- 管理后台已有无后台角色页面，但它只在成功获取身份后显示。

### 2.2 当前问题

| 编号 | 问题 | 影响 |
| --- | --- | --- |
| AUTH-01 | 本地前端默认用 `NEXT_PUBLIC_DEV_AUTH_TOKEN` 自动加 Bearer Token | 本地体验方便，但生产不能使用浏览器可见令牌 |
| AUTH-02 | `/admin` 没有专门登录页 | 未登录时只显示技术性错误，不像正式产品 |
| AUTH-03 | 客户前台和管理后台共用简单 fetch 认证逻辑 | 后台缺少面向管理角色的登录、无权限和会话过期处理 |
| AUTH-04 | 退出登录入口缺失 | 管理员无法在 UI 中主动结束后台会话 |
| AUTH-05 | OIDC 启用后缺少前端跳转约定 | 401、403、会话过期和 IdP 未配置状态容易混淆 |

## 3. 产品目标

1. 生产环境访问 `/admin` 时，未登录用户看到清晰的企业 SSO 登录页。
2. 登录按钮跳转到后端 `/auth/login?return_to=/admin/workspace`，由后端发起 OIDC 流程。
3. 登录成功后回到原始后台路径，且只允许具备后台角色的用户进入。
4. 已登录但无后台角色的用户看到无权限页面，并可返回客户前台。
5. 会话过期或 401 时，引导重新登录，不展示原始错误堆栈。
6. 后台侧边栏显示当前用户，并提供退出登录入口。
7. 本地开发模式继续支持 dev token 自动登录，避免影响开发效率。

## 4. 非目标

- 不开发用户名/密码登录表单。
- 不存储企业用户密码。
- 不在前端保存 OIDC access token、id token 或刷新令牌。
- 不允许客户前台匿名访问管理后台接口。
- 不把 `tenant_id`、角色或权限判断交给模型或浏览器决定。
- 不把开发令牌用于生产构建或生产运行。

## 5. 角色与权限

### 5.1 后台准入角色

进入 `/admin` 需要至少具备以下角色之一：

- `tenant_admin`
- `knowledge_editor`
- `knowledge_reviewer`
- `support_agent`

具体页面仍沿用现有页面级角色约束。例如连接器、成员与品牌设置仅允许 `tenant_admin`。

### 5.2 无权限处理

已登录但没有后台角色时：

1. 不展示后台导航和管理数据。
2. 展示“无法访问管理后台”页面。
3. 提供返回 `/support` 的入口。
4. 可提供“退出登录”入口，便于切换账号。

## 6. 目标用户体验

### 6.1 本地开发模式

当 `NEXT_PUBLIC_AUTH_MODE=dev`：

1. 前端继续自动附加 `Authorization: Bearer ${NEXT_PUBLIC_DEV_AUTH_TOKEN}`。
2. `/admin` 直接加载 `/v1/me`。
3. 如果 dev token 无效，显示开发环境认证错误，提示检查 `.env.local` 和后端 `.env`。
4. 登录页可存在，但不作为默认必经路径。

### 6.2 生产 OIDC 模式

当 `NEXT_PUBLIC_AUTH_MODE=oidc`：

1. 访问 `/admin` 或任意 `/admin/*` 路径。
2. 前端调用 `/v1/me`。
3. 如果返回 200 且包含后台角色，进入对应页面。
4. 如果返回 200 但无后台角色，显示无权限页面。
5. 如果返回 401，显示登录页，并保留当前 `return_to`。
6. 点击“使用企业 SSO 登录”后跳转到后端 `/auth/login?return_to=<当前后台路径>`。
7. 后端完成 OIDC 后设置 HttpOnly `enterprise_session` Cookie，并重定向回前端。
8. 用户点击退出后，前端调用 `/auth/logout`，清除会话并回到登录页或客户前台。

## 7. 页面与组件需求

### 7.1 登录页

管理后台登录页使用 `/admin/login`。旧 `/login` 仅作为兼容入口，重定向到 `/admin/login`，避免历史链接失效。

页面内容：

- 企业品牌名称和助手名称，优先来自 `/v1/portal/config`；如果未登录无法读取，则使用静态默认文案。
- 标题：“登录企业管理后台”。
- 主按钮：“使用企业 SSO 登录”。
- 辅助入口：“返回客户服务”。
- 状态提示：会话过期、没有权限、认证服务未配置、开发令牌错误。

交互要求：

- 登录按钮使用普通跳转，不通过模型或客户端拼装敏感参数。
- `return_to` 只能是站内路径，且默认 `/admin/workspace`。
- 登录页不得展示 `tenant_id`、内部角色映射、OIDC client secret 或任何令牌。

### 7.2 管理后台守卫

建议将当前 `AdminShell` 的身份加载逻辑拆成明确状态：

```text
loading
  ├── authenticated + admin role -> admin_shell
  ├── authenticated + no admin role -> forbidden
  ├── unauthenticated -> login_prompt
  └── unavailable -> auth_error
```

守卫行为：

- `loading`：显示短文本“正在验证管理权限”。
- `unauthenticated`：显示登录引导，不显示后台导航。
- `forbidden`：显示无权限页面。
- `auth_error`：显示可操作错误，区分后端不可用和认证未配置。

### 7.3 退出登录

后台侧边栏底部增加退出按钮：

- 图标：`LogOut`。
- 文案：`退出登录`。
- OIDC 模式：调用后端 `/auth/logout` 或直接提交表单到 `/auth/logout`。
- dev 模式：显示“开发模式”标签；退出按钮可禁用或只提示修改 dev token。

## 8. 后端需求

### 8.1 保持现有 OIDC 流程

继续复用：

- `GET /auth/login`
- `GET /auth/callback`
- `POST /auth/logout`
- `GET /v1/me`

### 8.2 增强建议

1. `GET /auth/login` 在 `AUTH_MODE!=oidc` 时当前返回 404；前端应把它理解为开发模式不可用，不应展示为生产错误。
2. `POST /auth/logout` 可考虑同时支持 `GET /auth/logout` 或前端表单 POST，以简化浏览器跳转。
3. `/v1/me` 的 401 响应保持明确，不把认证失败伪装成 500。
4. OIDC session cookie 继续使用 `HttpOnly`、`SameSite=Lax`，生产环境使用 `Secure`。
5. `return_to` 校验必须保持站内路径，禁止 `//evil.com` 或完整外部 URL。

## 9. 前端需求

### 9.1 认证配置

需要明确以下变量：

| 变量 | 用途 |
| --- | --- |
| `NEXT_PUBLIC_AUTH_MODE` | 前端认证模式：`dev` 或 `oidc` |
| `NEXT_PUBLIC_DEV_AUTH_TOKEN` | 本地开发 Bearer Token，仅 dev 模式使用 |
| `NEXT_PUBLIC_API_BASE_URL`（可选） | 如前后端不同域，显式指定后端 API 根地址 |

### 9.2 Fetch 行为

`authenticatedFetch` 应满足：

- dev 模式：继续添加 Bearer Token。
- oidc 模式：不添加开发 Bearer Token，使用 `credentials: "include"` 或同站 Cookie。
- 401 不直接抛普通错误，调用方能识别为 `unauthenticated`。
- 403 调用方能识别为 `forbidden`。

### 9.3 路由保护

后台页面应避免在未登录时短暂展示内部导航或数据。身份检查完成前，只展示 loading；失败后只展示登录或错误界面。

## 10. 安全要求

1. 生产构建不得依赖 `NEXT_PUBLIC_DEV_AUTH_TOKEN`。
2. 前端不得读取或存储 `enterprise_session` Cookie。
3. OIDC client secret 只存在后端环境变量。
4. 所有后台 API 继续由后端验证角色，前端角色判断只用于显示控制。
5. 401、403、连接失败和后端未配置必须区分展示。
6. 登录页不允许接受外部跳转地址作为 `return_to`。
7. 退出登录后，后台页面必须重新进入未登录态。

## 11. 验收标准

### 11.1 本地开发

- `NEXT_PUBLIC_AUTH_MODE=dev` 时，访问 `/admin` 可直接进入后台。
- dev token 错误时，显示开发认证错误，不进入后台。
- 本地开发体验不需要配置 OIDC。

### 11.2 OIDC 模式

- 未登录访问 `/admin/workspace` 显示登录页。
- 点击登录跳转到 `/auth/login?return_to=/admin/workspace`。
- OIDC 回调成功后回到 `/admin/workspace`。
- 已登录后台角色用户可以看到后台导航。
- 已登录无后台角色用户只能看到无权限页面。
- 退出登录后再次访问 `/admin` 显示登录页。

### 11.3 安全

- 生产模式下浏览器请求不携带 `local-dev-token`。
- 后台 API 缺少身份时返回 401。
- 后台 API 角色不足时返回 403。
- `return_to=https://example.com`、`return_to=//example.com` 均不会跳出本站。
- 前端源码和响应中不出现 OIDC client secret、id token、access token 或 session token。

## 12. 测试计划

### 12.1 后端测试

- `/auth/login` 只在 `AUTH_MODE=oidc` 启用。
- `_safe_return_to` 拒绝外部 URL 和协议相对 URL。
- `/auth/logout` 清除 `enterprise_session` Cookie。
- OIDC session 过期或签名错误时 `/v1/me` 返回 401。
- 无后台角色调用后台接口返回 403。

### 12.2 前端测试

- `authenticatedFetch` 在 dev 模式添加 Bearer Token。
- `authenticatedFetch` 在 oidc 模式不添加 dev token，并带 Cookie。
- `AdminShell` 对 401 显示登录入口。
- `AdminShell` 对 403 或无后台角色显示无权限页。
- 退出按钮触发 logout 流程。
- 移动端登录页和无权限页无横向滚动。

### 12.3 浏览器验收

至少覆盖：

- 桌面 `1440x900`：登录页、后台工作台、无权限页。
- 移动 `390x844`：登录页、后台移动导航、退出入口。
- 会话过期后刷新后台页面，进入登录页。

## 13. 实施拆分

### AUTH-UI-01 前端认证状态模型

- 修改 `ui/lib/auth.ts`，让调用方区分 401、403 和网络失败。
- 增加认证模式工具函数。
- 保留 dev 模式自动 token。

### AUTH-UI-02 登录页与登录 CTA

- 新增 `/admin/login` 页面，并保留 `/login` 兼容重定向。
- 增加企业 SSO 登录按钮。
- 支持 `return_to` 查询参数。
- 登录页可在无法获取品牌配置时使用静态默认样式。

### AUTH-UI-03 管理后台守卫

- 重构 `AdminShell` 的身份加载错误处理。
- 未登录时显示登录引导。
- 无权限时显示现有 Forbidden 页面并增加退出入口。
- 避免未登录时渲染内部导航。

### AUTH-UI-04 退出登录

- 后台侧边栏增加退出按钮。
- OIDC 模式调用 `/auth/logout`。
- 退出后跳回登录页或客户前台。

### AUTH-BE-01 后端登录/退出细节补齐

- 评估是否增加 `GET /auth/logout` 便利入口。
- 增加 OIDC flow、return_to 和 logout 相关测试。
- 确认 CORS、Cookie、SameSite 和生产域名配置。

### AUTH-DOC-01 文档与环境模板

- 更新 README 配置说明。
- 更新 `.env.local.example` 和 `.env.example` 中认证模式说明。
- 在阶段实现状态中标记登录守卫完成情况。

## 14. 发布与回滚

### 14.1 发布前检查

- `AUTH_MODE=oidc`。
- `NEXT_PUBLIC_AUTH_MODE=oidc`。
- `SESSION_SIGNING_KEY` 已配置且长度足够。
- `FRONTEND_BASE_URL` 与生产前端域名一致。
- `OIDC_REDIRECT_URI` 已在企业 IdP 中登记。
- `CORS_ORIGINS` 包含前端生产域名。

### 14.2 回滚策略

- 前端登录页和后台守卫可以单独回滚到上一版本。
- 后端 OIDC 已有流程不应破坏现有 dev 模式。
- 不允许通过生产配置回退到 `AUTH_MODE=dev` 作为长期解决方案；只能用于本地或临时沙箱排障。

## 15. 待确认问题

1. 企业 IdP 是否提供统一登出端点？如提供，是否需要联动 IdP logout？
2. 生产前后端是否同域？如果不同域，需要确认 Cookie `SameSite`、`Secure`、CORS 和反向代理配置。
3. 是否需要后台“切换租户”能力？本期默认不做，租户来自 OIDC/session。
