import uuid
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.database import get_db
from app.core.locks import lock_service
from app.models.dining import Restaurant, RestaurantMenu, DiningTable, DiningReservation
from app.models.booking import Booking, BookingItem
from app.models.location import Location
from app.models.user import User
from app.schemas.dining import (
    RestaurantResponse,
    RestaurantDetailResponse,
    TableReservationRequest,
    TableReservationResponse,
    DiningTableResponse,
    MenuItemResponse
)
from app.api.deps import get_current_user

from app.services.location import haversine_distance

router = APIRouter()


@router.get("/", response_model=List[RestaurantResponse])
def list_restaurants(
    locality: Optional[str] = Query(None),
    locality_id: Optional[int] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    cuisine: Optional[str] = Query(None),
    pure_veg: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("rating", description="Sort by 'rating' or 'distance'"),
    db: Session = Depends(get_db)
):
    query = db.query(Restaurant).filter(Restaurant.is_active == True)
    if locality_id:
        query = query.filter(Restaurant.location_id == locality_id)
    elif locality:
        query = query.join(Location, Restaurant.location_id == Location.id).filter(
            (Location.slug == locality) | (Location.name.ilike(f"%{locality}%"))
        )
    if pure_veg is not None:
        query = query.filter(Restaurant.is_pure_veg == pure_veg)
    if search:
        query = query.filter(Restaurant.name.ilike(f"%{search}%"))

    restaurants = query.all()
    results = []
    has_coords = (lat is not None and lon is not None)

    for r in restaurants:
        item = RestaurantResponse.from_orm(r)
        item.location_name = r.location.name if r.location else "Hyderabad"
        item.locality_id = r.location_id
        if has_coords and r.location and r.location.latitude and r.location.longitude:
            item.distance_km = haversine_distance(lat, lon, r.location.latitude, r.location.longitude)
        results.append(item)

    if sort_by == "distance" and has_coords:
        results.sort(key=lambda x: (x.distance_km if x.distance_km is not None else float("inf"), -x.rating))
    else:
        results.sort(key=lambda x: -x.rating)

    return results


@router.get("/{identifier}", response_model=RestaurantDetailResponse)
def get_restaurant_detail(identifier: str, db: Session = Depends(get_db)):
    if identifier.isdigit():
        rest = db.query(Restaurant).filter(Restaurant.id == int(identifier), Restaurant.is_active == True).first()
    else:
        rest = db.query(Restaurant).filter(Restaurant.slug == identifier, Restaurant.is_active == True).first()

    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    active_tables = [t for t in rest.tables if t.is_active]
    return RestaurantDetailResponse(
        id=rest.id,
        name=rest.name,
        slug=rest.slug,
        cuisines=rest.cuisines,
        cost_for_two=rest.cost_for_two,
        address=rest.address,
        phone=rest.phone,
        timings=rest.timings,
        images=rest.images,
        rating=rest.rating,
        review_count=rest.review_count,
        has_buffet=rest.has_buffet,
        has_alcohol=rest.has_alcohol,
        is_pure_veg=rest.is_pure_veg,
        is_active=rest.is_active,
        location_name=rest.location.name if rest.location else "Hyderabad",
        menus=[MenuItemResponse.model_validate(m) for m in rest.menus],
        tables=[DiningTableResponse.model_validate(t) for t in active_tables]
    )


