"use client";

import React from "react";
import { Card, CardContent } from "@/components/ui/card";

interface SeatMapProps {
  onSeatSelect: (seatNumber: string) => void;
  selectedSeats: string[];
  hideHeader?: boolean;
}

// Define cinema seat layout
const CINEMA_LAYOUT = {
  rows: ["A", "B", "C", "D", "E", "F", "G", "H"],
  seatsPerRow: 10,
  vipRows: ["C", "D"],
  accessibleSeats: ["A1", "A2", "A9", "A10", "H1", "H2", "H9", "H10"],
};

// Predefine occupied seats
const OCCUPIED_SEATS = new Set([
  "A3",
  "A4",
  "A7",
  "A8",
  "B2",
  "B5",
  "B8",
  "B9",
  "C1",
  "C4",
  "C7",
  "C10",
  "D3",
  "D8",
  "E5",
  "E6",
  "F2",
  "F9",
  "G4",
  "G7",
  "H3",
  "H8",
]);

export function SeatMap({
  onSeatSelect,
  selectedSeats,
  hideHeader = false,
}: SeatMapProps) {
  const getSeatStatus = (seatNumber: string) => {
    if (OCCUPIED_SEATS.has(seatNumber)) return "occupied";
    if (selectedSeats.includes(seatNumber)) return "selected";
    if (CINEMA_LAYOUT.accessibleSeats.includes(seatNumber)) return "accessible";
    if (CINEMA_LAYOUT.vipRows.includes(seatNumber.charAt(0))) return "vip";
    return "available";
  };

  const getSeatColor = (status: string) => {
    switch (status) {
      case "occupied":
        return "bg-gray-300 text-gray-500 cursor-not-allowed";
      case "selected":
        return "bg-gradient-to-r from-[#a1c4fd] to-[#c2e9fb] text-black cursor-pointer";
      case "vip":
        return "bg-yellow-400 hover:bg-yellow-500 cursor-pointer border-yellow-500";
      case "accessible":
        return "bg-blue-400 hover:bg-blue-500 cursor-pointer border-blue-500";
      case "available":
      default:
        return "bg-purple-100 hover:bg-purple-200 cursor-pointer border-purple-300";
    }
  };

  const getSeatSymbol = (status: string) => {
    if (status === "accessible") return "♿";
    if (status === "vip") return "⭐";
    return "";
  };

  return (
    <Card className="w-full max-w-2xl mx-auto my-4 bg-purple-50">
      <CardContent className="p-4">
        {/* Cabeçalho: escondido se hideHeader for true */}
        {!hideHeader && (
          <div className="text-center mb-4">
            <h3 className="font-semibold text-lg mb-2 text-black">
              Select Your Seats
            </h3>
            <div className="flex justify-center gap-4 text-xs">
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-purple-100 border border-purple-300 rounded"></div>
                <span>Available</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-gray-300 rounded"></div>
                <span>Occupied</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-yellow-400 border border-yellow-500 rounded"></div>
                <span>VIP</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 bg-blue-400 border border-blue-500 rounded"></div>
                <span>Accessible</span>
              </div>
            </div>
          </div>
        )}

        {/* Screen */}
        <div className="mb-6 bg-gray-800 text-white py-2 text-center rounded-md shadow-lg">
          🎬 Screen
        </div>

        {/* Seating Area */}
        <div className="space-y-2">
          {CINEMA_LAYOUT.rows.map((row) => (
            <div key={row} className="flex justify-center items-center gap-1">
              <span className="w-6 text-xs text-gray-700 font-medium mr-2">
                {row}
              </span>
              {Array.from({ length: CINEMA_LAYOUT.seatsPerRow }, (_, i) => {
                const seatNumber = `${row}${i + 1}`;
                const status = getSeatStatus(seatNumber);
                const isAisle = i === 4 || i === 5;

                return (
                  <React.Fragment key={seatNumber}>
                    <button
                      className={`w-8 h-8 text-xs font-medium border rounded flex items-center justify-center ${getSeatColor(
                        status
                      )} transition-colors`}
                      onClick={() =>
                        status !== "occupied" && onSeatSelect(seatNumber)
                      }
                      disabled={status === "occupied"}
                      title={`Seat ${seatNumber}${
                        status === "vip"
                          ? " (VIP)"
                          : status === "accessible"
                          ? " (Accessible)"
                          : ""
                      }`}
                    >
                      {getSeatSymbol(status) || i + 1}
                    </button>
                    {isAisle && <div className="w-6" />}
                  </React.Fragment>
                );
              })}
            </div>
          ))}
        </div>

        {selectedSeats.length > 0 && (
          <div className="mt-4 p-3 bg-gradient-to-r from-[#a1c4fd] to-[#c2e9fb] rounded-lg text-center">
            <p className="text-sm font-medium text-black">
              Selected: {selectedSeats.join(", ")}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
