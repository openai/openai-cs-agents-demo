"use client";

import { Check, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useState } from "react";
import {
  fetchBrandingSettings,
  type TenantBranding,
  updateBrandingSettings,
} from "@/lib/platform-api";

export function BrandingSettings() {
  const [branding, setBranding] = useState<TenantBranding | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setBranding(await fetchBrandingSettings());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "品牌配置加载失败");
    }
  }, []);

  useEffect(() => void load(), [load]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!branding) return;
    setBusy(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await updateBrandingSettings({
        ...branding,
        logo_url: branding.logo_url || null,
      });
      setBranding(updated);
      setSaved(true);
      window.dispatchEvent(new Event("tenant-branding-updated"));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "品牌配置保存失败");
    } finally {
      setBusy(false);
    }
  };

  if (!branding) {
    return (
      <section className="flex h-full items-center justify-center bg-zinc-50 text-sm text-zinc-500">
        {error ?? "正在加载企业设置"}
      </section>
    );
  }

  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-50">
      <div className="flex min-h-16 shrink-0 items-center border-b border-zinc-200 bg-white px-4 py-3 sm:px-6">
        <div>
          <h1 className="text-base font-semibold text-zinc-900">企业品牌</h1>
          <p className="text-xs text-zinc-500">客户前台公开配置</p>
        </div>
        <button
          type="button"
          title="重新加载"
          onClick={() => void load()}
          className="ml-auto flex h-9 w-9 items-center justify-center border border-zinc-300 text-zinc-700 hover:bg-zinc-50"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {error && <div className="border-b border-red-200 bg-red-50 px-6 py-2 text-sm text-red-700">{error}</div>}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <form onSubmit={submit} className="mx-auto grid max-w-7xl gap-0 lg:grid-cols-[minmax(440px,1fr)_minmax(360px,0.8fr)]">
          <div className="space-y-6 p-4 sm:p-6 lg:border-r lg:border-zinc-200">
            <fieldset className="grid gap-4 sm:grid-cols-2">
              <legend className="mb-3 text-sm font-semibold text-zinc-900">品牌信息</legend>
              <label className="text-xs font-medium text-zinc-600">
                企业名称
                <input
                  required
                  maxLength={120}
                  value={branding.display_name}
                  onChange={(event) => setBranding({ ...branding, display_name: event.target.value })}
                  className="mt-1 h-10 w-full border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-teal-700"
                />
              </label>
              <label className="text-xs font-medium text-zinc-600">
                助手名称
                <input
                  required
                  maxLength={120}
                  value={branding.assistant_name}
                  onChange={(event) => setBranding({ ...branding, assistant_name: event.target.value })}
                  className="mt-1 h-10 w-full border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-teal-700"
                />
              </label>
              <label className="text-xs font-medium text-zinc-600 sm:col-span-2">
                Logo 地址
                <input
                  value={branding.logo_url ?? ""}
                  onChange={(event) => setBranding({ ...branding, logo_url: event.target.value })}
                  placeholder="https://... 或 /logo.png"
                  className="mt-1 h-10 w-full border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-teal-700"
                />
              </label>
              <label className="text-xs font-medium text-zinc-600 sm:col-span-2">
                品牌主色
                <span className="mt-1 flex h-10 border border-zinc-300 bg-white">
                  <input
                    type="color"
                    value={branding.primary_color}
                    onChange={(event) => setBranding({ ...branding, primary_color: event.target.value })}
                    className="h-full w-12 cursor-pointer border-0 bg-transparent p-1"
                    title="选择品牌主色"
                  />
                  <input
                    required
                    pattern="#[0-9a-fA-F]{6}"
                    value={branding.primary_color}
                    onChange={(event) => setBranding({ ...branding, primary_color: event.target.value })}
                    className="min-w-0 flex-1 border-l border-zinc-200 px-3 font-mono text-sm outline-none"
                  />
                </span>
              </label>
            </fieldset>

            <fieldset className="space-y-4 border-t border-zinc-200 pt-5">
              <legend className="text-sm font-semibold text-zinc-900">客户文案</legend>
              <label className="block text-xs font-medium text-zinc-600">
                欢迎语
                <textarea
                  required
                  maxLength={500}
                  rows={3}
                  value={branding.welcome_message}
                  onChange={(event) => setBranding({ ...branding, welcome_message: event.target.value })}
                  className="mt-1 w-full resize-y border border-zinc-300 bg-white p-3 text-sm leading-6 outline-none focus:border-teal-700"
                />
              </label>
              <label className="block text-xs font-medium text-zinc-600">
                服务声明
                <textarea
                  required
                  maxLength={500}
                  rows={3}
                  value={branding.support_notice}
                  onChange={(event) => setBranding({ ...branding, support_notice: event.target.value })}
                  className="mt-1 w-full resize-y border border-zinc-300 bg-white p-3 text-sm leading-6 outline-none focus:border-teal-700"
                />
              </label>
            </fieldset>

            <fieldset className="space-y-3 border-t border-zinc-200 pt-5">
              <div className="flex items-center">
                <legend className="text-sm font-semibold text-zinc-900">建议问题</legend>
                <button
                  type="button"
                  title="添加建议问题"
                  disabled={branding.suggested_prompts.length >= 6}
                  onClick={() => setBranding({
                    ...branding,
                    suggested_prompts: [...branding.suggested_prompts, { label: "新问题", prompt: "" }],
                  })}
                  className="ml-auto flex h-8 w-8 items-center justify-center border border-zinc-300 bg-white text-zinc-700 disabled:opacity-40"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
              {branding.suggested_prompts.map((prompt, index) => (
                <div key={index} className="grid gap-2 border border-zinc-200 bg-white p-3 sm:grid-cols-[120px_130px_1fr_36px]">
                  <input
                    required
                    maxLength={24}
                    aria-label={`建议问题 ${index + 1} 标签`}
                    value={prompt.label}
                    onChange={(event) => {
                      const next = [...branding.suggested_prompts];
                      next[index] = { ...prompt, label: event.target.value };
                      setBranding({ ...branding, suggested_prompts: next });
                    }}
                    className="h-9 border border-zinc-300 px-2 text-sm outline-none focus:border-teal-700"
                  />
                  <select
                    aria-label={`建议问题 ${index + 1} 图标`}
                    value={prompt.icon ?? ""}
                    onChange={(event) => {
                      const next = [...branding.suggested_prompts];
                      next[index] = {
                        ...prompt,
                        icon: (event.target.value || null) as typeof prompt.icon,
                      };
                      setBranding({ ...branding, suggested_prompts: next });
                    }}
                    className="h-9 border border-zinc-300 bg-white px-2 text-sm outline-none focus:border-teal-700"
                  >
                    <option value="">自动图标</option>
                    <option value="wrench">技术工具</option>
                    <option value="network">方案架构</option>
                    <option value="shield-check">安全合规</option>
                    <option value="wallet-cards">账户服务</option>
                    <option value="message-circle">客户对话</option>
                    <option value="book-open">知识资料</option>
                  </select>
                  <input
                    required
                    maxLength={500}
                    aria-label={`建议问题 ${index + 1} 内容`}
                    value={prompt.prompt}
                    onChange={(event) => {
                      const next = [...branding.suggested_prompts];
                      next[index] = { ...prompt, prompt: event.target.value };
                      setBranding({ ...branding, suggested_prompts: next });
                    }}
                    className="h-9 min-w-0 border border-zinc-300 px-2 text-sm outline-none focus:border-teal-700"
                  />
                  <button
                    type="button"
                    title="删除建议问题"
                    disabled={branding.suggested_prompts.length <= 1}
                    onClick={() => setBranding({
                      ...branding,
                      suggested_prompts: branding.suggested_prompts.filter((_, itemIndex) => itemIndex !== index),
                    })}
                    className="flex h-9 w-9 items-center justify-center text-zinc-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-30"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </fieldset>

            <div className="flex items-center border-t border-zinc-200 pt-5">
              {saved && (
                <span className="flex items-center gap-2 text-sm text-emerald-700">
                  <Check className="h-4 w-4" /> 已发布
                </span>
              )}
              <button
                type="submit"
                disabled={busy}
                className="ml-auto flex h-10 items-center gap-2 bg-zinc-900 px-4 text-sm font-medium text-white disabled:opacity-50"
              >
                <Save className="h-4 w-4" /> {busy ? "正在保存" : "保存并发布"}
              </button>
            </div>
          </div>

          <aside className="bg-white p-4 sm:p-6">
            <h2 className="text-sm font-semibold text-zinc-900">客户前台预览</h2>
            <div className="mt-4 overflow-hidden border border-zinc-200">
              <div className="flex h-14 items-center border-b border-zinc-200 px-4">
                <span
                  className="flex h-8 w-8 items-center justify-center text-xs font-semibold text-white"
                  style={{ backgroundColor: branding.primary_color }}
                >
                  AI
                </span>
                <div className="ml-3 min-w-0">
                  <p className="truncate text-sm font-semibold text-zinc-900">{branding.assistant_name}</p>
                  <p className="truncate text-xs text-zinc-500">{branding.display_name}</p>
                </div>
              </div>
              <div className="min-h-80 bg-zinc-50 p-5">
                <p className="max-w-sm text-base font-semibold leading-6 text-zinc-900">{branding.welcome_message}</p>
                <div className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                  {branding.suggested_prompts.map((prompt) => (
                    <div key={`${prompt.label}-${prompt.prompt}`} className="border border-zinc-200 bg-white p-3">
                      <p className="text-xs font-semibold text-zinc-900">{prompt.label}</p>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-zinc-500">{prompt.prompt}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="border-t border-zinc-200 px-4 py-3 text-xs leading-5 text-zinc-500">
                {branding.support_notice}
              </div>
            </div>
          </aside>
        </form>
      </div>
    </section>
  );
}
