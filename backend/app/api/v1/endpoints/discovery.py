from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.movie import Movie, MovieShow, Screen, Cinema
from app.models.dining import Restaurant
from app.models.event import Event
from app.models.sports import SportsVenue, Activity
from app.models.location import Location
from app.schemas.movie import MovieResponse
from app.schemas.dining import RestaurantResponse
from app.schemas.event import EventResponse
from app.schemas.sports import SportsVenueResponse, ActivityResponse
from app.schemas.discovery import SearchResultItem, SearchResponse, HomeFeedResponse
from app.services.location import haversine_distance
from app.core.rate_limit import discovery_rate_limiter
from app.core.cache import CacheService

router = APIRouter()


def _build_search_item_from_movie(m: Movie) -> SearchResultItem:
    tags = []
    if m.genre:
        tags.extend([t.strip() for t in m.genre.split(",") if t.strip()])
    if m.language:
        tags.append(m.language)
    if m.censor_rating:
        tags.append(m.censor_rating)

    return SearchResultItem(
        id=m.id,
        title=m.title,
        slug=m.slug,
        category="MOVIES",
        category_label="Movies",
        description=f"{m.genre or 'Cinema'} • {m.language or 'All'} • {m.duration_minutes}m",
        image_url=m.poster_url,
        location_name="Hyderabad (All Cinemas)",
        locality_id=None,
        distance_km=None,
        rating=m.rating,
        price_label="From ₹200",
        price_value=200.0,
        action_url=f"/movies/{m.slug}",
        action_label="Book Tickets",
        tags=tags
    )


