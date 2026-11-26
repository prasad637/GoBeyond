"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { SearchResponse, SearchResultItem } from "@/types/discovery";
import { useLocation } from "@/context/LocationContext";

export interface SearchPriceRange {
  label: string;
  min?: number;
  max?: number;
}

export const SEARCH_CATEGORIES = [
  { key: "ALL", label: "All Experiences" },
  { key: "MOVIES", label: "Movies" },
  { key: "DINING", label: "Dining" },
  { key: "EVENTS", label: "Events" },
  { key: "SPORTS", label: "Sports" },
  { key: "ACTIVITIES", label: "Activities" },
] as const;

export const SEARCH_PRICE_RANGES: SearchPriceRange[] = [
  { label: "Any Price" },
  { label: "Under ₹500", min: 0, max: 500 },
  { label: "₹500 - ₹1500", min: 500, max: 1500 },
  { label: "₹1500+", min: 1500 },
];

export type SearchSortBy = "relevance" | "rating" | "distance" | "price_asc";

export interface UseDiscoverySearchOptions {
  pageSize?: number;
  debounceMs?: number;
  fetchWhenFilterActive?: boolean;
  onResultsLoaded?: (total: number) => void;
}

export function useDiscoverySearch(options: UseDiscoverySearchOptions = {}) {
  const {
    pageSize = 6,
    debounceMs = 250,
    fetchWhenFilterActive = false,
    onResultsLoaded,
  } = options;

  const { selectedLocality, gpsCoordinates } = useLocation();

  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [selectedPriceIdx, setSelectedPriceIdx] = useState<number>(0);
  const [sortBy, setSortBy] = useState<SearchSortBy>("relevance");

  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const requestSeq = useRef(0);
  const onResultsLoadedRef = useRef(onResultsLoaded);
  onResultsLoadedRef.current = onResultsLoaded;

  const hasActiveFilter =
    Boolean(query.trim()) ||
    selectedCategory !== "ALL" ||
    selectedPriceIdx !== 0 ||
    fetchWhenFilterActive;

  const executeSearch = useCallback(async () => {
    const seq = ++requestSeq.current;
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (query.trim()) params.append("q", query.trim());
      if (selectedCategory !== "ALL") params.append("category", selectedCategory);
      if (selectedLocality?.id) {
        params.append("locality_id", selectedLocality.id.toString());
      }
      if (gpsCoordinates) {
        params.append("lat", gpsCoordinates.lat.toString());
        params.append("lon", gpsCoordinates.lon.toString());
      }

      const priceOpt = SEARCH_PRICE_RANGES[selectedPriceIdx];
      if (priceOpt?.min !== undefined) {
        params.append("min_price", priceOpt.min.toString());
      }
      if (priceOpt?.max !== undefined) {
        params.append("max_price", priceOpt.max.toString());
      }

      params.append("sort_by", sortBy);
      params.append("page", "1");
      params.append("page_size", pageSize.toString());

      const data = await apiRequest<SearchResponse>(
        `/discovery/search?${params.toString()}`
      );

      if (seq !== requestSeq.current) return;

      const items = data.results || [];
      const total = data.total_results || 0;
      setResults(items);
      setTotalCount(total);
      setHasSearched(true);
      onResultsLoadedRef.current?.(total);
    } catch (err: unknown) {
      if (seq !== requestSeq.current) return;
      const message =
        err instanceof Error && err.message
          ? err.message
          : "Unable to load search results right now.";
      setError(message);
      setHasSearched(true);
    } finally {
      if (seq === requestSeq.current) {
        setIsLoading(false);
      }
    }
  }, [
    query,
    selectedCategory,
    selectedPriceIdx,
    sortBy,
    selectedLocality,
    gpsCoordinates,
    pageSize,
  ]);

  useEffect(() => {
    if (!query.trim() && selectedCategory === "ALL" && selectedPriceIdx === 0 && !fetchWhenFilterActive) {
      requestSeq.current += 1;
      setResults([]);
      setTotalCount(0);
      setError(null);
      setIsLoading(false);
      setHasSearched(false);
      return;
    }

    const timer = setTimeout(() => {
      executeSearch();
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [
    query,
    selectedCategory,
    selectedPriceIdx,
    sortBy,
    fetchWhenFilterActive,
    debounceMs,
    executeSearch,
  ]);

  const resetFilters = useCallback(() => {
    setQuery("");
    setSelectedCategory("ALL");
    setSelectedPriceIdx(0);
    setSortBy("relevance");
    setError(null);
  }, []);

  return {
    query,
    setQuery,
    selectedCategory,
    setSelectedCategory,
    selectedPriceIdx,
    setSelectedPriceIdx,
    sortBy,
    setSortBy,
    results,
    totalCount,
    isLoading,
    error,
    hasSearched,
    hasActiveFilter,
    retry: executeSearch,
    resetFilters,
  };
}

