"use client";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

interface PanelSectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

export function PanelSection({ title, icon, children }: PanelSectionProps) {
  return (
    <div className="mb-5">
      <Accordion type="single" collapsible defaultValue="item">
        <AccordionItem value="item" className="border-none">
          <AccordionTrigger className="px-2 rounded-md bg-primary/10 text-foreground">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-md bg-primary/20 text-primary-foreground/90">
                {icon}
              </span>
              <span className="text-base font-semibold">{title}</span>
            </div>
          </AccordionTrigger>
          <AccordionContent className="pt-2">
            {children}
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
