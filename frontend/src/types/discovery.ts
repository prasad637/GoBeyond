export interface SearchResultItem {
  id: number;
  title: string;
  slug: string;
  category: "MOVIES" | "DINING" | "EVENTS" | "SPORTS" | "ACTIVITIES" | string;
  category_label: string;
  description?: string | null;
  image_url?: string | null;
  location_name: string;
  locality_id?: number | null;
  distance_km?: number | null;
  rating?: number | null;
  price_label?: string | null;
  price_value?: number | null;
  action_url: string;
  action_label: string;
  tags?: string[];
}

export interface SearchResponse {
  total_results: number;
  page: number;
  page_size: number;
  has_more: boolean;
  results: SearchResultItem[];
}

export interface MovieFeedItem {
  id: number;
  title: string;
  slug: string;
  description?: string | null;
  duration_minutes?: number | null;
  language?: string | null;
  genre?: string | null;
  censor_rating?: string | null;
  release_date?: string | null;
  poster_url?: string | null;
  backdrop_url?: string | null;
  trailer_url?: string | null;
  rating?: number | null;
  vote_count?: number | null;
  is_active?: boolean;
}

export interface RestaurantFeedItem {
  id: number;
  name: string;
  slug: string;
  cuisines?: string[] | string | null;
  cost_for_two?: number | null;
  address?: string | null;
  phone?: string | null;
  timings?: string | null;
  images?: string[] | null;
  rating?: number | null;
  review_count?: number | null;
  has_buffet?: boolean;
  has_alcohol?: boolean;
  is_pure_veg?: boolean;
  is_active?: boolean;
  location_name?: string | null;
  locality_id?: number | null;
  distance_km?: number | null;
}

export interface EventFeedItem {
  id: number;
  title: string;
  slug: string;
  category: string;
  description?: string | null;
  artist_names?: string | null;
  venue_name?: string | null;
  venue_address?: string | null;
  start_datetime?: string | null;
  end_datetime?: string | null;
  banner_url?: string | null;
  is_featured?: boolean;
  is_active?: boolean;
  location_name?: string | null;
  locality_id?: number | null;
  distance_km?: number | null;
  lowest_price?: number | null;
}

export interface ActivityFeedItem {
  id: number;
  venue_id?: number | null;
  venue_name?: string | null;
  title: string;
  slug: string;
  category: string;
  description?: string | null;
  base_price?: number | null;
  duration_minutes?: number | null;
  image_url?: string | null;
  min_age?: number | null;
  is_active?: boolean;
  location_name?: string | null;
  locality_id?: number | null;
  distance_km?: number | null;
}

export interface SportsVenueFeedItem {
  id: number;
  name: string;
  sport_types?: string[] | string | null;
  address?: string | null;
  amenities?: string[] | string | null;
  images?: string[] | null;
  rating?: number | null;
  is_active?: boolean;
  location_name?: string | null;
  locality_id?: number | null;
  distance_km?: number | null;
  activities?: ActivityFeedItem[];
}

export interface HomeFeedResponse {
  city_name: string;
  city_slug: string;
  locality_name?: string | null;
  locality_id?: number | null;
  trending: SearchResultItem[];
  movies: MovieFeedItem[];
  restaurants: RestaurantFeedItem[];
  events: EventFeedItem[];
  sports_venues: SportsVenueFeedItem[];
  activities: ActivityFeedItem[];
  recommended: SearchResultItem[];
}