def _build_search_item_from_restaurant(
    r: Restaurant,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> SearchResultItem:
    dist = None
    if lat is not None and lon is not None and r.location and r.location.latitude and r.location.longitude:
        dist = haversine_distance(lat, lon, r.location.latitude, r.location.longitude)

    first_image = r.images[0] if (r.images and len(r.images) > 0) else None

    if isinstance(r.cuisines, list):
        cuisines_str = ", ".join(r.cuisines)
        tags = list(r.cuisines)
    else:
        cuisines_str = str(r.cuisines or "")
        tags = [c.strip() for c in cuisines_str.split(",") if c.strip()]

    return SearchResultItem(
        id=r.id,
        title=r.name,
        slug=r.slug,
        category="DINING",
        category_label="Dining",
        description=f"{cuisines_str} • ₹{r.cost_for_two} for two",
        image_url=first_image,
        location_name=r.location.name if r.location else "Hyderabad",
        locality_id=r.location_id,
        distance_km=dist,
        rating=r.rating,
        price_label=f"₹{r.cost_for_two} for two",
        price_value=float(r.cost_for_two),
        action_url=f"/dining/{r.slug}",
        action_label="Reserve Table",
        tags=tags
    )


def _build_search_item_from_event(
    ev: Event,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> SearchResultItem:
    dist = None
    if lat is not None and lon is not None and ev.location and ev.location.latitude and ev.location.longitude:
        dist = haversine_distance(lat, lon, ev.location.latitude, ev.location.longitude)

    prices = [float(tt.price) for tt in ev.ticket_types] if ev.ticket_types else []
    lowest = min(prices) if prices else 0.0

    tags = [ev.category]
    if ev.artist_names:
        tags.extend([a.strip() for a in ev.artist_names.split(",") if a.strip()])

    return SearchResultItem(
        id=ev.id,
        title=ev.title,
        slug=ev.slug,
        category="EVENTS",
        category_label="Live Events",
        description=f"{ev.category} • {ev.artist_names or ev.venue_name}",
        image_url=ev.banner_url,
        location_name=ev.location.name if ev.location else "Hyderabad",
        locality_id=ev.location_id,
        distance_km=dist,
        rating=4.9 if ev.is_featured else 4.5,
        price_label=f"From ₹{int(lowest)}" if lowest > 0 else "Free Entry",
        price_value=lowest,
        action_url=f"/events/{ev.slug}",
        action_label="Book Tickets",
        tags=tags
    )


def _build_search_item_from_sports(
    sv: SportsVenue,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> SearchResultItem:
    dist = None
    if lat is not None and lon is not None and sv.location and sv.location.latitude and sv.location.longitude:
        dist = haversine_distance(lat, lon, sv.location.latitude, sv.location.longitude)

    first_image = sv.images[0] if (sv.images and len(sv.images) > 0) else None
    act_prices = [float(a.base_price) for a in sv.activities if a.is_active]
    lowest = min(act_prices) if act_prices else 450.0

    if isinstance(sv.sport_types, list):
        sports_str = ", ".join(sv.sport_types)
        tags = list(sv.sport_types)
    else:
        sports_str = str(sv.sport_types or "")
        tags = [s.strip() for s in sports_str.split(",") if s.strip()]

    amenities_str = ""
    if isinstance(sv.amenities, list) and sv.amenities:
        amenities_str = f" • {', '.join(sv.amenities)}"
    elif sv.amenities:
        amenities_str = f" • {sv.amenities}"

    return SearchResultItem(
        id=sv.id,
        title=sv.name,
        slug=f"sports-venue-{sv.id}",
        category="SPORTS",
        category_label="Sports Arenas",
        description=f"{sports_str}{amenities_str}",
        image_url=first_image,
        location_name=sv.location.name if sv.location else "Hyderabad",
        locality_id=sv.location_id,
        distance_km=dist,
        rating=sv.rating,
        price_label=f"From ₹{int(lowest)}/hr",
        price_value=lowest,
        action_url=f"/sports/{sv.id}",
        action_label="Book Turf",
        tags=tags
    )


def _build_search_item_from_activity(
    act: Activity,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> SearchResultItem:
    dist = None
    if lat is not None and lon is not None and act.location and act.location.latitude and act.location.longitude:
        dist = haversine_distance(lat, lon, act.location.latitude, act.location.longitude)

    price_val = float(act.base_price)
    return SearchResultItem(
        id=act.id,
        title=act.title,
        slug=act.slug,
        category="ACTIVITIES",
        category_label="Activities",
        description=f"{act.category} • {act.duration_minutes}m duration",
        image_url=act.image_url,
        location_name=act.location.name if act.location else "Hyderabad",
        locality_id=act.location_id,
        distance_km=dist,
        rating=4.8,
        price_label=f"₹{int(price_val)} / slot",
        price_value=price_val,
        action_url=f"/activities/{act.slug}",
        action_label="Book Slot",
        tags=[act.category]
    )


@router.get("/home", response_model=HomeFeedResponse, dependencies=[Depends(discovery_rate_limiter)])
def get_home_feed(
    city_slug: str = Query("hyderabad", description="City slug"),
    locality_id: Optional[int] = Query(None, description="Optional locality ID filter"),
    lat: Optional[float] = Query(None, description="User GPS latitude"),
    lon: Optional[float] = Query(None, description="User GPS longitude"),
    db: Session = Depends(get_db)
):
    """
    Returns the comprehensive, location-aware homepage discovery feed for GO BEYOND.
    Sections include:
      - Trending Near You (Cross-vertical)
      - Popular Movies
      - Restaurants Around You
      - Upcoming Events
      - Sports Venues Near You
      - Popular Activities
      - Recommended Experiences
    """
    has_coords = (lat is not None and lon is not None)
    cache_key = f"discovery:home:{city_slug}:{locality_id or 'all'}"

    # Check cache for non-GPS feed requests
    if not has_coords:
        cached = CacheService.get(cache_key)
        if cached:
            return HomeFeedResponse(**cached)

    # 1. Resolve City & Locality
    city_name = "Hyderabad"
    city_rec = db.query(Location).filter(Location.slug == city_slug).first()
    if city_rec:
        city_name = city_rec.name

    locality_name: Optional[str] = None
    if locality_id:
        loc_rec = db.query(Location).filter(Location.id == locality_id).first()
        if loc_rec:
            locality_name = loc_rec.name

    has_coords = (lat is not None and lon is not None)

    # 2. Movies Query
    movies_q = db.query(Movie).filter(Movie.is_active == True)
    if locality_id:
        movies_q = movies_q.join(MovieShow, MovieShow.movie_id == Movie.id).join(Screen).join(Cinema).filter(
            Cinema.location_id == locality_id
        ).distinct()
    movies_db = movies_q.order_by(Movie.rating.desc()).limit(6).all()
    movies_resp = [MovieResponse.model_validate(m) for m in movies_db]

    # 3. Restaurants Query
    rest_q = db.query(Restaurant).filter(Restaurant.is_active == True)
    if locality_id:
        rest_q = rest_q.filter(Restaurant.location_id == locality_id)
    rest_db = rest_q.all()
    restaurants_resp = []
    for r in rest_db:
        item = RestaurantResponse.model_validate(r)
        item.location_name = r.location.name if r.location else "Hyderabad"
        item.locality_id = r.location_id
        if has_coords and r.location and r.location.latitude and r.location.longitude:
            item.distance_km = haversine_distance(lat, lon, r.location.latitude, r.location.longitude)
        restaurants_resp.append(item)
    if has_coords:
        restaurants_resp.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), -x.rating))
    else:
        restaurants_resp.sort(key=lambda x: -x.rating)
    restaurants_resp = restaurants_resp[:6]

    # 4. Events Query
    event_q = db.query(Event).filter(Event.is_active == True)
    if locality_id:
        event_q = event_q.filter(Event.location_id == locality_id)
    event_db = event_q.all()
    events_resp = []
    for ev in event_db:
        item = EventResponse.model_validate(ev)
        item.location_name = ev.location.name if ev.location else "Hyderabad"
        item.locality_id = ev.location_id
        if has_coords and ev.location and ev.location.latitude and ev.location.longitude:
            item.distance_km = haversine_distance(lat, lon, ev.location.latitude, ev.location.longitude)
        prices = [float(tt.price) for tt in ev.ticket_types] if ev.ticket_types else []
        item.lowest_price = min(prices) if prices else 0.0
        events_resp.append(item)
    if has_coords:
        events_resp.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), x.start_datetime))
    else:
        events_resp.sort(key=lambda x: x.start_datetime)
    events_resp = events_resp[:6]

    # 5. Sports Venues Query
    sv_q = db.query(SportsVenue).filter(SportsVenue.is_active == True)
    if locality_id:
        sv_q = sv_q.filter(SportsVenue.location_id == locality_id)
    sv_db = sv_q.all()
    sports_resp = []
    for sv in sv_db:
        item = SportsVenueResponse.model_validate(sv)
        item.location_name = sv.location.name if sv.location else "Hyderabad"
        item.locality_id = sv.location_id
        if has_coords and sv.location and sv.location.latitude and sv.location.longitude:
            item.distance_km = haversine_distance(lat, lon, sv.location.latitude, sv.location.longitude)
        item.activities = [ActivityResponse.model_validate(a) for a in sv.activities if a.is_active]
        sports_resp.append(item)
    if has_coords:
        sports_resp.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), -x.rating))
    else:
        sports_resp.sort(key=lambda x: -x.rating)
    sports_resp = sports_resp[:6]

    # 6. Activities Query
    act_q = db.query(Activity).filter(Activity.is_active == True)
    if locality_id:
        act_q = act_q.filter(Activity.location_id == locality_id)
    act_db = act_q.all()
    activities_resp = []
    for act in act_db:
        item = ActivityResponse.model_validate(act)
        item.venue_name = act.venue.name if act.venue else None
        item.location_name = act.location.name if act.location else "Hyderabad"
        item.locality_id = act.location_id
        if has_coords and act.location and act.location.latitude and act.location.longitude:
            item.distance_km = haversine_distance(lat, lon, act.location.latitude, act.location.longitude)
        activities_resp.append(item)
    if has_coords:
        activities_resp.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), x.title))
    else:
        activities_resp.sort(key=lambda x: x.title)
    activities_resp = activities_resp[:6]

    # 7. Trending Items (Multi-vertical curated blend)
    trending_items: List[SearchResultItem] = []
    for m in movies_db[:2]:
        trending_items.append(_build_search_item_from_movie(m))
    for r in rest_db[:2]:
        trending_items.append(_build_search_item_from_restaurant(r, lat, lon))
    for ev in event_db[:2]:
        trending_items.append(_build_search_item_from_event(ev, lat, lon))
    for act in act_db[:2]:
        trending_items.append(_build_search_item_from_activity(act, lat, lon))

    if has_coords:
        trending_items.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), -(x.rating or 0)))
    else:
        trending_items.sort(key=lambda x: -(x.rating or 0))
    trending_items = trending_items[:6]

    # 8. Recommended Experiences
    recommended_items: List[SearchResultItem] = []
    featured_events = [ev for ev in event_db if ev.is_featured]
    for ev in featured_events[:2]:
        recommended_items.append(_build_search_item_from_event(ev, lat, lon))
    for r in rest_db:
        if r.rating >= 4.7 and len(recommended_items) < 4:
            recommended_items.append(_build_search_item_from_restaurant(r, lat, lon))
    for act in act_db:
        if len(recommended_items) < 6:
            recommended_items.append(_build_search_item_from_activity(act, lat, lon))

    feed_resp = HomeFeedResponse(
        city_name=city_name,
        city_slug=city_slug,
        locality_name=locality_name,
        locality_id=locality_id,
        trending=trending_items,
        movies=movies_resp,
        restaurants=restaurants_resp,
        events=events_resp,
        sports_venues=sports_resp,
        activities=activities_resp,
        recommended=recommended_items[:6]
    )

    if not has_coords:
        CacheService.set(cache_key, feed_resp.model_dump(), ttl_seconds=60)

    return feed_resp


