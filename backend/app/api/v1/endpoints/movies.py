import uuid
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.locks import lock_service
from app.models.movie import Movie, MovieShow, Screen, Seat, Cinema
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.user import User
from app.schemas.movie import (
    MovieResponse,
    MovieDetailResponse,
    MovieShowResponse,
    SeatSchema,
    LockSeatsRequest,
    LockSeatsResponse
)
from app.api.deps import get_current_user

from app.services.location import haversine_distance

router = APIRouter()


@router.get("/", response_model=List[MovieResponse])
def list_movies(
    language: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    locality_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Movie).filter(Movie.is_active == True)
    if language:
        query = query.filter(Movie.language.ilike(f"%{language}%"))
    if genre:
        query = query.filter(Movie.genre.ilike(f"%{genre}%"))
    if search:
        query = query.filter(Movie.title.ilike(f"%{search}%"))
    if locality_id:
        query = query.join(MovieShow, MovieShow.movie_id == Movie.id).join(Screen).join(Cinema).filter(
            Cinema.location_id == locality_id
        ).distinct()
    return query.order_by(Movie.release_date.desc()).all()


@router.get("/{movie_identifier}", response_model=MovieDetailResponse)
def get_movie_detail(
    movie_identifier: str,
    lat: Optional[float] = Query(None, description="User GPS latitude"),
    lon: Optional[float] = Query(None, description="User GPS longitude"),
    db: Session = Depends(get_db)
):
    if movie_identifier.isdigit():
        movie = db.query(Movie).filter(Movie.id == int(movie_identifier), Movie.is_active == True).first()
    else:
        movie = db.query(Movie).filter(Movie.slug == movie_identifier, Movie.is_active == True).first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    shows = db.query(MovieShow).join(Screen).join(Cinema).filter(
        MovieShow.movie_id == movie.id,
        MovieShow.status != "CANCELLED"
    ).all()

    shows_data = []
    has_coords = (lat is not None and lon is not None)

    for s in shows:
        cinema = s.screen.cinema
        c_lat = cinema.latitude or (cinema.location.latitude if cinema.location else None)
        c_lon = cinema.longitude or (cinema.location.longitude if cinema.location else None)
        dist_km = haversine_distance(lat, lon, c_lat, c_lon) if (has_coords and c_lat and c_lon) else None

        shows_data.append(MovieShowResponse(
            id=s.id,
            movie_id=s.movie_id,
            screen_id=s.screen_id,
            cinema_id=cinema.id,
            cinema_name=cinema.name,
            screen_name=s.screen.name,
            screen_type=s.screen.screen_type,
            show_date=s.show_date,
            start_time=s.start_time,
            end_time=s.end_time,
            price_multiplier=s.price_multiplier,
            status=s.status,
            address=cinema.address,
            location_name=cinema.location.name if cinema.location else cinema.city,
            locality_id=cinema.location_id,
            distance_km=dist_km
        ))

    if has_coords:
        shows_data.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), x.show_date, x.start_time))

    return MovieDetailResponse(
        id=movie.id,
        title=movie.title,
        slug=movie.slug,
        description=movie.description,
        duration_minutes=movie.duration_minutes,
        language=movie.language,
        genre=movie.genre,
        censor_rating=movie.censor_rating,
        release_date=movie.release_date,
        poster_url=movie.poster_url,
        backdrop_url=movie.backdrop_url,
        trailer_url=movie.trailer_url,
        rating=movie.rating,
        vote_count=movie.vote_count,
        is_active=movie.is_active,
        shows=shows_data
    )


