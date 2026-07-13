"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Cable,
  CheckCircle2,
  CircleOff,
  RefreshCw,
  Save,
  DownloadCloud,
  TestTube2,
} from "lucide-react";
import {
  configureConnector,
  fetchConnectors,
  testConnector,
  syncDocumentConnector,
  type ConnectorConfiguration,
} from "@/lib/platform-api";

type ConnectorType = ConnectorConfiguration["connector_type"];

const definitions: Record<
  ConnectorType,
  {
    label: string;
    provider: ConnectorConfiguration["provider"];
    scopes: string[];
    credential: string;
    fields: { key: string; label: string; placeholder: string }[];
  }
> = {
  crm: {
    label: "CRM 客户账户",
    provider: "hubspot",
    scopes: ["crm.objects.companies.read"],
    credential: "env://HUBSPOT_ACCESS_TOKEN",
    fields: [
      { key: "company_id", label: "可信企业 ID", placeholder: "HubSpot company ID" },
      { key: "base_url", label: "API 地址（可选）", placeholder: "https://api.hubapi.com" },
    ],
  },
  ticketing: {
    label: "工单系统",
    provider: "jira",
    scopes: ["read:jira-work"],
    credential: "env://JIRA_API_TOKEN",
    fields: [
      { key: "base_url", label: "Atlassian 站点", placeholder: "https://company.atlassian.net" },
      { key: "account_email", label: "服务账户邮箱", placeholder: "service@example.com" },
      { key: "sample_ticket_key", label: "测试工单编号", placeholder: "SUP-100" },
    ],
  },
  usage: {
    label: "产品用量与账单",
    provider: "usage_api",
    scopes: ["usage:read", "billing:read"],
    credential: "env://USAGE_API_TOKEN",
    fields: [
      { key: "base_url", label: "只读 API 地址", placeholder: "https://usage.example.com" },
      { key: "account_id", label: "可信账户 ID", placeholder: "account_123" },
      { key: "usage_path", label: "用量路径", placeholder: "/v1/usage" },
    ],
  },
  documents: {
    label: "企业文档源",
    provider: "confluence",
    scopes: ["read:page:confluence", "read:space:confluence"],
    credential: "env://CONFLUENCE_API_TOKEN",
    fields: [
      { key: "base_url", label: "Atlassian 站点", placeholder: "https://company.atlassian.net" },
      { key: "account_email", label: "服务账户邮箱", placeholder: "service@example.com" },
      { key: "space_id", label: "知识空间 ID", placeholder: "123456" },
    ],
  },
};

const environmentLabels = {
  sandbox: "沙箱",
  staging: "预发布",
  production: "生产",
};

