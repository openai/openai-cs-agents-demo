"use client";

import {
  ArrowUp,
  BookOpen,
  Bot,
  ChevronRight,
  History,
  LoaderCircle,
  MessageCircle,
  MessageSquarePlus,
  Network,
  Plus,
  ShieldCheck,
  WalletCards,
  Wrench,
  X,
} from "lucide-react";
import {
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ChatKitPanel,
  type ChatKitPanelHandle,
} from "@/components/chatkit-panel";
import {
  fetchPortalThreads,
  type PortalConfig,
  type PortalThreadSummary,
  type SuggestedPrompt,
} from "@/lib/platform-api";

type PortalMode = "welcome" | "conversation";

const promptIcons: Record<NonNullable<SuggestedPrompt["icon"]>, ReactNode> = {
  wrench: <Wrench className="h-4 w-4" />,
  network: <Network className="h-4 w-4" />,
  "shield-check": <ShieldCheck className="h-4 w-4" />,
  "wallet-cards": <WalletCards className="h-4 w-4" />,
  "message-circle": <MessageCircle className="h-4 w-4" />,
  "book-open": <BookOpen className="h-4 w-4" />,
};

function iconForPrompt(prompt: SuggestedPrompt, index: number) {
  if (prompt.icon && promptIcons[prompt.icon]) return promptIcons[prompt.icon];
  const fallbacks = [
    promptIcons.wrench,
    promptIcons.network,
    promptIcons["shield-check"],
    promptIcons["wallet-cards"],
  ];
  return fallbacks[index % fallbacks.length];
}

function formatThreadDate(value: string) {
  const date = new Date(value);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return new Intl.DateTimeFormat("zh-CN", {
    month: sameDay ? undefined : "numeric",
    day: sameDay ? undefined : "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

type HistoryDrawerProps = {
  open: boolean;
  loading: boolean;
  error: string | null;
  threads: PortalThreadSummary[];
  activeThreadId: string | null;
  onClose: () => void;
  onNewThread: () => void;
  onSelectThread: (threadId: string) => void;
};

function HistoryDrawer({
  open,
  loading,
  error,
  threads,
  activeThreadId,
  onClose,
  onNewThread,
  onSelectThread,
}: HistoryDrawerProps) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!open) return;
    closeButtonRef.current?.focus();
  }, [open]);

  const handleDialogKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = Array.from(
      dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        aria-label="关闭会话记录"
        onClick={onClose}
        className="absolute inset-0 bg-black/30"
      />
      <aside
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="thread-history-title"
        onKeyDown={handleDialogKeyDown}
        className="absolute inset-y-0 right-0 flex w-full max-w-sm flex-col border-l border-zinc-200 bg-white shadow-xl"
      >
        <header className="flex h-16 shrink-0 items-center border-b border-zinc-200 px-4">
          <div>
            <h2 id="thread-history-title" className="text-sm font-semibold text-zinc-900">
              会话记录
            </h2>
            <p className="mt-0.5 text-xs text-zinc-500">仅显示当前账户的会话</p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            title="关闭会话记录"
            onClick={onClose}
            className="ml-auto flex h-11 w-11 items-center justify-center text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="shrink-0 border-b border-zinc-200 p-3">
          <button
            type="button"
            onClick={onNewThread}
            className="flex h-11 w-full items-center justify-center gap-2 bg-zinc-900 px-4 text-sm font-medium text-white hover:bg-zinc-800"
          >
            <MessageSquarePlus className="h-4 w-4" /> 新建会话
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex h-40 items-center justify-center text-sm text-zinc-500">
              <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> 正在加载
            </div>
          ) : error ? (
            <div className="m-4 border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {error}
            </div>
          ) : threads.length === 0 ? (
            <div className="flex h-48 flex-col items-center justify-center text-zinc-500">
              <History className="h-6 w-6" />
              <p className="mt-3 text-sm">暂无历史会话</p>
            </div>
          ) : (
            threads.map((thread) => (
              <button
                key={thread.id}
                type="button"
                onClick={() => onSelectThread(thread.id)}
                className={`flex w-full items-start gap-3 border-b border-zinc-100 px-4 py-4 text-left hover:bg-zinc-50 ${
                  activeThreadId === thread.id ? "bg-teal-50" : ""
                }`}
              >
                <MessageCircle className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" />
                <span className="min-w-0 flex-1">
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm font-medium text-zinc-900">
                      {thread.title}
                    </span>
                    <span className="shrink-0 text-xs text-zinc-400">
                      {formatThreadDate(thread.updated_at)}
                    </span>
                  </span>
                  <span className="mt-1 block truncate text-xs text-zinc-500">
                    {thread.preview || "尚无消息"}
                  </span>
                </span>
                <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-zinc-300" />
              </button>
            ))
          )}
        </div>
      </aside>
    </div>
  );
}

