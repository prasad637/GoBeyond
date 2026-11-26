"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { apiRequest } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

export interface LocationItem {
  id: number;
  name: string;
  slug: string;
  type: string;
  state: string;
  country: string;
  latitude?: number;
  longitude?: number;
  distance_km?: number | null;
}

export interface CityItem {
  id: number;
  name: string;
  slug: string;
  state: string;
  country: string;
  localities_count: number;
}

export type GpsStatus = "idle" | "loading" | "granted" | "denied" | "unavailable";

interface NearbyLocalityResponse {
  nearest_locality: LocationItem;
  distance_km: number;
  nearby_localities: LocationItem[];
}

interface LocationContextType {
  selectedCity: string;
  selectedCitySlug: string;
  selectedLocality: LocationItem | null;
  localities: LocationItem[];
  supportedCities: CityItem[];
  gpsStatus: GpsStatus;
  gpsCoordinates: { lat: number; lon: number } | null;
  gpsError: string | null;
  isDetecting: boolean;
  isLocationModalOpen: boolean;
  openLocationModal: () => void;
  closeLocationModal: () => void;
  selectLocality: (locality: LocationItem | null) => Promise<void>;
  selectCity: (city: CityItem) => void;
  detectLocation: () => Promise<void>;
  searchLocalities: (query: string) => Promise<LocationItem[]>;
}

const LocationContext = createContext<LocationContextType | undefined>(undefined);

const LOCAL_STORAGE_KEY = "gobeyond_selected_locality";
const LOCAL_STORAGE_CITY_KEY = "gobeyond_selected_city";

export function LocationProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [selectedCity, setSelectedCity] = useState("Hyderabad");
  const [selectedCitySlug, setSelectedCitySlug] = useState("hyderabad");
  const [selectedLocality, setSelectedLocality] = useState<LocationItem | null>(null);
  const [localities, setLocalities] = useState<LocationItem[]>([]);
  const [supportedCities, setSupportedCities] = useState<CityItem[]>([]);
  const [gpsStatus, setGpsStatus] = useState<GpsStatus>("idle");
  const [gpsCoordinates, setGpsCoordinates] = useState<{ lat: number; lon: number } | null>(null);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false);

  // 1. Load localities and cities from PostgreSQL backend APIs
  const loadData = useCallback(async () => {
    try {
      const [citiesData, localitiesData] = await Promise.all([
        apiRequest<CityItem[]>("/locations/cities").catch(() => []),
        apiRequest<LocationItem[]>(`/locations/localities?city_slug=${selectedCitySlug}`).catch(() => [])
      ]);
      if (citiesData.length > 0) setSupportedCities(citiesData);
      if (localitiesData.length > 0) setLocalities(localitiesData);
    } catch (err) {
      console.error("Failed to load location data from backend:", err);
    }
  }, [selectedCitySlug]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 2. Initialize from localStorage or logged-in user profile
  useEffect(() => {
    if (typeof window === "undefined") return;

    // A. Priority to user's saved profile locality if logged in
    if (user && user.locality_id && localities.length > 0) {
      const matching = localities.find((l) => l.id === user.locality_id);
      if (matching) {
        setSelectedLocality(matching);
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(matching));
        return;
      }
    }

    // B. Guest / persistent localStorage check
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.id && parsed.name) {
          setSelectedLocality(parsed);
        }
      }
    } catch {
      // ignore JSON parse error
    }
  }, [user, localities]);

  // 3. User manually selects a locality
  const selectLocality = async (locality: LocationItem | null) => {
    setSelectedLocality(locality);

    if (locality) {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(locality));
      try {
        // Send to backend (persists to DB if user has token, confirms for guests)
        await apiRequest("/locations/select", {
          method: "POST",
          body: JSON.stringify({ locality_id: locality.id })
        });
      } catch (err) {
        console.warn("Could not sync selected locality with backend:", err);
      }
    } else {
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    }
  };

  const selectCity = (city: CityItem) => {
    setSelectedCity(city.name);
    setSelectedCitySlug(city.slug);
    setSelectedLocality(null);
    localStorage.setItem(LOCAL_STORAGE_CITY_KEY, JSON.stringify(city));
    localStorage.removeItem(LOCAL_STORAGE_KEY);
  };

  // 4. GPS-Based Location Detection with strict user permission handling
  const detectLocation = async () => {
    setIsDetecting(true);
    setGpsError(null);

    if (typeof window === "undefined" || !navigator.geolocation) {
      setGpsStatus("unavailable");
      setGpsError("GPS geolocation is not supported by your browser. Please select your locality manually.");
      setIsDetecting(false);
      return;
    }

    setGpsStatus("loading");

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        setGpsCoordinates({ lat, lon });
        setGpsStatus("granted");

        try {
          // Discover nearest locality via Haversine backend endpoint
          const result = await apiRequest<NearbyLocalityResponse>(
            `/locations/nearby?lat=${lat}&lon=${lon}&city_slug=${selectedCitySlug}`
          );

          if (result && result.nearest_locality) {
            const nearest = result.nearest_locality;
            setSelectedLocality(nearest);
            localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(nearest));

            // Sync with backend profile if authenticated
            apiRequest("/locations/select", {
              method: "POST",
              body: JSON.stringify({ locality_id: nearest.id })
            }).catch(() => {});

            // Update localities list with distance annotations
            if (result.nearby_localities && result.nearby_localities.length > 0) {
              setLocalities(result.nearby_localities);
            }
          }
        } catch (err) {
          console.error("Failed to discover nearest locality from GPS coordinates:", err);
        } finally {
          setIsDetecting(false);
          setIsLocationModalOpen(false);
        }
      },
      (error) => {
        // PERMISSION DENIED or GPS ERROR:
        // NEVER silently assign Banjara Hills or any locality!
        // Keep city as Hyderabad, leave locality unassigned, and inform user.
        setIsDetecting(false);
        setGpsStatus("denied");

        let msg = "GPS permission was denied. Please select your locality manually from the list below.";
        if (error.code === error.TIMEOUT) {
          msg = "GPS request timed out. Please pick your locality manually.";
        } else if (error.code === error.POSITION_UNAVAILABLE) {
          msg = "GPS position unavailable. Please choose your locality manually.";
        }
        setGpsError(msg);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  };

  // 5. Locality search with Haversine distance
  const searchLocalities = async (query: string): Promise<LocationItem[]> => {
    try {
      let url = `/locations/localities?city_slug=${selectedCitySlug}&search=${encodeURIComponent(query)}`;
      if (gpsCoordinates) {
        url += `&lat=${gpsCoordinates.lat}&lon=${gpsCoordinates.lon}&sort_by=distance`;
      }
      const data = await apiRequest<LocationItem[]>(url);
      return data;
    } catch {
      return localities.filter((l) => l.name.toLowerCase().includes(query.toLowerCase()));
    }
  };

  return (
    <LocationContext.Provider
      value={{
        selectedCity,
        selectedCitySlug,
        selectedLocality,
        localities,
        supportedCities,
        gpsStatus,
        gpsCoordinates,
        gpsError,
        isDetecting,
        isLocationModalOpen,
        openLocationModal: () => setIsLocationModalOpen(true),
        closeLocationModal: () => setIsLocationModalOpen(false),
        selectLocality,
        selectCity,
        detectLocation,
        searchLocalities,
      }}
    >
      {children}
    </LocationContext.Provider>
  );
}

export function useLocation() {
  const context = useContext(LocationContext);
  if (!context) {
    throw new Error("useLocation must be used within a LocationProvider");
  }
  return context;
}
