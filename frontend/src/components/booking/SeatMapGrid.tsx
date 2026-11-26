"use client";

import React from "react";
import { Accessibility, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/cn";
import { Skeleton } from "@/components/ui/Skeleton";

export interface ShowSeatItem {
  id: number;
  screen_id: number;
  row_code: string;
  seat_number: number;
  tier: string;
  base_price: number;
  is_accessible: boolean;
  is_locked: boolean;
  is_booked: boolean;
}

export interface SeatMapGridProps {
  seats: ShowSeatItem[];
  loading?: boolean;
  selectedSeatIds: number[];
  onToggleSeat: (seat: ShowSeatItem) => void;
  maxSeats?: number;
  limitWarning?: string | null;
}

function formatTierHeading(tier?: string | null): string {
  if (!tier) return "Standard";
  return tier
    .toLowerCase()
    .split(/[_\s]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function SeatMapGrid({
  seats,
  loading = false,
  selectedSeatIds,
  onToggleSeat,
  maxSeats = 6,
  limitWarning,
}: SeatMapGridProps) {
  // Derive rows dynamically from backend seat data (supports any screen layout A..Z)
  const groupedByRow = React.useMemo(() => {
    const map = new Map<string, ShowSeatItem[]>();
    const sorted = [...seats].sort((a, b) => {
      if (a.row_code !== b.row_code) return a.row_code.localeCompare(b.row_code);
      return a.seat_number - b.seat_number;
    });
    for (const seat of sorted) {
      const list = map.get(seat.row_code) ?? [];
      list.push(seat);
      map.set(seat.row_code, list);
    }
    return Array.from(map.entries());
  }, [seats]);

  if (loading) {
    return (
      <div aria-busy="true" className="py-6 space-y-4">
        <Skeleton className="h-3 w-2/3 mx-auto rounded-full" />
        <div className="space-y-2.5 max-w-md mx-auto">
          {Array.from({ length: 4 }).map((_, idx) => (
            <Skeleton key={idx} className="h-8 w-full rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Inline Max Seat Warning */}
      {limitWarning ? (
        <div
          role="status"
          className="p-2.5 rounded-xl bg-amber-500/12 border border-amber-500/30 text-amber-300 text-xs flex items-center gap-2"
        >
          <AlertTriangle className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>{limitWarning}</span>
        </div>
      ) : null}

      {/* Cinema Screen Curve */}
      <div className="py-1 text-center space-y-2">
        <div
          aria-hidden="true"
          className="w-3/4 mx-auto h-2 bg-gradient-to-r from-transparent via-brand-500 to-transparent rounded-full shadow-[0_4px_20px_rgba(244,63,94,0.45)]"
        />
        <div className="font-mono text-[10px] text-muted uppercase tracking-[0.18em]">
          All eyes this way — Audi Screen (Max {maxSeats} seats)
        </div>
      </div>

      {/* Horizontal-Scroll Seat Rows */}
      <div className="py-2 overflow-x-auto">
        {groupedByRow.length === 0 ? (
          <p className="text-center text-xs text-muted py-6">
            No seat layout available for this show.
          </p>
        ) : (
          <div className="w-max min-w-full space-y-3 mx-auto px-0.5 sm:px-1">
            {groupedByRow.map(([rowCode, rowSeats], rowIdx) => {
              const firstSeat = rowSeats[0];
              const prevFirstSeat = rowIdx > 0 ? groupedByRow[rowIdx - 1][1][0] : null;
              const showTierHeader =
                !prevFirstSeat ||
                prevFirstSeat.tier !== firstSeat.tier ||
                prevFirstSeat.base_price !== firstSeat.base_price;

              return (
                <div key={rowCode} className="space-y-1.5">
                  {showTierHeader ? (
                    <div className="flex items-center justify-between text-[11px] font-medium text-champagne px-1 pt-1">
                      <span>{formatTierHeading(firstSeat.tier)}</span>
                      <span className="font-mono tabular-nums-lining">
                        ₹{firstSeat.base_price.toFixed(0)}
                      </span>
                    </div>
                  ) : null}

                  <div className="flex items-center justify-center gap-1 sm:gap-1.5">
                    <span className="w-4 sm:w-5 text-[10px] sm:text-xs font-mono font-bold text-muted text-center shrink-0">
                      {rowCode}
                    </span>

                    <div className="flex items-center justify-center gap-[3px] sm:gap-1.5 flex-nowrap">
                      {rowSeats.map((seat) => {
                        const isSelected = selectedSeatIds.includes(seat.id);
                        const isUnavailable = seat.is_booked || seat.is_locked;

                        return (
                          <button
                            key={seat.id}
                            type="button"
                            disabled={isUnavailable}
                            aria-pressed={isSelected}
                            onClick={() => onToggleSeat(seat)}
                            title={`Seat ${seat.row_code}${seat.seat_number} - ₹${seat.base_price}`}
                            className={cn(
                              "relative w-6 h-7 sm:w-8 sm:h-8 rounded-md sm:rounded-lg text-[10px] sm:text-[11px] font-mono font-bold border transition-all flex items-center justify-center shrink-0",
                              seat.is_booked
                                ? "bg-canvas border-subtle/60 text-muted/40 cursor-not-allowed"
                                : seat.is_locked
                                ? "bg-amber-500/15 border-amber-500/35 text-amber-400 cursor-not-allowed"
                                : isSelected
                                ? "bg-brand-500 border-brand-400 text-white shadow-brand-sm scale-105"
                                : "bg-surface-2 border-subtle text-secondary hover:bg-surface-3 hover:text-primary hover:border-strong"
                            )}
                          >
                            {seat.is_accessible ? (
                              <Accessibility className="w-3.5 h-3.5" aria-hidden="true" />
                            ) : (
                              <span>{seat.seat_number}</span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Seat Status Legend */}
      <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[11px] text-secondary pt-3 border-t border-subtle">
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-surface-2 border border-subtle" />
          <span>Available</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-brand-500 border border-brand-400" />
          <span>Selected</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-amber-500/20 border border-amber-500/40" />
          <span>Held by Other</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3.5 h-3.5 rounded bg-canvas border border-subtle/60" />
          <span>Booked</span>
        </div>
      </div>
    </div>
  );
}

