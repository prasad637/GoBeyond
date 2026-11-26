"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, MapPin, Search, X } from "lucide-react";
import { Modal } from "@/components/ui";
import { useLocation } from "@/context/LocationContext";
import {
  SEARCH_CATEGORIES,
  SEARCH_PRICE_RANGES,
  useDiscoverySearch,
} from "@/hooks/useDiscoverySearch";
import { SearchResultsList } from "@/components/discovery/SearchResultsList";
import { cn } from "@/lib/cn";

export function NavbarSearch() {
  const router = useRouter();
  const { selectedCity, selectedLocality } = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIdx, setHighlightedIdx] = useState(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    query,
    setQuery,
    selectedCategory,
    setSelectedCategory,
    results,
    totalCount,
    isLoading,
    error,
    hasActiveFilter,
    retry,
    resetFilters,
  } = useDiscoverySearch({
    pageSize: 8,
    debounceMs: 250,
    fetchWhenFilterActive: false,
  });

  useEffect(() => {
    setHighlightedIdx(-1);
  }, [results]);

  // Global Cmd/Ctrl+K shortcut for desktop focus
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setIsOpen(true);
      }
    };
    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  // Close popover on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const showPopover =
    isOpen &&
    (Boolean(query.trim()) || selectedCategory !== "ALL" || isLoading || Boolean(error));

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      setIsOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (!showPopover || results.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightedIdx((prev) => (prev + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightedIdx((prev) => (prev <= 0 ? results.length - 1 : prev - 1));
    } else if (e.key === "Enter") {
      const target = results[highlightedIdx >= 0 ? highlightedIdx : 0];
      if (target) {
        e.preventDefault();
        setIsOpen(false);
        router.push(target.action_url);
      }
    }
  };

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative flex items-center bg-surface-2 hover:bg-surface-2/90 border border-subtle hover:border-strong focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20 rounded-full transition-colors duration-150">
        <span className="pl-3.5 pr-2 text-secondary flex items-center shrink-0">
          {isLoading ? (
            <Loader2 className="w-4 h-4 text-brand-500 animate-spin" aria-hidden="true" />
          ) : (
            <Search className="w-4 h-4" aria-hidden="true" />
          )}
        </span>

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={
            selectedLocality
              ? `Search in ${selectedLocality.name}...`
              : "Search movies, dining, events, turfs..."
          }
          aria-label="Global search"
          aria-expanded={showPopover}
          aria-controls="navbar-search-popover"
          role="combobox"
          aria-autocomplete="list"
          className="w-full py-2 bg-transparent text-sm text-primary placeholder:text-muted focus:outline-none min-w-0"
        />

        {query ? (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              inputRef.current?.focus();
            }}
            aria-label="Clear search"
            className="p-1.5 mr-1.5 rounded-full text-secondary hover:text-primary hover:bg-surface-3 transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        ) : (
          <kbd className="hidden lg:inline-flex items-center px-2 py-0.5 mr-2.5 text-[11px] font-mono text-muted bg-surface border border-subtle rounded-md shrink-0">
            ⌘K
          </kbd>
        )}
      </div>

      {showPopover && (
        <div
          id="navbar-search-popover"
          className="absolute top-full left-0 right-0 mt-2 bg-surface border border-strong rounded-2xl shadow-modal overflow-hidden z-50 animate-fadeIn"
        >
          {/* Quick Category Pills inside Popover */}
          <div className="px-3.5 py-2.5 bg-surface-2/50 border-b border-subtle flex items-center gap-1.5 overflow-x-auto no-scrollbar">
            {SEARCH_CATEGORIES.map((cat) => (
              <button
                key={cat.key}
                type="button"
                onClick={() => setSelectedCategory(cat.key)}
                className={cn(
                  "px-2.5 py-1 rounded-full text-[11px] font-semibold whitespace-nowrap border transition-colors",
                  selectedCategory === cat.key
                    ? "bg-brand-500 border-brand-500 text-white"
                    : "bg-surface border-subtle text-secondary hover:text-primary hover:border-strong"
                )}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <SearchResultsList
            query={query}
            results={results}
            totalCount={totalCount}
            isLoading={isLoading}
            error={error}
            localityName={selectedLocality?.name ?? selectedCity}
            highlightedIndex={highlightedIdx}
            onSelect={() => setIsOpen(false)}
            onRetry={retry}
            onResetFilters={hasActiveFilter ? resetFilters : undefined}
            maxHeightClassName="max-h-[400px]"
          />
        </div>
      )}
    </div>
  );
}

export interface MobileSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MobileSearchModal({ isOpen, onClose }: MobileSearchModalProps) {
  const { selectedCity, selectedLocality } = useLocation();
  const inputRef = useRef<HTMLInputElement>(null);

  const {
    query,
    setQuery,
    selectedCategory,
    setSelectedCategory,
    selectedPriceIdx,
    setSelectedPriceIdx,
    results,
    totalCount,
    isLoading,
    error,
    hasActiveFilter,
    retry,
    resetFilters,
  } = useDiscoverySearch({
    pageSize: 10,
    debounceMs: 220,
    fetchWhenFilterActive: false,
  });

  useEffect(() => {
    if (!isOpen) return;
    const timer = setTimeout(() => inputRef.current?.focus(), 60);
    return () => clearTimeout(timer);
  }, [isOpen]);

  const showPromptSuggestions =
    !query.trim() && selectedCategory === "ALL" && selectedPriceIdx === 0 && !isLoading && !error;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="lg"
      title={
        <span className="flex items-center gap-2">
          <Search className="w-4 h-4 text-brand-500" />
          <span>Search Experiences</span>
        </span>
      }
      description={
        <span className="inline-flex items-center gap-1">
          <MapPin className="w-3 h-3 text-brand-400" />
          <span>
            {selectedLocality ? `${selectedLocality.name}, ${selectedCity}` : `All ${selectedCity}`}
          </span>
        </span>
      }
      bodyClassName="p-0"
    >
      <div className="p-4 sm:p-5 border-b border-subtle space-y-3 bg-surface-2/40">
        <div className="relative flex items-center bg-surface-2 border border-strong focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20 rounded-xl transition-colors">
          <span className="pl-3.5 pr-2 text-secondary">
            {isLoading ? (
              <Loader2 className="w-4 h-4 text-brand-500 animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
          </span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search movies, biryani, concerts, turfs..."
            aria-label="Mobile experience search"
            className="w-full py-3 bg-transparent text-base text-primary placeholder:text-muted focus:outline-none"
          />
          {query ? (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear search text"
              className="p-2 mr-1 text-secondary hover:text-primary"
            >
              <X className="w-4 h-4" />
            </button>
          ) : null}
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar pb-0.5">
          {SEARCH_CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              type="button"
              onClick={() => setSelectedCategory(cat.key)}
              className={cn(
                "px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap border transition-colors",
                selectedCategory === cat.key
                  ? "bg-brand-500 border-brand-500 text-white"
                  : "bg-surface border-subtle text-secondary hover:text-primary"
              )}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
          {SEARCH_PRICE_RANGES.map((pr, idx) => (
            <button
              key={pr.label}
              type="button"
              onClick={() => setSelectedPriceIdx(idx)}
              className={cn(
                "px-2.5 py-1 rounded-lg text-xs font-medium whitespace-nowrap border transition-colors",
                selectedPriceIdx === idx
                  ? "bg-brand-500/15 border-brand-500/50 text-brand-300 font-semibold"
                  : "bg-surface border-subtle text-secondary hover:text-primary"
              )}
            >
              {pr.label}
            </button>
          ))}
        </div>
      </div>

      {showPromptSuggestions ? (
        <div className="p-5 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">
            Quick Suggestions
          </p>
          <div className="flex flex-wrap gap-2">
            {["Pushpa", "Biryani", "Alan Walker", "Badminton", "AMB Cinemas"].map(
              (term) => (
                <button
                  key={term}
                  type="button"
                  onClick={() => setQuery(term)}
                  className="px-3 py-1.5 rounded-lg bg-surface-2 hover:bg-surface-3 border border-subtle text-xs font-medium text-secondary hover:text-primary transition-colors"
                >
                  {term}
                </button>
              )
            )}
          </div>
        </div>
      ) : (
        <SearchResultsList
          query={query}
          results={results}
          totalCount={totalCount}
          isLoading={isLoading}
          error={error}
          localityName={selectedLocality?.name ?? selectedCity}
          onSelect={onClose}
          onRetry={retry}
          onResetFilters={hasActiveFilter ? resetFilters : undefined}
          maxHeightClassName="max-h-[55vh]"
        />
      )}
    </Modal>
  );
}

