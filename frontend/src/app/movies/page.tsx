"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Film } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { MovieFeedItem } from "@/types/discovery";
import { useLocation } from "@/context/LocationContext";
import { ListingPageHeader } from "@/components/discovery/ListingPageHeader";
import { ListingFilterToolbar } from "@/components/discovery/ListingFilterToolbar";
import { DiscoveryGrid } from "@/components/discovery/DiscoveryGrid";
import { MovieCard } from "@/components/discovery/MovieCard";

const LANGUAGE_CHIPS = [
  { label: "All", value: "" },
  { label: "Telugu", value: "Telugu" },
  { label: "English", value: "English" },
  { label: "Hindi", value: "Hindi" },
  { label: "Tamil", value: "Tamil" },
];

const GENRE_CHIPS = [
  { label: "All Genres", value: "" },
  { label: "Action", value: "Action" },
  { label: "Sci-Fi", value: "Sci-Fi" },
  { label: "Thriller", value: "Thriller" },
  { label: "Drama", value: "Drama" },
];

const SORT_OPTIONS = [
  { label: "Latest Releases", value: "release_desc" },
  { label: "Highest Rated", value: "rating_desc" },
  { label: "Most Popular", value: "votes_desc" },
  { label: "Runtime: Shortest", value: "duration_asc" },
];

export default function MoviesPage() {
  const { selectedCity } = useLocation();

  const [movies, setMovies] = useState<MovieFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedLang, setSelectedLang] = useState("");
  const [selectedGenre, setSelectedGenre] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("release_desc");

  const requestSeq = useRef(0);

  const fetchMovies = useCallback(async () => {
    const seq = ++requestSeq.current;
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (selectedLang) params.append("language", selectedLang);

      const qs = params.toString();
      const data = await apiRequest<MovieFeedItem[]>(`/movies/${qs ? `?${qs}` : ""}`);
      if (seq !== requestSeq.current) return;
      setMovies(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      if (seq !== requestSeq.current) return;
      const msg =
        err instanceof Error && err.message
          ? err.message
          : "Unable to load movies right now.";
      setError(msg);
    } finally {
      if (seq === requestSeq.current) {
        setLoading(false);
      }
    }
  }, [selectedLang]);

  useEffect(() => {
    fetchMovies();
  }, [fetchMovies]);

  const filteredMovies = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const g = selectedGenre.trim().toLowerCase();

    const filtered = movies.filter((m) => {
      if (g && !(m.genre || "").toLowerCase().includes(g)) return false;
      if (q) {
        const hay = `${m.title} ${m.genre || ""} ${m.language || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });

    return [...filtered].sort((a, b) => {
      if (sortBy === "rating_desc") return (b.rating || 0) - (a.rating || 0);
      if (sortBy === "votes_desc") return (b.vote_count || 0) - (a.vote_count || 0);
      if (sortBy === "duration_asc") {
        return (a.duration_minutes || 999) - (b.duration_minutes || 999);
      }
      return (b.release_date || "").localeCompare(a.release_date || "");
    });
  }, [movies, searchQuery, selectedGenre, sortBy]);

  const activeFilterCount =
    (selectedLang ? 1 : 0) + (selectedGenre ? 1 : 0) + (searchQuery.trim() ? 1 : 0);

  const handleClearFilters = () => {
    setSelectedLang("");
    setSelectedGenre("");
    setSearchQuery("");
    setSortBy("release_desc");
  };

  return (
    <div className="min-h-screen bg-canvas text-primary pb-16">
      <ListingPageHeader
        eyebrow="GO BEYOND • CINEMA"
        icon={<Film className="w-3.5 h-3.5" aria-hidden="true" />}
        title={`Movies in ${selectedCity}`}
        subtitle="Discover the biggest releases in 4K Laser Atmos and IMAX across Hyderabad theatres"
        breadcrumbLabel="Movies"
        resultCount={filteredMovies.length}
        resultLabel="movies"
        loading={loading}
        cityWideScope
      />

      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <ListingFilterToolbar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchPlaceholder="Search movie title or genre..."
          primaryLabel="Language"
          primaryChips={LANGUAGE_CHIPS}
          selectedPrimaryValue={selectedLang}
          onPrimarySelect={setSelectedLang}
          secondaryGroups={[
            {
              id: "genre",
              label: "Genre",
              options: GENRE_CHIPS,
              selectedValue: selectedGenre,
              onSelect: setSelectedGenre,
            },
          ]}
          sortOptions={SORT_OPTIONS}
          selectedSort={sortBy}
          onSortChange={setSortBy}
          activeFilterCount={activeFilterCount}
          onClearAll={handleClearFilters}
          drawerTitle="Filter Movies"
        />

        <DiscoveryGrid
          loading={loading}
          error={error}
          onRetry={fetchMovies}
          isEmpty={filteredMovies.length === 0}
          categoryLabel="movies"
          hasActiveFilters={activeFilterCount > 0}
          onClearFilters={handleClearFilters}
          cityWideScope
          skeletonAspect="2/3"
          skeletonCount={10}
          columnsClassName="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 sm:gap-5"
        >
          {filteredMovies.map((movie) => (
            <MovieCard key={movie.id} movie={movie} />
          ))}
        </DiscoveryGrid>
      </div>
    </div>
  );
}
