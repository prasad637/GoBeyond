"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  CalendarDays,
  Compass,
  Film,
  Trophy,
  UtensilsCrossed,
} from "lucide-react";
import { useLocation } from "@/context/LocationContext";
import { apiRequest } from "@/lib/api";
import { HomeFeedResponse } from "@/types/discovery";
import { HeroSection } from "@/components/home/HeroSection";
import { CategoryShowcase } from "@/components/home/CategoryShowcase";
import { WhyGoBeyondSection } from "@/components/home/WhyGoBeyondSection";
import { FinalCtaSection } from "@/components/home/FinalCtaSection";
import { SectionHeading } from "@/components/discovery/SectionHeading";
import {
  HorizontalDiscoveryRail,
  RailItemWrapper,
} from "@/components/discovery/HorizontalDiscoveryRail";
import { MovieCard } from "@/components/discovery/MovieCard";
import { RestaurantCard } from "@/components/discovery/RestaurantCard";
import { EventCard } from "@/components/discovery/EventCard";
import { VenueCard } from "@/components/discovery/VenueCard";
import { ExperienceCard } from "@/components/discovery/ExperienceCard";
import { DiscoverySectionSkeleton } from "@/components/discovery/DiscoverySectionSkeleton";
import { DiscoveryEmptyState } from "@/components/discovery/DiscoveryEmptyState";

