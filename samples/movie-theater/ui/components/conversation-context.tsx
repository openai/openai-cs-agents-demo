"use client";

import { PanelSection } from "./panel-section";
import { Card, CardContent } from "@/components/ui/card";
import { BookText } from "lucide-react";

interface ConversationContextProps {
  context: {
    customer_name?: string;
    confirmation_number?: string;
    seats?: string[];
    movie_title?: string;
    cinema_name?: string;
    city?: string;
    session_datetime?: string;
    room_number?: string;
    ticket_count?: number;
    ticket_type?: string;
    account_number?: string;
  };
}

export function ConversationContext({ context }: ConversationContextProps) {
  const formatContextValue = (key: string, value: any) => {
    if (value === null || value === undefined) return "null";
    if (Array.isArray(value)) return value.join(", ");
    return value.toString();
  };

  const getContextLabel = (key: string) => {
    const labels: Record<string, string> = {
      customer_name: "Customer Name",
      confirmation_number: "Confirmation #",
      seats: "Selected Seats",
      movie_title: "Movie",
      cinema_name: "Cinema",
      city: "City",
      session_datetime: "Session",
      room_number: "Room",
      ticket_count: "Tickets",
      ticket_type: "Ticket Type",
      account_number: "Account #",
    };
    return labels[key] || key.replace(/_/g, " ");
  };

  const contextEntries = Object.entries(context).filter(
    ([key, value]) => key !== "account_number" || value
  );

  return (
    <PanelSection
      title="Conversation Context"
      icon={<BookText className="h-4 w-4 text-black" />}
    >
      <Card className="bg-gradient-to-r from-white to-gray-50 border-gray-200 shadow-sm">
        <CardContent className="p-3">
          <div className="grid grid-cols-2 gap-2">
            {contextEntries.map(([key, value]) => (
              <div
                key={key}
                className="flex items-center gap-2 bg-white p-2 rounded-md border border-gray-200 shadow-sm transition-all hover:shadow-md"
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    value
                      ? "bg-gradient-to-r from-[#a1c4fd] to-[#c2e9fb]"
                      : "bg-gray-300"
                  }`}
                ></div>
                <div className="text-xs flex-1 min-w-0">
                  <span className="text-zinc-500 font-medium block">
                    {getContextLabel(key)}:
                  </span>
                  <span
                    className={`block truncate ${
                      value
                        ? "text-zinc-900 font-medium"
                        : "text-gray-400 italic"
                    }`}
                  >
                    {formatContextValue(key, value)}
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
