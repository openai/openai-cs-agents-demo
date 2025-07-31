"use client";

import { PanelSection } from "./panel-section";
import { Card, CardContent } from "@/components/ui/card";
import { BookText } from "lucide-react";

interface ConversationContextProps {
  context: {
    passenger_name?: string;
    confirmation_number?: string;
    seat_number?: string;
    flight_number?: string;
    account_number?: string;
  };
}

export function ConversationContext({ context }: ConversationContextProps) {
  return (
    <PanelSection
      title="Conversation Context"
      icon={<BookText className="h-4 w-4 text-primary" />}
    >
      <Card className="bg-card border-border shadow-sm">
        <CardContent className="p-3">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(context).map(([key, value]) => (
              <div
                key={key}
                className="flex items-center gap-2 bg-background p-2 rounded-md border border-border shadow-sm transition-all"
              >
                <div className="w-2 h-2 rounded-full bg-primary"></div>
                <div className="text-xs">
                  <span className="text-muted-foreground font-light">{key}:</span>{" "}
                  <span
                    className={
                      value
                        ? "text-foreground font-light"
                        : "text-muted-foreground italic"
                    }
                  >
                    {value || "null"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </PanelSection>
  );
}