export default function HomePage() {
  const {
    selectedCity,
    selectedCitySlug,
    selectedLocality,
    gpsCoordinates,
    selectLocality,
  } = useLocation();

  const [feed, setFeed] = useState<HomeFeedResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [feedError, setFeedError] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchHomeFeed = useCallback(async () => {
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const currentRequestId = ++requestIdRef.current;

    setLoading(true);
    setFeedError(null);

    try {
      const params = new URLSearchParams();
      params.append("city_slug", selectedCitySlug || "hyderabad");
      if (selectedLocality?.id) {
        params.append("locality_id", selectedLocality.id.toString());
      }
      if (gpsCoordinates) {
        params.append("lat", gpsCoordinates.lat.toString());
        params.append("lon", gpsCoordinates.lon.toString());
      }

      const data = await apiRequest<HomeFeedResponse>(
        `/discovery/home?${params.toString()}`,
        { signal: controller.signal }
      );

      if (currentRequestId === requestIdRef.current) {
        setFeed(data);
        setFeedError(null);
      }
    } catch (err: any) {
      if (controller.signal.aborted || err?.name === "AbortError") {
        return;
      }
      if (currentRequestId === requestIdRef.current) {
        setFeedError(
          err?.message || "Unable to fetch live experiences from the server."
        );
      }
    } finally {
      if (currentRequestId === requestIdRef.current && !controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [selectedCitySlug, selectedLocality?.id, gpsCoordinates?.lat, gpsCoordinates?.lon]);

  useEffect(() => {
    fetchHomeFeed();
    return () => {
      abortControllerRef.current?.abort();
    };
  }, [fetchHomeFeed]);

  const cityName = selectedCity || "Hyderabad";
  const areaLabel = selectedLocality ? selectedLocality.name : cityName;
  const hasLocalityFilter = Boolean(selectedLocality);

  const movies = feed?.movies ?? [];
  const restaurants = feed?.restaurants ?? [];
  const events = feed?.events ?? [];
  const sportsVenues = feed?.sports_venues ?? [];
  const activities = (feed?.activities ?? []).filter(
    (act) => act.category?.toUpperCase() !== "SPORTS"
  );

  return (
    <div className="bg-canvas text-primary">
      {/* 1. Cinematic Hero */}
      <HeroSection />

      {/* Main Content Container */}
      <div className="max-w-editorial mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14 space-y-14 sm:space-y-16 lg:space-y-20">
        {/* 2. Explore Categories */}
        <CategoryShowcase feed={feed} />

        {/* Live Feed Error State */}
        {!loading && feedError ? (
          <DiscoveryEmptyState
            mode="error"
            errorMessage={feedError}
            onRetry={fetchHomeFeed}
            cityName={cityName}
            hasLocalityFilter={hasLocalityFilter}
            onResetLocality={() => selectLocality(null)}
          />
        ) : (
          <>
            {/* 3. Trending Movies */}
            <section id="trending-movies" aria-labelledby="trending-movies-heading">
              {loading ? (
                <DiscoverySectionSkeleton
                  aspect="2/3"
                  count={5}
                  ariaLabel="Loading trending movies"
                />
              ) : (
                <>
                  <SectionHeading
                    headingId="trending-movies-heading"
                    eyebrow="In Cinemas Now"
                    title="Trending Movies"
                    subtitle={`Now showing across ${cityName} cinemas — compare formats and book seats directly.`}
                    viewAllHref="/movies"
                    viewAllLabel="View All"
                    icon={<Film className="w-3.5 h-3.5" aria-hidden="true" />}
                  />
                  {movies.length > 0 ? (
                    <HorizontalDiscoveryRail
                      ariaLabel="Trending Movies"
                      itemDensity="poster"
                    >
                      {movies.map((movie) => (
                        <RailItemWrapper key={movie.id} variant="poster">
                          <MovieCard movie={movie} />
                        </RailItemWrapper>
                      ))}
                    </HorizontalDiscoveryRail>
                  ) : (
                    <DiscoveryEmptyState
                      mode="empty"
                      categoryName="Movies"
                      locationLabel={areaLabel}
                      cityName={cityName}
                      exploreHref="/movies"
                      exploreLabel="Browse Movies"
                      hasLocalityFilter={hasLocalityFilter}
                      onResetLocality={() => selectLocality(null)}
                    />
                  )}
                </>
              )}
            </section>

            {/* 4. Popular Dining */}
            <section id="popular-dining" aria-labelledby="popular-dining-heading">
              {loading ? (
                <DiscoverySectionSkeleton
                  aspect="16/10"
                  count={4}
                  ariaLabel="Loading popular dining"
                />
              ) : (
                <>
                  <SectionHeading
                    headingId="popular-dining-heading"
                    eyebrow="Culinary Selection"
                    title="Popular Dining"
                    subtitle={`Acclaimed kitchens, neighbourhood classics, and modern rooftops in ${areaLabel}.`}
                    viewAllHref="/dining"
                    viewAllLabel="View All"
                    icon={<UtensilsCrossed className="w-3.5 h-3.5" aria-hidden="true" />}
                  />
                  {restaurants.length > 0 ? (
                    <HorizontalDiscoveryRail
                      ariaLabel="Popular Dining"
                      itemDensity="landscape"
                    >
                      {restaurants.map((restaurant) => (
                        <RailItemWrapper key={restaurant.id} variant="landscape">
                          <RestaurantCard restaurant={restaurant} />
                        </RailItemWrapper>
                      ))}
                    </HorizontalDiscoveryRail>
                  ) : (
                    <DiscoveryEmptyState
                      mode="empty"
                      categoryName="Dining Venues"
                      locationLabel={areaLabel}
                      cityName={cityName}
                      exploreHref="/dining"
                      exploreLabel="Explore Dining"
                      hasLocalityFilter={hasLocalityFilter}
                      onResetLocality={() => selectLocality(null)}
                    />
                  )}
                </>
              )}
            </section>

            {/* 5. Upcoming Events */}
            <section id="upcoming-events" aria-labelledby="upcoming-events-heading">
              {loading ? (
                <DiscoverySectionSkeleton
                  aspect="16/10"
                  count={4}
                  ariaLabel="Loading upcoming events"
                />
              ) : (
                <>
                  <SectionHeading
                    headingId="upcoming-events-heading"
                    eyebrow="Live & On Stage"
                    title="Upcoming Events"
                    subtitle={`Live concerts, comedy specials, and curated city gatherings in ${areaLabel}.`}
                    viewAllHref="/events"
                    viewAllLabel="View All"
                    icon={<CalendarDays className="w-3.5 h-3.5" aria-hidden="true" />}
                  />
                  {events.length > 0 ? (
                    <HorizontalDiscoveryRail
                      ariaLabel="Upcoming Events"
                      itemDensity="landscape"
                    >
                      {events.map((eventItem) => (
                        <RailItemWrapper key={eventItem.id} variant="landscape">
                          <EventCard event={eventItem} />
                        </RailItemWrapper>
                      ))}
                    </HorizontalDiscoveryRail>
                  ) : (
                    <DiscoveryEmptyState
                      mode="empty"
                      categoryName="Events"
                      locationLabel={areaLabel}
                      cityName={cityName}
                      exploreHref="/events"
                      exploreLabel="Browse Events"
                      hasLocalityFilter={hasLocalityFilter}
                      onResetLocality={() => selectLocality(null)}
                    />
                  )}
                </>
              )}
            </section>

            {/* 6. Sports Near You */}
            <section id="sports-near-you" aria-labelledby="sports-near-you-heading">
              {loading ? (
                <DiscoverySectionSkeleton
                  aspect="16/10"
                  count={4}
                  ariaLabel="Loading sports venues"
                />
              ) : (
                <>
                  <SectionHeading
                    headingId="sports-near-you-heading"
                    eyebrow="Courts & Turfs"
                    title="Sports Near You"
                    subtitle={`Book floodlit astroturfs, synthetic courts, and box cricket arenas in ${areaLabel}.`}
                    viewAllHref="/sports"
                    viewAllLabel="View All"
                    icon={<Trophy className="w-3.5 h-3.5" aria-hidden="true" />}
                  />
                  {sportsVenues.length > 0 ? (
                    <HorizontalDiscoveryRail
                      ariaLabel="Sports Near You"
                      itemDensity="landscape"
                    >
                      {sportsVenues.map((venue) => (
                        <RailItemWrapper key={venue.id} variant="landscape">
                          <VenueCard venue={venue} />
                        </RailItemWrapper>
                      ))}
                    </HorizontalDiscoveryRail>
                  ) : (
                    <DiscoveryEmptyState
                      mode="empty"
                      categoryName="Sports Venues"
                      locationLabel={areaLabel}
                      cityName={cityName}
                      exploreHref="/sports"
                      exploreLabel="Browse Sports"
                      hasLocalityFilter={hasLocalityFilter}
                      onResetLocality={() => selectLocality(null)}
                    />
                  )}
                </>
              )}
            </section>

            {/* 7. Activities & Experiences */}
            <section
              id="activities-experiences"
              aria-labelledby="activities-experiences-heading"
            >
              {loading ? (
                <DiscoverySectionSkeleton
                  aspect="16/10"
                  count={4}
                  ariaLabel="Loading activities and experiences"
                />
              ) : (
                <>
                  <SectionHeading
                    headingId="activities-experiences-heading"
                    eyebrow="City Thrills"
                    title="Activities & Experiences"
                    subtitle={`Go-karting circuits, interactive arcades, and weekend sessions in ${areaLabel}.`}
                    viewAllHref="/activities"
                    viewAllLabel="View All"
                    icon={<Compass className="w-3.5 h-3.5" aria-hidden="true" />}
                  />
                  {activities.length > 0 ? (
                    <HorizontalDiscoveryRail
                      ariaLabel="Activities & Experiences"
                      itemDensity="landscape"
                    >
                      {activities.map((activity) => (
                        <RailItemWrapper key={activity.id} variant="landscape">
                          <ExperienceCard activity={activity} />
                        </RailItemWrapper>
                      ))}
                    </HorizontalDiscoveryRail>
                  ) : (
                    <DiscoveryEmptyState
                      mode="empty"
                      categoryName="Activities"
                      locationLabel={areaLabel}
                      cityName={cityName}
                      exploreHref="/activities"
                      exploreLabel="Explore Activities"
                      hasLocalityFilter={hasLocalityFilter}
                      onResetLocality={() => selectLocality(null)}
                    />
                  )}
                </>
              )}
            </section>
          </>
        )}

        {/* 8. Why GO BEYOND */}
        <WhyGoBeyondSection />

        {/* 9. Final CTA (Section 10 Footer is provided globally by AppShell) */}
        <FinalCtaSection />
      </div>
    </div>
  );
}
