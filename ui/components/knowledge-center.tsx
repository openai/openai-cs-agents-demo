"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  Archive,
  CheckCircle2,
  FileText,
  Plus,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";
import {
  createDocument,
  deprecateDocument,
  fetchDocument,
  fetchDocuments,
  type KnowledgeDocument,
  type KnowledgeSearchResult,
  publishDocument,
  testKnowledgeSearch,
  uploadDocument,
} from "@/lib/platform-api";

const statusLabels: Record<KnowledgeDocument["status"], string> = {
  draft: "草稿",
  processing: "处理中",
  review_pending: "待审核",
  published: "已发布",
  failed: "失败",
  deprecated: "已下线",
};

const statusStyles: Record<KnowledgeDocument["status"], string> = {
  draft: "bg-zinc-100 text-zinc-700",
  processing: "bg-sky-50 text-sky-700",
  review_pending: "bg-amber-50 text-amber-700",
  published: "bg-emerald-50 text-emerald-700",
  failed: "bg-red-50 text-red-700",
  deprecated: "bg-zinc-200 text-zinc-600",
};

type EditorState = {
  title: string;
  category: KnowledgeDocument["category"];
  content: string;
};

const emptyEditor: EditorState = {
  title: "",
  category: "product",
  content: "",
};

export function KnowledgeCenter() {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [selected, setSelected] = useState<KnowledgeDocument | null>(null);
  const [creating, setCreating] = useState(false);
  const [editor, setEditor] = useState<EditorState>(emptyEditor);
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const items = await fetchDocuments();
      setDocuments(items);
      if (selected) {
        const next = items.find((item) => item.id === selected.id);
        if (next) setSelected({ ...selected, ...next });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "知识文档加载失败");
    }
  }, [selected]);

  useEffect(() => {
    void refresh();
  }, []);

  const openDocument = async (document: KnowledgeDocument) => {
    setCreating(false);
    setError(null);
    try {
      setSelected(await fetchDocument(document.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "文档加载失败");
    }
  };

  const submitDocument = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const document = await createDocument(editor);
      setEditor(emptyEditor);
      setCreating(false);
      setSelected(document);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "文档创建失败");
    } finally {
      setBusy(false);
    }
  };

  const handleUpload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const document = await uploadDocument(file, "product");
      setSelected(document);
      setCreating(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "文档上传失败");
    } finally {
      setBusy(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const changeStatus = async (action: "publish" | "deprecate") => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const document =
        action === "publish"
          ? await publishDocument(selected.id)
          : await deprecateDocument(selected.id);
      setSelected(document);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "文档状态更新失败");
    } finally {
      setBusy(false);
    }
  };

  const searchKnowledge = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const response = await testKnowledgeSearch(query.trim());
      setSearchResults(response.results);
      setCreating(false);
      setSelected(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "检索测试失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="flex h-full min-h-0 flex-col bg-white">
      <div className="flex min-h-16 shrink-0 flex-wrap items-center gap-3 border-b border-zinc-200 px-4 py-3 sm:px-6">
        <div>
          <h1 className="text-base font-semibold text-zinc-900">知识中心</h1>
          <p className="text-xs text-zinc-500">{documents.length} 个企业文档</p>
        </div>
        <form onSubmit={searchKnowledge} className="ml-auto flex min-w-0 flex-1 sm:max-w-md">
          <div className="flex h-9 min-w-0 flex-1 items-center border border-zinc-300 bg-white px-3 focus-within:border-teal-700">
            <Search className="mr-2 h-4 w-4 shrink-0 text-zinc-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="检索测试"
              className="min-w-0 flex-1 bg-transparent text-sm outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={busy || !query.trim()}
            className="h-9 bg-zinc-900 px-3 text-sm font-medium text-white disabled:opacity-40"
          >
            测试
          </button>
        </form>
        <input
          ref={fileInput}
          type="file"
          accept=".pdf,.docx,.md,.markdown,.txt,.html,.htm"
          className="hidden"
          onChange={(event) => void handleUpload(event.target.files?.[0])}
        />
        <button
          type="button"
          title="上传文档"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
          className="flex h-9 w-9 items-center justify-center border border-zinc-300 text-zinc-700 hover:bg-zinc-50 disabled:opacity-40"
        >
          <Upload className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={() => {
            setCreating(true);
            setSelected(null);
            setSearchResults(null);
          }}
          className="flex h-9 items-center gap-2 bg-teal-700 px-3 text-sm font-medium text-white hover:bg-teal-800"
        >
          <Plus className="h-4 w-4" /> 新建
        </button>
      </div>

      {error && (
        <div className="border-b border-red-200 bg-red-50 px-6 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(300px,0.8fr)_minmax(420px,1.2fr)]">
        <div className="min-h-0 overflow-y-auto border-b border-zinc-200 lg:border-b-0 lg:border-r">
          <div className="flex h-11 items-center border-b border-zinc-200 bg-zinc-50 px-4 text-xs font-semibold uppercase text-zinc-500">
            文档
            <button
              type="button"
              title="刷新"
              onClick={() => void refresh()}
              className="ml-auto flex h-8 w-8 items-center justify-center hover:bg-zinc-200"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
          {documents.length === 0 ? (
            <div className="px-4 py-12 text-center text-sm text-zinc-500">暂无企业文档</div>
          ) : (
            documents.map((document) => (
              <button
                key={document.id}
                type="button"
                onClick={() => void openDocument(document)}
                className={`flex w-full items-start gap-3 border-b border-zinc-100 px-4 py-3 text-left hover:bg-zinc-50 ${
                  selected?.id === document.id ? "bg-teal-50" : ""
                }`}
              >
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-zinc-900">
                    {document.title}
                  </span>
                  <span className="mt-1 block text-xs text-zinc-500">
                    v{document.version} · {document.category}
                  </span>
                </span>
                <span className={`shrink-0 px-2 py-1 text-xs ${statusStyles[document.status]}`}>
                  {statusLabels[document.status]}
                </span>
              </button>
            ))
          )}
        </div>

        <div className="min-h-0 overflow-y-auto bg-zinc-50 p-4 sm:p-6">
          {creating && (
            <form onSubmit={submitDocument} className="mx-auto max-w-3xl bg-white p-5 ring-1 ring-zinc-200">
              <h2 className="text-sm font-semibold text-zinc-900">新建知识文档</h2>
              <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_180px]">
                <label className="text-xs font-medium text-zinc-600">
                  标题
                  <input
                    required
                    value={editor.title}
                    onChange={(event) => setEditor({ ...editor, title: event.target.value })}
                    className="mt-1 h-10 w-full border border-zinc-300 px-3 text-sm outline-none focus:border-teal-700"
                  />
                </label>
                <label className="text-xs font-medium text-zinc-600">
                  分类
                  <select
                    value={editor.category}
                    onChange={(event) =>
                      setEditor({
                        ...editor,
                        category: event.target.value as KnowledgeDocument["category"],
                      })
                    }
                    className="mt-1 h-10 w-full border border-zinc-300 bg-white px-3 text-sm outline-none focus:border-teal-700"
                  >
                    <option value="product">产品</option>
                    <option value="support">售后支持</option>
                    <option value="compliance">安全合规</option>
                    <option value="sales">售前销售</option>
                  </select>
                </label>
              </div>
              <label className="mt-4 block text-xs font-medium text-zinc-600">
                正文
                <textarea
                  required
                  value={editor.content}
                  onChange={(event) => setEditor({ ...editor, content: event.target.value })}
                  className="mt-1 min-h-72 w-full resize-y border border-zinc-300 p-3 text-sm leading-6 outline-none focus:border-teal-700"
                />
              </label>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setCreating(false)}
                  className="h-9 border border-zinc-300 px-4 text-sm text-zinc-700 hover:bg-zinc-50"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={busy}
                  className="h-9 bg-teal-700 px-4 text-sm font-medium text-white disabled:opacity-40"
                >
                  保存草稿
                </button>
              </div>
            </form>
          )}

          {!creating && selected && (
            <article className="mx-auto max-w-3xl bg-white p-5 ring-1 ring-zinc-200">
              <div className="flex flex-wrap items-start gap-3 border-b border-zinc-200 pb-4">
                <div className="min-w-0 flex-1">
                  <h2 className="break-words text-base font-semibold text-zinc-900">
                    {selected.title}
                  </h2>
                  <p className="mt-1 text-xs text-zinc-500">
                    {selected.category} · {selected.language} · v{selected.version}
                  </p>
                </div>
                <span className={`px-2 py-1 text-xs ${statusStyles[selected.status]}`}>
                  {statusLabels[selected.status]}
                </span>
                {selected.status !== "published" && selected.status !== "deprecated" && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void changeStatus("publish")}
                    className="flex h-9 items-center gap-2 bg-emerald-700 px-3 text-sm font-medium text-white disabled:opacity-40"
                  >
                    <CheckCircle2 className="h-4 w-4" /> 发布
                  </button>
                )}
                {selected.status === "published" && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void changeStatus("deprecate")}
                    className="flex h-9 items-center gap-2 border border-zinc-300 px-3 text-sm text-zinc-700 disabled:opacity-40"
                  >
                    <Archive className="h-4 w-4" /> 下线
                  </button>
                )}
              </div>
              <div className="mt-5 whitespace-pre-wrap break-words text-sm leading-7 text-zinc-700">
                {selected.content}
              </div>
            </article>
          )}

          {!creating && !selected && searchResults !== null && (
            <div className="mx-auto max-w-3xl">
              <h2 className="text-sm font-semibold text-zinc-900">检索结果</h2>
              {searchResults.length === 0 ? (
                <div className="mt-3 border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                  未找到充分证据
                </div>
              ) : (
                <div className="mt-3 space-y-3">
                  {searchResults.map((result) => (
                    <article key={`${result.document_id}-${result.section}`} className="bg-white p-4 ring-1 ring-zinc-200">
                      <div className="flex items-center gap-2">
                        <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-zinc-900">
                          {result.title}
                        </h3>
                        <span className="text-xs text-zinc-500">
                          {(result.score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-zinc-500">{result.section}</p>
                      <p className="mt-3 line-clamp-5 whitespace-pre-wrap text-sm leading-6 text-zinc-700">
                        {result.content}
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </div>
          )}

          {!creating && !selected && searchResults === null && (
            <div className="flex h-full min-h-64 items-center justify-center text-sm text-zinc-500">
              选择文档或创建新文档
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
