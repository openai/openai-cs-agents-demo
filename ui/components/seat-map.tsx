"use client";

import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface SeatMapProps {
    onSeatSelect: (seatNumber: string) => void;
    selectedSeat?: string;
}

// Define seat layout for a typical narrow-body aircraft
const SEAT_LAYOUT = {
    business: { rows: [1, 2, 3, 4], seatsPerRow: ['A', 'B', 'C', 'D'] },
    economyPlus: { rows: [5, 6, 7, 8], seatsPerRow: ['A', 'B', 'C', 'D', 'E', 'F'] },
    economy: {
        rows: Array.from({ length: 16 }, (_, i) => i + 9), // rows 9-24
        seatsPerRow: ['A', 'B', 'C', 'D', 'E', 'F']
    }
};

const OCCUPIED_SEATS = new Set([
    '1A', '2B', '3C', '5A', '5F', '7B', '7E', '9A', '9F', '10C', '10D',
    '12A', '12F', '14B', '14E', '16A', '16F', '18C', '18D', '20A', '20F',
    '22B', '22E', '24A', '24F'
]);

const EXIT_ROWS = new Set([4, 16]);

export function SeatMap({ onSeatSelect, selectedSeat }: SeatMapProps) {
    const getSeatStatus = (seatNumber: string) => {
        if (OCCUPIED_SEATS.has(seatNumber)) return 'occupied';
        if (selectedSeat === seatNumber) return 'selected';
        return 'available';
    };

    const getSeatClasses = (status: string, isExit: boolean) => {
        switch (status) {
            case 'occupied':
                return 'cursor-not-allowed opacity-60 bg-muted text-muted-foreground border-border';
            case 'selected':
                return 'bg-primary text-primary-foreground hover:bg-primary/90';
            case 'available':
                return isExit
                    ? 'bg-accent hover:bg-accent/80 border-ring'
                    : 'bg-accent hover:bg-accent/80 border-border';
            default:
                return 'bg-accent';
        }
    };

    const renderSeatSection = (title: string, config: typeof SEAT_LAYOUT.business, className: string) => (
        <div className={`mb-6 ${className}`}>
            <h4 className="text-sm font-semibold mb-2 text-center">{title}</h4>
            <div className="space-y-1">
                {config.rows.map(row => {
                    const isExitRow = EXIT_ROWS.has(row);
                    return (
                        <div key={row} className="flex items-center justify-center gap-1">
                            <span className="w-6 text-xs text-gray-500 text-right mr-2">{row}</span>
                            <div className="flex gap-1">
                                {config.seatsPerRow.slice(0, Math.ceil(config.seatsPerRow.length / 2)).map(letter => {
                                    const seatNumber = `${row}${letter}`;
                                    const status = getSeatStatus(seatNumber);
                                    return (
                                        <Button
                                            variant="outline"
                                            key={seatNumber}
                                            className={`w-8 h-8 text-xs font-medium rounded ${getSeatClasses(status, isExitRow)} transition-colors`}
                                            onClick={() => status === 'available' && onSeatSelect(seatNumber)}
                                            disabled={status === 'occupied'}
                                            title={`Seat ${seatNumber}${isExitRow ? ' (Exit Row)' : ''}${status === 'occupied' ? ' - Occupied' : ''}`}
                                        >
                                            {letter}
                                        </Button>
                                    );
                                })}
                            </div>
                            <div className="w-4" /> {/* Aisle */}
                            <div className="flex gap-1">
                                {config.seatsPerRow.slice(Math.ceil(config.seatsPerRow.length / 2)).map(letter => {
                                    const seatNumber = `${row}${letter}`;
                                    const status = getSeatStatus(seatNumber);
                                    return (
                                        <Button
                                            variant="outline"
                                            key={seatNumber}
                                            className={`w-8 h-8 text-xs font-medium rounded ${getSeatClasses(status, isExitRow)} transition-colors`}
                                            onClick={() => status === 'available' && onSeatSelect(seatNumber)}
                                            disabled={status === 'occupied'}
                                            title={`Seat ${seatNumber}${isExitRow ? ' (Exit Row)' : ''}${status === 'occupied' ? ' - Occupied' : ''}`}
                                        >
                                            {letter}
                                        </Button>
                                    );
                                })}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );

    return (
        <Card className="w-full max-w-md mx-auto my-4 bg-card">
            <CardContent className="p-4">
                <div className="text-center mb-4">
                    <h3 className="font-semibold text-lg mb-2">Select Your Seat</h3>
                    <div className="flex justify-center gap-4 text-xs">
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 bg-accent border border-border rounded"></div>
                            <span>Available</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 bg-muted rounded"></div>
                            <span>Occupied</span>
                        </div>
                        <div className="flex items-center gap-1">
                            <div className="w-3 h-3 bg-accent border border-ring rounded"></div>
                            <span>Exit Row</span>
                        </div>
                    </div>
                </div>

                <div className="space-y-4">
                    {renderSeatSection("Business Class", SEAT_LAYOUT.business, "border-b pb-4")}
                    {renderSeatSection("Economy Plus", SEAT_LAYOUT.economyPlus, "border-b pb-4")}
                    {renderSeatSection("Economy", SEAT_LAYOUT.economy, "")}
                </div>

                {selectedSeat && (
                    <div className="mt-4 p-3 bg-muted rounded-lg text-center">
                        <p className="text-sm font-medium text-foreground">
                            Selected: Seat {selectedSeat}
                        </p>
                    </div>
                )}
            </CardContent>
        </Card>
    );
} 