export function ConnectorCenter() {
  const [connectors, setConnectors] = useState<ConnectorConfiguration[]>([]);
  const [connectorType, setConnectorType] = useState<ConnectorType>("crm");
  const [environment, setEnvironment] = useState<ConnectorConfiguration["environment"]>("sandbox");
  const [enabled, setEnabled] = useState(false);
  const [credentialReference, setCredentialReference] = useState(definitions.crm.credential);
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const definition = useMemo(() => definitions[connectorType], [connectorType]);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setConnectors(await fetchConnectors());
    } catch (err) {
      setError(err instanceof Error ? err.message : "连接器列表加载失败");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectType = (nextType: ConnectorType) => {
    setConnectorType(nextType);
    setCredentialReference(definitions[nextType].credential);
    setSettings({});
    setEnabled(false);
    setNotice(null);
  };

  const save = async () => {
    setBusy("save");
    setError(null);
    setNotice(null);
    try {
      const updated = await configureConnector({
        connector_type: connectorType,
        provider: definition.provider,
        environment,
        status: enabled ? "enabled" : "disabled",
        credential_reference: credentialReference,
        granted_scopes: definition.scopes,
        settings: Object.fromEntries(
          Object.entries(settings).filter(([, value]) => value.trim().length > 0),
        ),
      });
      setConnectors((items) => {
        const remaining = items.filter(
          (item) =>
            !(item.connector_type === updated.connector_type && item.environment === updated.environment),
        );
        return [...remaining, updated].sort((a, b) =>
          `${a.connector_type}:${a.environment}`.localeCompare(`${b.connector_type}:${b.environment}`),
        );
      });
      setNotice("连接器配置已保存。密钥值只从后端环境变量读取。 ");
    } catch (err) {
      setError(err instanceof Error ? err.message : "连接器保存失败");
    } finally {
      setBusy(null);
    }
  };

  const runTest = async (connector: ConnectorConfiguration) => {
    setBusy(connector.id);
    setError(null);
    setNotice(null);
    try {
      await testConnector(connector.id);
      setNotice(`${definitions[connector.connector_type].label}只读测试通过。`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "连接器测试失败");
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  const syncDocuments = async (connector: ConnectorConfiguration) => {
    setBusy(connector.id);
    setError(null);
    setNotice(null);
    try {
      const result = await syncDocumentConnector(connector.id);
      setNotice(`同步完成：${result.synced.length} 个版本进入待审核，跳过 ${result.skipped} 个页面。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "文档同步失败");
    } finally {
      setBusy(null);
    }
  };

  const disable = async (connector: ConnectorConfiguration) => {
    setBusy(connector.id);
    setError(null);
    setNotice(null);
    try {
      const updated = await configureConnector({
        connector_type: connector.connector_type,
        provider: connector.provider,
        environment: connector.environment,
        status: "disabled",
        credential_reference: connector.credential_reference,
        granted_scopes: connector.granted_scopes,
        settings: connector.settings,
      });
      setConnectors((items) =>
        items.map((item) => (item.id === connector.id ? updated : item)),
      );
      setNotice(`${definitions[connector.connector_type].label}已禁用，新请求不会再调用该连接器。`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "连接器禁用失败");
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-50">
      <div className="flex min-h-16 shrink-0 items-center border-b border-zinc-200 bg-white px-4 py-3 sm:px-6">
        <div>
          <h1 className="text-base font-semibold text-zinc-900">连接器</h1>
          <p className="text-xs text-zinc-500">真实系统只读接入，外部写权限禁止启用</p>
        </div>
        <button
          type="button"
          title="刷新"
          onClick={() => void refresh()}
          className="ml-auto flex h-9 w-9 items-center justify-center border border-zinc-300 text-zinc-700 hover:bg-zinc-50"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {error && <div className="border-b border-red-200 bg-red-50 px-6 py-2 text-sm text-red-700">{error}</div>}
      {notice && <div className="border-b border-emerald-200 bg-emerald-50 px-6 py-2 text-sm text-emerald-800">{notice}</div>}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="border-b border-zinc-200 bg-white px-4 py-5 sm:px-6">
          <div className="mx-auto max-w-6xl">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {(Object.keys(definitions) as ConnectorType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => selectType(type)}
                  className={`flex min-h-12 items-center gap-3 border px-3 text-left text-sm font-medium ${
                    connectorType === type
                      ? "border-zinc-900 bg-zinc-900 text-white"
                      : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50"
                  }`}
                >
                  <Cable className="h-4 w-4 shrink-0" />
                  {definitions[type].label}
                </button>
              ))}
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <label className="grid gap-1.5 text-sm text-zinc-700">
                环境
                <select
                  value={environment}
                  onChange={(event) => setEnvironment(event.target.value as ConnectorConfiguration["environment"])}
                  className="h-10 border border-zinc-300 bg-white px-3 outline-none focus:border-teal-700"
                >
                  <option value="sandbox">沙箱</option>
                  <option value="staging">预发布</option>
                  <option value="production">生产</option>
                </select>
              </label>
              <label className="grid gap-1.5 text-sm text-zinc-700">
                密钥引用
                <input
                  value={credentialReference}
                  onChange={(event) => {
                    const name = event.target.value.replace(/^env:\/\//i, "").toUpperCase();
                    setCredentialReference(`env://${name}`);
                  }}
                  className="h-10 border border-zinc-300 px-3 font-mono text-sm outline-none focus:border-teal-700"
                />
              </label>
              {definition.fields.map((field) => (
                <label key={field.key} className="grid gap-1.5 text-sm text-zinc-700">
                  {field.label}
                  <input
                    value={settings[field.key] ?? ""}
                    onChange={(event) =>
                      setSettings((current) => ({ ...current, [field.key]: event.target.value }))
                    }
                    placeholder={field.placeholder}
                    className="h-10 border border-zinc-300 px-3 text-sm outline-none focus:border-teal-700"
                  />
                </label>
              ))}
              <label className="grid gap-1.5 text-sm text-zinc-700 lg:col-span-2">
                灰度用户 ID（可选，逗号分隔）
                <input
                  value={settings.allowed_user_ids ?? ""}
                  onChange={(event) =>
                    setSettings((current) => ({
                      ...current,
                      allowed_user_ids: event.target.value,
                    }))
                  }
                  placeholder="support-user-1, presales-user-2"
                  className="h-10 border border-zinc-300 px-3 text-sm outline-none focus:border-teal-700"
                />
              </label>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-zinc-700">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(event) => setEnabled(event.target.checked)}
                  className="h-4 w-4 accent-teal-700"
                />
                启用该环境配置
              </label>
              <span className="text-xs text-zinc-500">Scope：{definition.scopes.join(" · ")}</span>
              <button
                type="button"
                disabled={busy === "save" || !credentialReference.startsWith("env://")}
                onClick={() => void save()}
                className="ml-auto flex h-10 items-center gap-2 bg-zinc-900 px-4 text-sm font-medium text-white disabled:opacity-40"
              >
                <Save className="h-4 w-4" /> 保存配置
              </button>
            </div>
          </div>
        </div>

        <div className="p-4 sm:p-6">
          <div className="mx-auto max-w-6xl">
            <h2 className="text-sm font-semibold text-zinc-900">已配置连接器</h2>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {connectors.length === 0 ? (
                <div className="flex min-h-40 items-center justify-center border border-zinc-200 bg-white text-sm text-zinc-500 lg:col-span-2">
                  暂无连接器配置
                </div>
              ) : (
                connectors.map((connector) => (
                  <article key={connector.id} className="border border-zinc-200 bg-white p-4">
                    <div className="flex items-start gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center bg-zinc-100 text-zinc-700">
                        <Cable className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-semibold text-zinc-900">
                            {definitions[connector.connector_type].label}
                          </h3>
                          <span className="bg-zinc-100 px-2 py-1 text-xs text-zinc-600">
                            {environmentLabels[connector.environment]}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-zinc-500">
                          {connector.provider} · {connector.credential_reference}
                        </p>
                      </div>
                      {connector.last_health_status === "healthy" ? (
                        <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
                      ) : (
                        <CircleOff className="h-5 w-5 shrink-0 text-zinc-400" />
                      )}
                    </div>
                    <div className="mt-4 flex items-center gap-3 border-t border-zinc-100 pt-3">
                      <span className="text-xs text-zinc-500">
                        {connector.status === "enabled" ? "已启用" : "未启用"}
                        {connector.last_error_status ? ` · ${connector.last_error_status}` : ""}
                      </span>
                      <button
                        type="button"
                        disabled={busy === connector.id}
                        onClick={() => void runTest(connector)}
                        className="ml-auto flex h-9 items-center gap-2 border border-zinc-300 px-3 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-40"
                      >
                        <TestTube2 className="h-4 w-4" /> 只读测试
                      </button>
                      {connector.status === "enabled" && (
                        <button
                          type="button"
                          disabled={busy === connector.id}
                          onClick={() => void disable(connector)}
                          className="flex h-9 items-center gap-2 border border-red-200 px-3 text-sm text-red-700 hover:bg-red-50 disabled:opacity-40"
                        >
                          <CircleOff className="h-4 w-4" /> 禁用
                        </button>
                      )}
                      {connector.status === "enabled" && connector.connector_type === "documents" && (
                        <button
                          type="button"
                          disabled={busy === connector.id}
                          onClick={() => void syncDocuments(connector)}
                          className="flex h-9 items-center gap-2 border border-teal-200 px-3 text-sm text-teal-800 hover:bg-teal-50 disabled:opacity-40"
                        >
                          <DownloadCloud className="h-4 w-4" /> 同步待审核
                        </button>
                      )}
                    </div>
                  </article>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