@router.get("/shows/{show_id}/seats", response_model=List[SeatSchema])
def get_show_seats(show_id: int, db: Session = Depends(get_db)):
    show = db.query(MovieShow).filter(MovieShow.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    seats = db.query(Seat).filter(Seat.screen_id == show.screen_id).order_by(Seat.row_code, Seat.seat_number).all()
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Find already confirmed booked seats for this show
    confirmed_bookings = db.query(BookingItem.item_id).join(Booking).filter(
        Booking.status == "CONFIRMED",
        Booking.booking_type == "MOVIE",
        BookingItem.details["show_id"].as_integer() == show_id
    ).all()
    booked_seat_ids = {b[0] for b in confirmed_bookings}

    # Find seats held in active unexpired checkouts or DB SeatLocks
    active_booking_holds = db.query(BookingItem.item_id).join(Booking).filter(
        Booking.booking_type == "MOVIE",
        BookingItem.item_type == "SEAT",
        BookingItem.details["show_id"].as_integer() == show_id,
        Booking.status.in_(["INITIATED", "INVENTORY_HELD", "PAYMENT_PENDING"]),
        sa.or_(Booking.expires_at.is_(None), Booking.expires_at > now_utc),
    ).all()
    db_held_seat_ids = {b[0] for b in active_booking_holds}

    active_seat_locks = db.query(SeatLock.identifier).filter(
        SeatLock.resource_type == "MOVIE_SHOW",
        SeatLock.resource_id == show_id,
        SeatLock.is_released == False,
        SeatLock.expires_at > now_utc,
    ).all()
    for (ident,) in active_seat_locks:
        if isinstance(ident, str) and ident.startswith("seat_"):
            try:
                db_held_seat_ids.add(int(ident.split("_", 1)[1]))
            except ValueError:
                pass

    result = []
    for s in seats:
        seat_identifier = f"show_{show_id}:seat_{s.id}"
        is_locked = lock_service.is_locked(seat_identifier) or (s.id in db_held_seat_ids)
        is_booked = s.id in booked_seat_ids

        seat_schema = SeatSchema(
            id=s.id,
            screen_id=s.screen_id,
            row_code=s.row_code,
            seat_number=s.seat_number,
            tier=s.tier,
            base_price=round(s.base_price * show.price_multiplier, 2),
            is_accessible=s.is_accessible,
            is_locked=is_locked,
            is_booked=is_booked
        )
        result.append(seat_schema)

    return result


@router.post("/shows/{show_id}/lock-seats", response_model=LockSeatsResponse)
def lock_seats_for_checkout(
    show_id: int,
    req: LockSeatsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not req.seat_ids:
        raise HTTPException(status_code=400, detail="No seats selected")

    show = db.query(MovieShow).filter(MovieShow.id == show_id).first()
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # Check already confirmed OR active unexpired pending bookings before acquiring locks
    existing_booking = db.query(BookingItem).join(Booking).filter(
        Booking.booking_type == "MOVIE",
        BookingItem.item_type == "SEAT",
        BookingItem.item_id.in_(req.seat_ids),
        BookingItem.details["show_id"].as_integer() == show_id,
        sa.or_(
            Booking.status == "CONFIRMED",
            sa.and_(
                Booking.status.in_(["INITIATED", "INVENTORY_HELD", "PAYMENT_PENDING"]),
                sa.or_(Booking.expires_at.is_(None), Booking.expires_at > now_utc),
            ),
        ),
    ).first()
    if existing_booking:
        raise HTTPException(
            status_code=409,
            detail=f"Seat '{existing_booking.name}' is currently booked or reserved in an active checkout."
        )

    lock_token = str(uuid.uuid4())
    acquired_locks = []

    try:
        for seat_id in req.seat_ids:
            key = f"show_{show_id}:seat_{seat_id}"
            success = lock_service.acquire_lock(key, lock_token, expiry_seconds=600)
            if not success:
                # Rollback acquired locks
                for acq in acquired_locks:
                    lock_service.release_lock(acq, lock_token)
                raise HTTPException(
                    status_code=409,
                    detail=f"Seat ID {seat_id} is currently held by another user. Please choose another seat."
                )
            acquired_locks.append(key)

        # Record in seat_locks database table
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=600)
        for seat_id in req.seat_ids:
            sl = SeatLock(
                resource_type="MOVIE_SHOW",
                resource_id=show_id,
                identifier=f"seat_{seat_id}",
                user_id=current_user.id,
                lock_token=lock_token,
                expires_at=expires_at
            )
            db.add(sl)
        db.commit()

        # Calculate total price
        seats = db.query(Seat).filter(Seat.id.in_(req.seat_ids)).all()
        total_price = sum(s.base_price * show.price_multiplier for s in seats)

        return LockSeatsResponse(
            success=True,
            lock_token=lock_token,
            show_id=show_id,
            locked_seat_ids=req.seat_ids,
            expires_at=expires_at.isoformat(),
            total_amount=round(total_price, 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        for acq in acquired_locks:
            lock_service.release_lock(acq, lock_token)
        raise HTTPException(status_code=500, detail=str(e))
