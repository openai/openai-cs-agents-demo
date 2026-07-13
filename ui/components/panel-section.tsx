"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface PanelSectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

export function PanelSection({ title, icon, children }: PanelSectionProps) {
  const [show, setShow] = useState(true);

  return (
    <section className="mb-6 min-w-0">
      <button
        type="button"
        className="mb-3 flex w-full items-center justify-between text-left text-sm font-semibold text-zinc-900"
        onClick={() => setShow(!show)}
        aria-expanded={show}
      >
        <div className="flex items-center">
          <span className="mr-2 flex h-7 w-7 items-center justify-center bg-teal-50 text-teal-700">
            {icon}
          </span>
          <span>{title}</span>
        </div>
        {show ? (
          <ChevronDown className="h-4 w-4 text-zinc-900" />
        ) : (
          <ChevronRight className="h-4 w-4 text-zinc-900" />
        )}
      </button>
      {show && children}
    </section>
  );
}
