"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import type { Message } from "@/lib/types";
import ReactMarkdown from "react-markdown";
import { SeatMap } from "./seat-map";

interface ChatProps {
  messages: Message[];
  onSendMessage: (message: string) => void;
  isLoading?: boolean;
}

export function Chat({ messages, onSendMessage, isLoading }: ChatProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [inputText, setInputText] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const [showSeatMap, setShowSeatMap] = useState(false);
  const [selectedSeats, setSelectedSeats] = useState<string[]>([]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    const triggerIndex = messages
      .map((m) => m.content)
      .lastIndexOf("DISPLAY_SEAT_MAP");

    if (triggerIndex === -1) {
      if (showSeatMap) setShowSeatMap(false);
      return;
    }

    const lastUserMessageIndex = messages
      .map((m) => m.role)
      .lastIndexOf("user");

    const shouldShowMap = lastUserMessageIndex < triggerIndex;

    if (shouldShowMap !== showSeatMap) {
      setShowSeatMap(shouldShowMap);
      if (shouldShowMap) {
        setSelectedSeats([]);
      }
    }
  }, [messages, showSeatMap]);

  const handleSend = useCallback(() => {
    if (!inputText.trim()) return;
    onSendMessage(inputText);
    setInputText("");
  }, [inputText, onSendMessage]);

  const handleSeatSelect = useCallback((seat: string) => {
    setSelectedSeats((prev) => {
      if (prev.includes(seat)) {
        return prev.filter((s) => s !== seat);
      } else {
        return [...prev, seat];
      }
    });
  }, []);

  const handleConfirmSeats = useCallback(() => {
    if (selectedSeats.length === 0) return;
    setShowSeatMap(false);
    onSendMessage(`${selectedSeats.join(" and ")}`);
    setSelectedSeats([]);
  }, [selectedSeats, onSendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey && !isComposing) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend, isComposing]
  );

  return (
    <div className="flex flex-col h-full flex-1 bg-white shadow-sm border border-gray-200 border-t-0 rounded-xl">
      <div className="bg-gradient-to-r from-[#a1c4fd] to-[#c2e9fb] text-black h-12 px-4 flex items-center rounded-t-xl">
        <h2 className="text-sm sm:text-base lg:text-lg">
          <span className="font-semibold">CUSTOMER</span>
          <span className="font-light">VIEW</span>
        </h2>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto min-h-0 md:px-4 pt-4 pb-20">
        {messages.map((msg, idx) => {
          if (
            msg.content === "DISPLAY_SEAT_MAP" ||
            msg.content === "TICKET_PURCHASE_CONFIRMED"
          )
            return null;

          return (
            <div
              key={idx}
              className={`flex mb-5 text-sm ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {msg.role === "user" ? (
                <div className="ml-4 rounded-[16px] rounded-br-[4px] px-4 py-2 md:ml-24 bg-black text-white font-light max-w-[80%]">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <div className="mr-4 rounded-[16px] rounded-bl-[4px] px-4 py-2 md:mr-24 text-zinc-900 bg-[#ECECF1] font-light max-w-[80%]">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              )}
            </div>
          );
        })}

        {/* Seat Map Display */}
        {showSeatMap && (
          <div className="flex justify-start mb-5">
            <div className="mr-4 rounded-[16px] rounded-bl-[4px] md:mr-24 max-w-[80%]">
              <SeatMap
                onSeatSelect={handleSeatSelect}
                selectedSeats={selectedSeats}
              />
              {selectedSeats.length > 0 && (
                <div className="mt-4 flex flex-col items-center bg-white p-4 rounded-lg border border-gray-200">
                  <div className="text-sm font-medium mb-3 text-center">
                    Selected Seats:{" "}
                    <span className="text-black font-bold">
                      {selectedSeats.join(", ")}
                    </span>
                  </div>
                  <button
                    onClick={handleConfirmSeats}
                    className="bg-gradient-to-r from-[#a1c4fd] to-[#c2e9fb] text-black px-6 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm"
                  >
                    Confirm Selection
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex mb-5 text-sm justify-start">
            <div className="mr-4 rounded-[16px] rounded-bl-[4px] px-4 py-2 md:mr-24 text-zinc-900 bg-[#ECECF1] font-light">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 bg-gray-400 rounded-full animate-pulse"></div>
                <div
                  className="h-2 w-2 bg-gray-400 rounded-full animate-pulse"
                  style={{ animationDelay: "0.2s" }}
                ></div>
                <div
                  className="h-2 w-2 bg-gray-400 rounded-full animate-pulse"
                  style={{ animationDelay: "0.4s" }}
                ></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-2 md:px-4">
        <div className="flex items-center">
          <div className="flex w-full items-center pb-4 md:pb-1">
            <div className="flex w-full flex-col gap-1.5 rounded-2xl p-2.5 pl-1.5 bg-white border border-stone-200 shadow-sm transition-colors">
              <div className="flex items-end gap-1.5 md:gap-2 pl-4">
                <div className="flex min-w-0 flex-1 flex-col">
                  <textarea
                    id="prompt-textarea"
                    tabIndex={0}
                    dir="auto"
                    rows={2}
                    placeholder="Type your message..."
                    className="mb-2 resize-none border-0 focus:outline-none text-sm bg-transparent px-0 pb-6 pt-2"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={handleKeyDown}
                    onCompositionStart={() => setIsComposing(true)}
                    onCompositionEnd={() => setIsComposing(false)}
                  />
                </div>
                <button
                  disabled={!inputText.trim()}
                  className="flex h-8 w-8 items-end justify-center rounded-full bg-black text-white hover:opacity-70 disabled:bg-gray-300 disabled:text-gray-400 transition-colors focus:outline-none"
                  onClick={handleSend}
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="32"
                    height="32"
                    fill="none"
                    viewBox="0 0 32 32"
                    className="icon-2xl"
                  >
                    <path
                      fill="currentColor"
                      fillRule="evenodd"
                      d="M15.192 8.906a1.143 1.143 0 0 1 1.616 0l5.143 5.143a1.143 1.143 0 0 1-1.616 1.616l-3.192-3.192v9.813a1.143 1.143 0 0 1-2.286 0v-9.813l-3.192 3.192a1.143 1.143 0 1 1-1.616-1.616z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
