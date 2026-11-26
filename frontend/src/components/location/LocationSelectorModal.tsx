"use client";

import React, { useState, useEffect } from "react";
import { useLocation, LocationItem } from "@/context/LocationContext";
import {
  MapPin,
  Navigation,
  Check,
  Search,
  AlertCircle,
  Building2,
  X,
} from "lucide-react";
import { Badge, Button, Modal } from "@/components/ui";
import { cn } from "@/lib/cn";

export default function LocationSelectorModal() {
  const {
    isLocationModalOpen,
    closeLocationModal,
    selectedCity,
    selectedLocality,
    localities,
    supportedCities,
    selectLocality,
    selectCity,
    detectLocation,
    isDetecting,
    gpsStatus,
    gpsError,
    searchLocalities,
  } = useLocation();

  const [searchQuery, setSearchQuery] = useState("");
  const [displayedLocalities, setDisplayedLocalities] =
    useState<LocationItem[]>(localities);
  const [isSearching, setIsSearching] = useState(false);

  // Sync displayed localities when modal opens or localities change
  useEffect(() => {
    setDisplayedLocalities(localities);
  }, [localities]);

  // Reset search input whenever the modal closes so reopening shows all localities
  useEffect(() => {
    if (!isLocationModalOpen) {
      setSearchQuery("");
    }
  }, [isLocationModalOpen]);

  // Handle debounced locality search query
  useEffect(() => {
    if (!searchQuery.trim()) {
      setDisplayedLocalities(localities);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await searchLocalities(searchQuery);
        setDisplayedLocalities(results);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery, localities, searchLocalities]);

  const activeCityObj = supportedCities.find(
    (c) => c.name.toLowerCase() === selectedCity.toLowerCase()
  );
  const activeStateLabel =
    activeCityObj?.state || localities[0]?.state || "India";

  return (
    <Modal
      isOpen={isLocationModalOpen}
      onClose={closeLocationModal}
      size="md"
      title={
        <span className="flex items-center gap-2.5">
          <span className="w-8 h-8 rounded-xl bg-brand-500/12 border border-brand-500/25 flex items-center justify-center text-brand-400 shrink-0">
            <MapPin className="w-4 h-4" />
          </span>
          <span>Choose Your Locality</span>
        </span>
      }
      description={`Discover curated experiences near you in ${selectedCity}`}
      bodyClassName="space-y-4"
    >
      {/* Active City & Multi-City Selector */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 p-3.5 rounded-xl bg-surface-2 border border-subtle text-xs">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-brand-400 shrink-0" />
          <span className="text-secondary">
            City: <strong className="text-primary font-semibold">{selectedCity}</strong>
          </span>
          <Badge variant="brand" size="sm">
            {activeStateLabel}
          </Badge>
        </div>

        {supportedCities.length > 1 && (
          <div className="flex flex-wrap gap-1.5">
            {supportedCities.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => selectCity(c)}
                className={cn(
                  "px-2.5 py-1 rounded-lg text-xs font-medium transition-colors",
                  selectedCity === c.name
                    ? "bg-brand-500 text-white"
                    : "bg-surface border border-subtle text-secondary hover:text-primary"
                )}
              >
                {c.name}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* GPS Auto-Detect Action */}
      <Button
        variant="secondary"
        size="lg"
        fullWidth
        isLoading={isDetecting}
        loadingText="Detecting GPS location..."
        onClick={detectLocation}
        leftIcon={
          <Navigation className="w-4 h-4 text-brand-400" />
        }
        className="border-brand-500/35 hover:border-brand-500/60"
      >
        Use Current GPS Location
      </Button>

      {/* GPS Denied / Error Banner */}
      {(gpsStatus === "denied" || gpsStatus === "unavailable" || Boolean(gpsError)) && (
        <div
          role="alert"
          className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-2.5 text-xs text-amber-200"
        >
          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-300">Location Access Notice</p>
            <p className="text-amber-200/85 mt-0.5 leading-relaxed">
              {gpsError ||
                "GPS permission was denied. We will never guess your area — please manually pick your preferred locality below."}
            </p>
          </div>
        </div>
      )}

      {/* Search Localities (16px on mobile to prevent iOS Safari zoom) */}
      <div className="relative flex items-center">
        <Search className="pointer-events-none absolute left-3.5 w-4 h-4 text-muted" />
        <input
          type="text"
          placeholder="Search locality (e.g. Banjara Hills, Gachibowli, Hitec City)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          aria-label="Search localities"
          className="w-full h-11 md:h-10 pl-10 pr-20 bg-surface-2 border border-subtle rounded-lg text-base md:text-sm text-primary placeholder:text-muted focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-colors"
        />
        <div className="absolute right-3 flex items-center gap-1.5">
          {isSearching && (
            <span className="text-[11px] text-brand-400 animate-pulse font-medium">
              Searching...
            </span>
          )}
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              aria-label="Clear locality search"
              className="p-1 text-secondary hover:text-primary rounded-md"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* All City Option */}
      <button
        type="button"
        onClick={() => {
          selectLocality(null);
          closeLocationModal();
        }}
        className={cn(
          "w-full p-3.5 rounded-xl border flex items-center justify-between text-left transition-colors",
          !selectedLocality
            ? "bg-brand-500/12 border-brand-500/60 text-primary"
            : "bg-surface-2/60 border-subtle hover:bg-surface-2 hover:border-strong text-secondary hover:text-primary"
        )}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span
            className={cn(
              "w-2.5 h-2.5 rounded-full shrink-0",
              !selectedLocality ? "bg-brand-500" : "bg-gray-600"
            )}
          />
          <div className="min-w-0">
            <div className="text-sm font-semibold text-primary">
              All {selectedCity}
            </div>
            <div className="text-xs text-secondary truncate">
              Browse experiences across the entire city
            </div>
          </div>
        </div>
        {!selectedLocality && <Check className="w-4 h-4 text-brand-400 shrink-0" />}
      </button>

      {/* Popular Localities Grid */}
      <div className="space-y-2 pt-1">
        <div className="flex items-center justify-between px-0.5">
          <span className="text-[11px] font-semibold text-secondary uppercase tracking-wider">
            Localities in {selectedCity}
          </span>
          <span className="text-[11px] text-muted tabular-nums-lining">
            {displayedLocalities.length} available
          </span>
        </div>

        <div className="max-h-60 overflow-y-auto grid grid-cols-1 sm:grid-cols-2 gap-2 pr-0.5">
          {displayedLocalities.map((loc) => {
            const isSelected = selectedLocality?.id === loc.id;
            return (
              <button
                key={loc.id}
                type="button"
                onClick={() => {
                  selectLocality(loc);
                  closeLocationModal();
                }}
                className={cn(
                  "min-h-[46px] p-3 rounded-xl border flex items-center justify-between gap-2 text-left text-sm transition-colors",
                  isSelected
                    ? "bg-brand-500/12 border-brand-500/60 text-primary font-semibold"
                    : "bg-surface-2/60 border-subtle hover:bg-surface-2 hover:border-strong text-secondary hover:text-primary"
                )}
              >
                <span className="flex items-center gap-2 min-w-0">
                  <MapPin
                    className={cn(
                      "w-4 h-4 shrink-0",
                      isSelected ? "text-brand-400" : "text-muted"
                    )}
                  />
                  <span className="truncate">{loc.name}</span>
                </span>

                <span className="flex items-center gap-1.5 shrink-0">
                  {loc.distance_km !== undefined && loc.distance_km !== null && (
                    <Badge variant="info" size="sm" className="tabular-nums-lining">
                      {loc.distance_km} km
                    </Badge>
                  )}
                  {isSelected && <Check className="w-4 h-4 text-brand-400" />}
                </span>
              </button>
            );
          })}

          {displayedLocalities.length === 0 && (
            <div className="col-span-full py-8 text-center text-muted text-sm">
              No localities found matching &ldquo;{searchQuery}&rdquo;.
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
