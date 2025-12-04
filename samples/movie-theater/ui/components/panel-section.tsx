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
    <div className="mb-5">
      <h2
        className="text-lg font-semibold mb-3 text-zinc-900 flex items-center justify-between cursor-pointer"
        onClick={() => setShow(!show)}
      >
        <div className="flex items-center">
          <span className="bg-gradient-to-r from-[#a1c4fd] to-[#c2e9fb] bg-opacity-10 p-1.5 rounded-md mr-2 shadow-sm">
            {icon}
          </span>
          <span>{title}</span>
        </div>
        {show ? (
          <ChevronDown className="h-4 w-4 text-zinc-900" />
        ) : (
          <ChevronRight className="h-4 w-4 text-zinc-900" />
        )}
      </h2>
      {show && (
        <div className="transition-all duration-300 ease-in-out">
          {children}
        </div>
      )}
    </div>
  );
}