@router.post("/reserve", response_model=TableReservationResponse)
def reserve_table(
    req: TableReservationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rest = db.query(Restaurant).filter(Restaurant.id == req.restaurant_id, Restaurant.is_active == True).first()
    if not rest:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # Parse time
    try:
        res_time = datetime.datetime.strptime(req.reservation_time, "%H:%M:%S").time()
    except ValueError:
        try:
            res_time = datetime.datetime.strptime(req.reservation_time, "%H:%M").time()
        except ValueError:
            res_time = datetime.time(19, 30)

    # Compute reservation time window (duration + buffer)
    duration_min = 90
    buffer_min = 15
    start_dt = datetime.datetime.combine(req.reservation_date, res_time)
    end_dt = start_dt + datetime.timedelta(minutes=duration_min + buffer_min)

    # Lock candidate tables deterministically (id asc) to serialize concurrent & overlapping reservations
    locked_tables = db.query(DiningTable).filter(
        DiningTable.restaurant_id == rest.id,
        DiningTable.capacity >= req.guest_count,
        DiningTable.is_active == True
    ).order_by(DiningTable.id.asc()).with_for_update().all()

    available_tables = sorted(locked_tables, key=lambda t: (t.capacity, t.id))

    if not available_tables:
        raise HTTPException(status_code=400, detail=f"No tables available accommodating {req.guest_count} guests.")

    chosen_table = None
    acquired_lock_key = None
    lock_token = str(uuid.uuid4())
    slot_key = res_time.strftime("%H_%M")

    try:
        for table in available_tables:
            # Overlap check protected by PostgreSQL FOR UPDATE row lock + GiST exclusion index
            existing_res = db.query(DiningReservation).filter(
                DiningReservation.table_id == table.id,
                DiningReservation.status.in_(["CONFIRMED", "SEATED", "PENDING"]),
                (
                    ((DiningReservation.start_datetime < end_dt) & (DiningReservation.end_datetime > start_dt))
                    | (
                        (DiningReservation.start_datetime == None)
                        & (DiningReservation.reservation_date == req.reservation_date)
                        & (DiningReservation.reservation_time == res_time)
                    )
                )
            ).first()

            if existing_res:
                continue

            lock_key = f"dining_table_{table.id}:{req.reservation_date}:{slot_key}"
            if lock_service.acquire_lock(lock_key, lock_token, expiry_seconds=60):
                chosen_table = table
                acquired_lock_key = lock_key
                break

        if not chosen_table:
            raise HTTPException(
                status_code=409,
                detail="All tables for this time slot are currently reserved or locked by other guests. Please try another time."
            )

        # Create Booking Record
        ref_code = f"GB-DINE-{datetime.datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:5].upper()}"
        booking = Booking(
            booking_reference=ref_code,
            user_id=current_user.id,
            booking_type="DINING",
            total_amount=0.0,  # Table reservations are free or cover charge
            tax_amount=0.0,
            discount_amount=0.0,
            final_payable=0.0,
            status="CONFIRMED",
            qr_code_token=f"QR-DINE-{ref_code}"
        )
        db.add(booking)
        db.flush()

        reservation = DiningReservation(
            restaurant_id=rest.id,
            table_id=chosen_table.id,
            user_id=current_user.id,
            booking_id=booking.id,
            reservation_date=req.reservation_date,
            reservation_time=res_time,
            start_datetime=start_dt,
            end_datetime=end_dt,
            duration_minutes=duration_min,
            buffer_minutes=buffer_min,
            guest_count=req.guest_count,
            special_requests=req.special_requests,
            status="CONFIRMED"
        )
        db.add(reservation)

        item = BookingItem(
            booking_id=booking.id,
            item_type="TABLE",
            item_id=chosen_table.id,
            name=f"Table {chosen_table.table_number} ({chosen_table.zone})",
            quantity=req.guest_count,
            unit_price=0.0,
            subtotal=0.0,
            details={
                "restaurant_name": rest.name,
                "restaurant_id": rest.id,
                "reservation_date": str(req.reservation_date),
                "reservation_time": str(res_time),
                "table_number": chosen_table.table_number
            }
        )
        db.add(item)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Table was just reserved by another guest for an overlapping window. Please select another slot."
            )

        return TableReservationResponse(
            success=True,
            reservation_id=reservation.id,
            booking_reference=ref_code,
            restaurant_name=rest.name,
            table_number=chosen_table.table_number,
            reservation_date=req.reservation_date,
            reservation_time=str(res_time),
            guest_count=req.guest_count,
            status="CONFIRMED"
        )
    finally:
        if acquired_lock_key:
            try:
                lock_service.release_lock(acquired_lock_key, lock_token)
            except Exception:
                pass