export function PortalChatExperience({ config }: { config: PortalConfig }) {
  const { branding, service } = config;
  const chatRef = useRef<ChatKitPanelHandle>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const historyButtonRef = useRef<HTMLButtonElement>(null);
  const composingRef = useRef(false);
  const [mode, setMode] = useState<PortalMode>("welcome");
  const [draft, setDraft] = useState("");
  const [chatReady, setChatReady] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [threads, setThreads] = useState<PortalThreadSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const page = await fetchPortalThreads();
      setThreads(page.data);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "会话记录加载失败");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const openHistory = () => {
    setHistoryOpen(true);
    void loadHistory();
  };

  const closeHistory = () => {
    setHistoryOpen(false);
    requestAnimationFrame(() => historyButtonRef.current?.focus());
  };

  const startNewThread = async () => {
    try {
      await chatRef.current?.setThreadId(null);
    } finally {
      setActiveThreadId(null);
      setDraft("");
      setSendError(null);
      setMode("welcome");
      closeHistory();
      requestAnimationFrame(() => textareaRef.current?.focus());
    }
  };

  const selectThread = async (threadId: string) => {
    if (!chatReady) return;
    setHistoryError(null);
    try {
      await chatRef.current?.setThreadId(threadId);
      setActiveThreadId(threadId);
      setMode("conversation");
      closeHistory();
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "会话打开失败");
    }
  };

  const selectPrompt = (prompt: SuggestedPrompt) => {
    setDraft(prompt.prompt);
    setSendError(null);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const sendFirstMessage = async (event?: FormEvent) => {
    event?.preventDefault();
    const message = draft.trim();
    if (!message || submitting || !chatReady || service.status === "offline") return;

    setSubmitting(true);
    setSendError(null);
    try {
      const sendPromise = chatRef.current?.sendUserMessage({
        text: message,
        newThread: true,
      });
      setMode("conversation");
      setDraft("");
      await sendPromise;
    } catch (error) {
      setMode("welcome");
      setDraft(message);
      setSendError(error instanceof Error ? error.message : "消息发送失败，请重试");
    } finally {
      setSubmitting(false);
    }
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey || composingRef.current) return;
    event.preventDefault();
    void sendFirstMessage();
  };

  const statusClass =
    service.status === "online"
      ? "bg-emerald-500"
      : service.status === "degraded"
        ? "bg-amber-500"
        : "bg-red-500";

  const visiblePrompts = branding.suggested_prompts.slice(0, 4);
  const conversationVisible = mode === "conversation";

  return (
    <main className="flex h-[100dvh] min-h-0 flex-col bg-zinc-100">
      <header className="h-16 shrink-0 border-b border-zinc-200 bg-white">
        <div className="mx-auto flex h-full w-full max-w-6xl items-center px-4 sm:px-6">
          {branding.logo_url ? (
            <img src={branding.logo_url} alt="" className="h-9 w-9 shrink-0 object-contain" />
          ) : (
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center text-white"
              style={{ backgroundColor: branding.primary_color }}
            >
              <Bot className="h-5 w-5" />
            </span>
          )}
          <div className="ml-3 min-w-0">
            <h1 className="truncate text-sm font-semibold text-zinc-900">{branding.assistant_name}</h1>
            <p className="truncate text-xs text-zinc-500">{branding.display_name}</p>
          </div>

          <div className="ml-auto flex items-center gap-1 sm:gap-2">
            {conversationVisible && (
              <button
                type="button"
                title="新建会话"
                onClick={() => void startNewThread()}
                className="flex h-11 w-11 items-center justify-center text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
              >
                <Plus className="h-5 w-5" />
              </button>
            )}
            <button
              ref={historyButtonRef}
              type="button"
              title="会话记录"
              onClick={openHistory}
              className="flex h-11 items-center gap-2 px-3 text-sm font-medium text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
            >
              <History className="h-4 w-4" />
              <span className="hidden sm:inline">会话</span>
            </button>
            <span
              aria-label={service.label}
              title={service.label}
              className="ml-1 flex shrink-0 items-center gap-2 px-1 text-xs text-zinc-500 sm:ml-2"
            >
              <span className={`h-2 w-2 rounded-full ${statusClass}`} />
              <span className="hidden sm:inline">{service.label}</span>
            </span>
          </div>
        </div>
      </header>

      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div
          aria-hidden={!conversationVisible}
          className={`absolute inset-0 bg-white transition-opacity duration-150 ${
            conversationVisible
              ? "visible opacity-100"
              : "pointer-events-none invisible opacity-0"
          }`}
        >
          <ChatKitPanel
            ref={chatRef}
            surface="portal"
            assistantName={branding.assistant_name}
            greeting={branding.welcome_message}
            prompts={branding.suggested_prompts}
            accentColor={branding.primary_color}
            headerEnabled={false}
            historyEnabled={false}
            showStartScreen={false}
            onReady={() => setChatReady(true)}
            onThreadChange={(threadId) => setActiveThreadId(threadId)}
            onResponseEnd={() => {
              if (historyOpen) void loadHistory();
            }}
          />
        </div>

        {!conversationVisible && (
          <section className="h-full overflow-y-auto bg-zinc-50" data-testid="portal-welcome">
            <div className="mx-auto flex min-h-full w-full max-w-4xl flex-col px-4 pb-6 pt-12 sm:px-6 sm:pt-[clamp(64px,10vh,96px)]">
              <div className="w-full">
                <h2 className="max-w-3xl text-[22px] font-semibold leading-[30px] text-zinc-900 sm:text-2xl sm:leading-[34px]">
                  {branding.welcome_message}
                </h2>

                <div className="mt-7 grid grid-cols-2 gap-2.5 sm:mt-8 sm:gap-3">
                  {visiblePrompts.map((prompt, index) => (
                    <button
                      key={`${prompt.label}-${prompt.prompt}`}
                      type="button"
                      onClick={() => selectPrompt(prompt)}
                      className="group flex min-h-[60px] min-w-0 items-center gap-3 border border-zinc-200 bg-white px-3 text-left transition-colors hover:border-zinc-300 hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 sm:min-h-[70px] sm:px-4"
                      style={{ "--tw-ring-color": branding.primary_color } as React.CSSProperties}
                    >
                      <span
                        className="flex h-9 w-9 shrink-0 items-center justify-center bg-zinc-100 text-zinc-600 group-hover:bg-white"
                        aria-hidden="true"
                      >
                        {iconForPrompt(prompt, index)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-zinc-900">
                          {prompt.label}
                        </span>
                        <span className="mt-1 hidden truncate text-xs text-zinc-500 sm:block">
                          {prompt.prompt}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>

                <form onSubmit={sendFirstMessage} className="mt-7 sm:mt-8">
                  <div className="flex min-h-14 items-end gap-2 border border-zinc-300 bg-white p-1.5 shadow-sm focus-within:border-zinc-500">
                    <textarea
                      ref={textareaRef}
                      rows={1}
                      maxLength={2000}
                      value={draft}
                      disabled={service.status === "offline"}
                      aria-label="输入客户问题"
                      placeholder={
                        service.status === "offline"
                          ? "服务暂不可用"
                          : "请输入产品、技术或业务问题..."
                      }
                      onChange={(event) => {
                        setDraft(event.target.value);
                        setSendError(null);
                        event.target.style.height = "auto";
                        event.target.style.height = `${Math.min(event.target.scrollHeight, 120)}px`;
                      }}
                      onKeyDown={handleComposerKeyDown}
                      onCompositionStart={() => {
                        composingRef.current = true;
                      }}
                      onCompositionEnd={() => {
                        composingRef.current = false;
                      }}
                      className="max-h-[120px] min-h-10 min-w-0 flex-1 resize-none bg-transparent px-3 py-2 text-base leading-6 text-zinc-900 outline-none placeholder:text-zinc-400 disabled:cursor-not-allowed"
                    />
                    <button
                      type="submit"
                      title="发送消息"
                      disabled={
                        !draft.trim() ||
                        !chatReady ||
                        submitting ||
                        service.status === "offline"
                      }
                      className="flex h-11 w-11 shrink-0 items-center justify-center text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-35"
                      style={{ backgroundColor: branding.primary_color }}
                    >
                      {submitting ? (
                        <LoaderCircle className="h-5 w-5 animate-spin" />
                      ) : (
                        <ArrowUp className="h-5 w-5" />
                      )}
                    </button>
                  </div>
                  <div className="mt-2 flex min-h-5 items-start gap-2 px-1 text-xs leading-5 text-zinc-500">
                    {sendError ? (
                      <p aria-live="polite" className="text-red-700">
                        {sendError}
                      </p>
                    ) : (
                      <>
                        <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-700" />
                        <p>{branding.support_notice}</p>
                      </>
                    )}
                  </div>
                </form>
              </div>
            </div>
          </section>
        )}
      </div>

      <HistoryDrawer
        open={historyOpen}
        loading={historyLoading}
        error={historyError}
        threads={threads}
        activeThreadId={activeThreadId}
        onClose={closeHistory}
        onNewThread={() => void startNewThread()}
        onSelectThread={(threadId) => void selectThread(threadId)}
      />
    </main>
  );
}