@router.get("/search", response_model=SearchResponse, dependencies=[Depends(discovery_rate_limiter)])
def unified_search(
    q: Optional[str] = Query(None, description="Search query string"),
    category: str = Query("ALL", description="Category: ALL, MOVIES, DINING, EVENTS, SPORTS, ACTIVITIES"),
    locality_id: Optional[int] = Query(None, description="Locality filter ID"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    lat: Optional[float] = Query(None, description="User GPS latitude"),
    lon: Optional[float] = Query(None, description="User GPS longitude"),
    sort_by: str = Query("relevance", description="Sort by: relevance, distance, rating, price_asc, price_desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=50, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Unified multi-vertical search engine for GO BEYOND.
    Searches across Movies, Dining, Live Events, Sports Arenas, and Activities.
    """
    category_upper = category.upper().strip()
    all_results: List[SearchResultItem] = []
    has_coords = (lat is not None and lon is not None)
    q_clean = q.strip().lower() if q else None

    # 1. MOVIES
    if category_upper in ("ALL", "MOVIES"):
        m_query = db.query(Movie).filter(Movie.is_active == True)
        if q_clean:
            m_query = m_query.filter(
                (Movie.title.ilike(f"%{q_clean}%")) |
                (Movie.genre.ilike(f"%{q_clean}%")) |
                (Movie.language.ilike(f"%{q_clean}%"))
            )
        if locality_id:
            m_query = m_query.join(MovieShow, MovieShow.movie_id == Movie.id).join(Screen).join(Cinema).filter(
                Cinema.location_id == locality_id
            ).distinct()
        for m in m_query.all():
            price_val = 200.0
            if min_price is not None and price_val < min_price:
                continue
            if max_price is not None and price_val > max_price:
                continue
            all_results.append(_build_search_item_from_movie(m))

    # 2. DINING
    if category_upper in ("ALL", "DINING"):
        r_query = db.query(Restaurant).filter(Restaurant.is_active == True)
        if locality_id:
            r_query = r_query.filter(Restaurant.location_id == locality_id)
        for r in r_query.all():
            if q_clean:
                # match restaurant name or any item in cuisines list
                name_match = q_clean in r.name.lower()
                cuisines_match = False
                if isinstance(r.cuisines, list):
                    cuisines_match = any(q_clean in c.lower() for c in r.cuisines)
                elif r.cuisines:
                    cuisines_match = q_clean in str(r.cuisines).lower()
                if not (name_match or cuisines_match):
                    continue

            price_val = float(r.cost_for_two)
            if min_price is not None and price_val < min_price:
                continue
            if max_price is not None and price_val > max_price:
                continue
            all_results.append(_build_search_item_from_restaurant(r, lat, lon))

    # 3. EVENTS
    if category_upper in ("ALL", "EVENTS"):
        ev_query = db.query(Event).filter(Event.is_active == True)
        if q_clean:
            ev_query = ev_query.filter(
                (Event.title.ilike(f"%{q_clean}%")) |
                (Event.artist_names.ilike(f"%{q_clean}%")) |
                (Event.category.ilike(f"%{q_clean}%"))
            )
        if locality_id:
            ev_query = ev_query.filter(Event.location_id == locality_id)
        for ev in ev_query.all():
            prices = [float(tt.price) for tt in ev.ticket_types] if ev.ticket_types else []
            lowest = min(prices) if prices else 0.0
            if min_price is not None and lowest < min_price:
                continue
            if max_price is not None and lowest > max_price:
                continue
            all_results.append(_build_search_item_from_event(ev, lat, lon))

    # 4. SPORTS
    if category_upper in ("ALL", "SPORTS"):
        sv_query = db.query(SportsVenue).filter(SportsVenue.is_active == True)
        if locality_id:
            sv_query = sv_query.filter(SportsVenue.location_id == locality_id)
        for sv in sv_query.all():
            if q_clean:
                name_match = q_clean in sv.name.lower()
                sports_match = False
                if isinstance(sv.sport_types, list):
                    sports_match = any(q_clean in s.lower() for s in sv.sport_types)
                elif sv.sport_types:
                    sports_match = q_clean in str(sv.sport_types).lower()
                if not (name_match or sports_match):
                    continue

            act_prices = [float(a.base_price) for a in sv.activities if a.is_active]
            lowest = min(act_prices) if act_prices else 450.0
            if min_price is not None and lowest < min_price:
                continue
            if max_price is not None and lowest > max_price:
                continue
            all_results.append(_build_search_item_from_sports(sv, lat, lon))

    # 5. ACTIVITIES
    if category_upper in ("ALL", "ACTIVITIES"):
        act_query = db.query(Activity).filter(Activity.is_active == True)
        if q_clean:
            act_query = act_query.filter(
                (Activity.title.ilike(f"%{q_clean}%")) |
                (Activity.category.ilike(f"%{q_clean}%")) |
                (Activity.description.ilike(f"%{q_clean}%"))
            )
        if locality_id:
            act_query = act_query.filter(Activity.location_id == locality_id)
        for act in act_query.all():
            price_val = float(act.base_price)
            if min_price is not None and price_val < min_price:
                continue
            if max_price is not None and price_val > max_price:
                continue
            all_results.append(_build_search_item_from_activity(act, lat, lon))

    # Sorting
    if sort_by == "distance" and has_coords:
        all_results.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), -(x.rating or 0)))
    elif sort_by == "rating":
        all_results.sort(key=lambda x: -(x.rating or 0))
    elif sort_by == "price_asc":
        all_results.sort(key=lambda x: (x.price_value if x.price_value is not None else float("inf")))
    elif sort_by == "price_desc":
        all_results.sort(key=lambda x: -(x.price_value if x.price_value is not None else 0))
    else:  # "relevance"
        if q_clean:
            all_results.sort(key=lambda x: (
                0 if q_clean in x.title.lower() else 1,
                -(x.rating or 0)
            ))
        elif has_coords:
            all_results.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), -(x.rating or 0)))
        else:
            all_results.sort(key=lambda x: -(x.rating or 0))

    total = len(all_results)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = all_results[start_idx:end_idx]
    has_more = end_idx < total

    return SearchResponse(
        total_results=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
        results=page_items
    )
