"use client";

import React, { useState } from "react";
import { Search, SlidersHorizontal, X, ArrowUpDown, RotateCcw } from "lucide-react";
import { cn } from "@/lib/cn";
import { FilterDrawer } from "@/components/discovery/FilterDrawer";

export interface FilterChipOption {
  label: string;
  value: string;
}

export interface SortOption {
  label: string;
  value: string;
}

export interface SecondaryFilterGroup {
  id: string;
  label: string;
  options: FilterChipOption[];
  selectedValue: string;
  onSelect: (value: string) => void;
}

export interface ListingFilterToolbarProps {
  searchQuery: string;
  onSearchChange: (val: string) => void;
  searchPlaceholder: string;
  primaryChips?: FilterChipOption[];
  selectedPrimaryValue?: string;
  onPrimarySelect?: (value: string) => void;
  primaryLabel?: string;
  extraInlineSlot?: React.ReactNode;
  secondaryGroups?: SecondaryFilterGroup[];
  sortOptions?: SortOption[];
  selectedSort?: string;
  onSortChange?: (value: string) => void;
  activeFilterCount?: number;
  onClearAll?: () => void;
  drawerTitle?: string;
}

export function ListingFilterToolbar({
  searchQuery,
  onSearchChange,
  searchPlaceholder,
  primaryChips,
  selectedPrimaryValue = "",
  onPrimarySelect,
  primaryLabel = "Category",
  extraInlineSlot,
  secondaryGroups = [],
  sortOptions = [],
  selectedSort = "",
  onSortChange,
  activeFilterCount = 0,
  onClearAll,
  drawerTitle = "Filter & Sort",
}: ListingFilterToolbarProps) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const hasSecondaryOrSort = secondaryGroups.length > 0 || sortOptions.length > 0;

  return (
    <div className="space-y-3 mb-7">
      {/* Main Toolbar Row */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-3 sm:p-3.5 rounded-2xl bg-surface border border-subtle shadow-surface">
        {/* Desktop & Tablet Primary Filter Pills (kept accessible & visible >=md for direct clicks) */}
        {(primaryChips && primaryChips.length > 0) || extraInlineSlot ? (
          <div className="hidden md:flex flex-wrap items-center gap-2 min-w-0">
            {primaryChips && primaryChips.length > 0 ? (
              <div
                role="group"
                aria-label={primaryLabel}
                className="flex flex-wrap items-center gap-1 p-1 rounded-xl bg-canvas/80 border border-subtle"
              >
                {primaryChips.map((chip) => {
                  const isActive = selectedPrimaryValue === chip.value;
                  return (
                    <button
                      key={chip.label}
                      type="button"
                      aria-pressed={isActive}
                      onClick={() => onPrimarySelect?.(chip.value)}
                      className={cn(
                        "px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors whitespace-nowrap",
                        isActive
                          ? "bg-brand-500 text-white shadow-brand-sm"
                          : "text-secondary hover:text-primary hover:bg-surface-2"
                      )}
                    >
                      {chip.label}
                    </button>
                  );
                })}
              </div>
            ) : null}

            {extraInlineSlot}
          </div>
        ) : (
          <div className="hidden md:block text-xs text-muted font-medium px-1">
            Explore curated listings across the city
          </div>
        )}

        {/* Right Controls: Search + Sort + Mobile Drawer Trigger */}
        <div className="flex items-center gap-2 w-full lg:w-auto lg:ml-auto">
          <div className="relative flex-1 lg:w-64 xl:w-72">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted"
              aria-hidden="true"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={searchPlaceholder}
              aria-label={searchPlaceholder}
              className="w-full h-10 md:h-9 pl-9 pr-8 rounded-xl bg-surface-2 border border-subtle text-base md:text-xs text-primary placeholder:text-muted focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-colors"
            />
            {searchQuery ? (
              <button
                type="button"
                onClick={() => onSearchChange("")}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md text-muted hover:text-primary hover:bg-surface-3 transition-colors"
              >
                <X className="w-3.5 h-3.5" aria-hidden="true" />
              </button>
            ) : null}
          </div>

          {/* Desktop Sort Dropdown */}
          {sortOptions.length > 0 && onSortChange ? (
            <div className="hidden md:flex items-center relative shrink-0">
              <ArrowUpDown
                className="pointer-events-none absolute left-2.5 w-3.5 h-3.5 text-muted"
                aria-hidden="true"
              />
              <select
                aria-label="Sort results"
                value={selectedSort}
                onChange={(e) => onSortChange(e.target.value)}
                className="h-9 pl-8 pr-7 rounded-xl bg-surface-2 border border-subtle text-xs font-medium text-primary focus:outline-none focus:border-brand-500 appearance-none cursor-pointer"
              >
                {sortOptions.map((opt) => (
                  <option key={opt.value} value={opt.value} className="bg-surface text-primary">
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          {/* Mobile Filters Drawer Button */}
          {(primaryChips?.length || extraInlineSlot || hasSecondaryOrSort) && (
            <button
              type="button"
              onClick={() => setIsDrawerOpen(true)}
              aria-expanded={isDrawerOpen}
              className={cn(
                "md:hidden inline-flex items-center gap-1.5 h-10 px-3.5 rounded-xl border text-xs font-semibold shrink-0 transition-colors",
                activeFilterCount > 0
                  ? "bg-brand-500/15 border-brand-500/40 text-brand-400"
                  : "bg-surface-2 border-subtle text-secondary hover:text-primary"
              )}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Filters</span>
              {activeFilterCount > 0 ? (
                <span className="px-1.5 py-0.2 rounded-full bg-brand-500 text-white text-[10px] font-bold tabular-nums-lining">
                  {activeFilterCount}
                </span>
              ) : null}
            </button>
          )}
        </div>
      </div>

      {/* Desktop Secondary Filters Row (Genres, Price tiers, Cuisines, etc.) */}
      {secondaryGroups.length > 0 ? (
        <div className="hidden md:flex flex-wrap items-center gap-x-5 gap-y-2 px-1">
          {secondaryGroups.map((group) => (
            <div key={group.id} className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted mr-1">
                {group.label}:
              </span>
              {group.options.map((opt) => {
                const isSelected = group.selectedValue === opt.value;
                return (
                  <button
                    key={opt.value || opt.label}
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => group.onSelect(opt.value)}
                    className={cn(
                      "px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors",
                      isSelected
                        ? "bg-brand-500/15 border-brand-500/45 text-brand-300 font-semibold"
                        : "bg-surface border-subtle text-secondary hover:text-primary hover:bg-surface-2"
                    )}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          ))}

          {activeFilterCount > 0 && onClearAll ? (
            <button
              type="button"
              onClick={onClearAll}
              className="inline-flex items-center gap-1 text-xs font-semibold text-brand-400 hover:text-brand-300 transition-colors ml-auto"
            >
              <RotateCcw className="w-3 h-3" aria-hidden="true" />
              <span>Clear Filters</span>
            </button>
          ) : null}
        </div>
      ) : activeFilterCount > 0 && onClearAll ? (
        <div className="hidden md:flex justify-end px-1">
          <button
            type="button"
            onClick={onClearAll}
            className="inline-flex items-center gap-1 text-xs font-semibold text-brand-400 hover:text-brand-300 transition-colors"
          >
            <RotateCcw className="w-3 h-3" aria-hidden="true" />
            <span>Clear Filters</span>
          </button>
        </div>
      ) : null}

      {/* Mobile Filter Drawer */}
      <FilterDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        title={drawerTitle}
        activeFilterCount={activeFilterCount}
        onReset={onClearAll}
      >
        {primaryChips && primaryChips.length > 0 ? (
          <div>
            <span className="block font-mono text-[11px] uppercase tracking-wider text-secondary mb-2">
              {primaryLabel}
            </span>
            <div className="flex flex-wrap gap-2">
              {primaryChips.map((chip) => {
                const isActive = selectedPrimaryValue === chip.value;
                return (
                  <button
                    key={chip.label}
                    type="button"
                    onClick={() => onPrimarySelect?.(chip.value)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors",
                      isActive
                        ? "bg-brand-500 border-brand-500 text-white"
                        : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                    )}
                  >
                    {chip.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        {extraInlineSlot ? (
          <div className="flex flex-wrap gap-2">{extraInlineSlot}</div>
        ) : null}

        {secondaryGroups.map((group) => (
          <div key={group.id}>
            <span className="block font-mono text-[11px] uppercase tracking-wider text-secondary mb-2">
              {group.label}
            </span>
            <div className="flex flex-wrap gap-2">
              {group.options.map((opt) => {
                const isSelected = group.selectedValue === opt.value;
                return (
                  <button
                    key={opt.value || opt.label}
                    type="button"
                    onClick={() => group.onSelect(opt.value)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                      isSelected
                        ? "bg-brand-500/15 border-brand-500/45 text-brand-300 font-semibold"
                        : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                    )}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        {sortOptions.length > 0 && onSortChange ? (
          <div>
            <span className="block font-mono text-[11px] uppercase tracking-wider text-secondary mb-2">
              Sort By
            </span>
            <div className="flex flex-wrap gap-2">
              {sortOptions.map((opt) => {
                const isSelected = selectedSort === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => onSortChange(opt.value)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                      isSelected
                        ? "bg-surface-3 border-strong text-primary font-semibold"
                        : "bg-surface-2 border-subtle text-secondary hover:text-primary"
                    )}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </FilterDrawer>
    </div>
  );
}

