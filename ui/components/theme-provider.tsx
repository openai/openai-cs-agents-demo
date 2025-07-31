"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type ThemeMode = "light" | "dark";

interface ThemeContextValue {
  theme: ThemeMode;
  setTheme: (mode: ThemeMode) => void;
  colorway: Colorway;
  setColorway: (cw: Colorway) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

type Colorway = "blue" | "slate";

const STORAGE_KEY = "ui-theme";
const STORAGE_COLORWAY_KEY = "ui-colorway";

function applyThemeClass(mode: ThemeMode) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (mode === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
}

function applyColorwayClass(cw: Colorway) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.remove("palette-blue", "palette-slate");
  if (cw === "slate") root.classList.add("palette-slate");
  else root.classList.add("palette-blue");
}

export function ThemeProvider({ children, defaultTheme = "light" as ThemeMode }: { children: React.ReactNode; defaultTheme?: ThemeMode }) {
  const [theme, setThemeState] = useState<ThemeMode>(defaultTheme);
  const [colorway, setColorwayState] = useState<Colorway>("blue");

  // Initialize from storage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as (ThemeMode | "system") | null;
      if (stored === "light" || stored === "dark") {
        setThemeState(stored);
        applyThemeClass(stored);
      } else if (stored === "system") {
        setThemeState("light");
        applyThemeClass("light");
      } else {
        applyThemeClass(defaultTheme);
      }
      const storedCwRaw = localStorage.getItem(STORAGE_COLORWAY_KEY);
      let storedCw: Colorway = "blue";
      if (storedCwRaw === "slate") storedCw = "slate";
      // migrate legacy values (default, neutral, zinc) to blue
      if (storedCwRaw === "blue") storedCw = "blue";
      setColorwayState(storedCw);
      applyColorwayClass(storedCw);
    } catch {
      applyThemeClass(defaultTheme);
      applyColorwayClass("blue");
    }
    return () => {};
  }, [defaultTheme]);

  const setTheme = useCallback((mode: ThemeMode) => {
    setThemeState(mode);
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {}
    applyThemeClass(mode);
  }, []);

  const setColorway = useCallback((cw: Colorway) => {
    setColorwayState(cw);
    try {
      localStorage.setItem(STORAGE_COLORWAY_KEY, cw);
    } catch {}
    applyColorwayClass(cw);
  }, []);

  const value = useMemo(() => ({ theme, setTheme, colorway, setColorway }), [theme, setTheme, colorway, setColorway]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
