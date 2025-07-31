"use client";

import { useTheme } from "@/components/theme-provider";
import { Sun, Moon } from "lucide-react";

export function ThemePicker() {
  const { theme, setTheme, colorway, setColorway } = useTheme();

  return (
    <div className="flex items-center gap-2">
      <div className="hidden sm:flex items-center gap-1 rounded-md border border-border bg-background text-foreground p-1 shadow-sm">
        <button
          aria-label="Use Light theme"
          className={`h-8 w-8 rounded-sm flex items-center justify-center hover:bg-muted ${theme === "light" ? "bg-muted" : ""}`}
          onClick={() => setTheme("light")}
        >
          <Sun className="h-4 w-4" />
        </button>
        <button
          aria-label="Use Dark theme"
          className={`h-8 w-8 rounded-sm flex items-center justify-center hover:bg-muted ${theme === "dark" ? "bg-muted" : ""}`}
          onClick={() => setTheme("dark")}
        >
          <Moon className="h-4 w-4" />
        </button>
      </div>
      <div className="flex items-center gap-1">
        <select
          aria-label="Theme"
          className="sm:hidden h-8 rounded-md border border-input bg-background text-foreground text-sm"
          value={theme}
          onChange={(e) => setTheme(e.target.value as any)}
        >
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
        <select
          aria-label="Colorway"
          className="h-8 rounded-md border border-input bg-background text-foreground text-sm"
          value={colorway}
          onChange={(e) => setColorway(e.target.value as any)}
          title="Accent color"
        >
          <option value="blue">Blue</option>
          <option value="slate">Slate</option>
        </select>
      </div>
    </div>
  );
}
