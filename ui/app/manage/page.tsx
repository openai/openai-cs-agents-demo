"use client";

import { useEffect, useState } from "react";
import { fetchAgentsConfig, putAgentsConfig, fetchEffectiveInstructions } from "@/lib/api";
import type { AgentConfig, RegistryConfig } from "@/lib/types";
import { PanelSection } from "@/components/panel-section";
import { Card, CardContent } from "@/components/ui/card";

function deepClone<T>(x: T): T { return JSON.parse(JSON.stringify(x)); }

export default function ManageAgentsPage() {
  const [cfg, setCfg] = useState<RegistryConfig | null>(null);
  const [effective, setEffective] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const c = await fetchAgentsConfig();
      setCfg(c);
      try {
        const eff = await fetchEffectiveInstructions();
        const map: Record<string, string> = {};
        for (const a of (eff?.agents ?? [])) map[a.name] = a.instructions;
        setEffective(map);
      } catch {
        // ignore preview errors
      }
    })();
  }, []);

  const updateAgent = (idx: number, partial: Partial<AgentConfig>) => {
    setCfg((prev) => {
      if (!prev) return prev;
      const next = deepClone(prev);
      next.agents[idx] = { ...next.agents[idx], ...partial } as AgentConfig;
      return next;
    });
  };

  const save = async () => {
    if (!cfg) return;
    setSaving(true); setError(null);
    try {
      const res = await putAgentsConfig(cfg);
      if (!res.ok) throw new Error(res.error || "Failed to save");
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setSaving(false);
    }
  };

  if (!cfg) {
    return (
      <main className="p-4">
        <div className="text-sm text-muted-foreground">Loading agents…</div>
      </main>
    );
  }

  return (
    <main className="p-4 flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <h1 className="text-lg font-semibold">Manage Agents</h1>
        <div className="ml-auto">
          <button
            className="h-8 px-3 rounded-md bg-primary text-primary-foreground disabled:opacity-50"
            disabled={saving}
            onClick={save}
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      </div>
      {error && <div className="text-sm text-red-600">{error}</div>}

      {cfg.agents.map((a, idx) => (
        <PanelSection key={idx} title={a.name} icon={<span className="w-4 h-4 rounded-sm bg-primary inline-block" />}> 
          <Card className="bg-card border-border">
            <CardContent className="p-4 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-muted-foreground">Name</label>
                  <input
                    className="w-full h-8 rounded-md border border-input bg-background px-2"
                    value={a.name}
                    onChange={(e) => updateAgent(idx, { name: e.target.value })}
                  />
                </div>
                <div className="col-span-2">
                  <label className="text-xs text-muted-foreground">Description</label>
                  <input
                    className="w-full h-8 rounded-md border border-input bg-background px-2"
                    value={a.description}
                    onChange={(e) => updateAgent(idx, { description: e.target.value })}
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-muted-foreground mr-2">Instructions</label>
                <textarea
                  rows={8}
                  className="w-full mt-2 rounded-md border border-input bg-background px-2 py-1"
                  value={(a.instructions as any)?.mode === "custom" ? (a.instructions as any).value : (effective[a.name] ?? "")}
                  onChange={(e) => updateAgent(idx, { instructions: { mode: "custom", value: e.target.value } as any })}
                />
                <div className="text-[11px] text-muted-foreground mt-1">Editing converts builtin instructions to custom text.</div>
              </div>
            </CardContent>
          </Card>
        </PanelSection>
      ))}
    </main>
  );
}
