import os
import uuid
import datetime
import hmac
import hashlib
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, update, select

from app.core.config import settings
from app.core.locks import lock_service
from app.models.booking import Booking, BookingItem, SeatLock
from app.models.payment import Payment, Refund, Coupon
from app.models.user import User
from app.models.movie import MovieShow, Seat, Screen, Cinema
from app.models.dining import Restaurant, DiningTable, DiningReservation
from app.models.event import Event, EventTicketType
from app.models.sports import SportsVenue, Activity, ActivitySlot
from app.models.audit import AuditLog, Notification


TWO_PLACES = Decimal("0.01")

def quantize_amount(val: Any) -> Decimal:
    """Helper to ensure currency values are Decimal with 2 decimal places using ROUND_HALF_UP."""
    if val is None:
        return Decimal("0.00")
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# --- 1. Booking State Machine ---
VALID_STATUSES = {
    "INITIATED",
    "INVENTORY_HELD",
    "PAYMENT_PENDING",
    "CONFIRMED",
    "EXPIRED",
    "CANCELLED",
    "REFUND_PENDING",
    "REFUNDED",
    "FAILED"
}

ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "INITIATED": ["INVENTORY_HELD", "PAYMENT_PENDING", "EXPIRED", "FAILED"],
    "INVENTORY_HELD": ["PAYMENT_PENDING", "CONFIRMED", "EXPIRED", "FAILED", "CANCELLED"],
    "PAYMENT_PENDING": ["CONFIRMED", "EXPIRED", "REFUND_PENDING", "FAILED", "CANCELLED"],
    "CONFIRMED": ["CANCELLED", "REFUND_PENDING"],
    "CANCELLED": ["REFUND_PENDING", "REFUNDED"],
    "REFUND_PENDING": ["REFUNDED", "FAILED"],
    "EXPIRED": ["REFUND_PENDING"],  # When late payment arrives after hold expired
    "REFUNDED": [],                 # Terminal
    "FAILED": []                    # Terminal
}

def validate_state_transition(current_status: str, next_status: str) -> None:
    if next_status not in VALID_STATUSES:
        raise ValueError(f"Invalid booking status '{next_status}'.")
    if current_status == next_status:
        return  # Idempotent no-op
    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Illegal booking state transition from '{current_status}' to '{next_status}'."
        )


# --- 2. QR Pass Security & Reference Codes ---
def generate_booking_reference(vertical_code: str) -> str:
    """
    Generates a unique booking reference e.g. GB-MOV-2611-AB12CD
    """
    v = (vertical_code or "EXP").upper()[:3]
    date_part = datetime.datetime.now().strftime("%y%m")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"GB-{v}-{date_part}-{unique_suffix}"


def generate_secure_qr_pass_token(booking_reference: str) -> str:
    """
    Generates a cryptographically authenticated pass token.
    Contains no PII, strictly the booking reference and an HMAC signature.
    """
    sig = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        booking_reference.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:16].upper()
    return f"GB-PASS-{booking_reference}-{sig}"


# --- 3. Inventory Locking & Valuation Engine ---
class BookingEngineService:

    @staticmethod
    def calculate_merchandise_and_validate_inventory(
        db: Session,
        booking_type: str,
        items: List[Dict[str, Any]],
        current_user: User,
        lock_token: Optional[str] = None
    ) -> Tuple[Decimal, List[Dict[str, Any]], List[str], str]:
        """
        Validates inventory availability and calculates subtotals strictly from
        database catalog records (Seats, DiningTables, EventTicketTypes, ActivitySlots).
        Never trusts client-submitted prices!

        Returns:
            (total_merchandise_subtotal, validated_booking_items, acquired_redis_keys, effective_lock_token)
        """
        b_type = booking_type.upper()
        if b_type not in ["MOVIE", "DINING", "EVENT", "SPORTS", "ACTIVITY"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported booking type '{booking_type}'."
            )

        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking must contain at least one item."
            )

        total_amount = Decimal("0.00")
        validated_items = []
        acquired_lock_keys: List[str] = []
        effective_lock_token = lock_token or str(uuid.uuid4())
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        hold_ttl = settings.LOCK_EXPIRY_SECONDS

        try:
            # 1. MOVIE VERTICAL
            if b_type == "MOVIE":
                for item in items:
                    seat_id = int(item["item_id"])
                    show_id = int(item.get("details", {}).get("show_id") or item.get("show_id", 0))
                    if not show_id:
                        raise HTTPException(status_code=400, detail="Movie booking item missing show_id in details.")

                    show = db.query(MovieShow).filter(MovieShow.id == show_id).first()
                    if not show or show.status == "CANCELLED":
                        raise HTTPException(status_code=404, detail="Selected movie show is unavailable or cancelled.")

                    seat = db.query(Seat).filter(
                        Seat.id == seat_id,
                        Seat.screen_id == show.screen_id
                    ).with_for_update().first()
                    if not seat:
                        raise HTTPException(status_code=404, detail=f"Seat ID {seat_id} not found in screen.")

                    # Check confirmed OR active non-expired pending bookings (prevents same-user duplicate holds)
                    conflict = db.query(BookingItem).join(Booking).filter(
                        Booking.booking_type == "MOVIE",
                        BookingItem.item_type == "SEAT",
                        BookingItem.item_id == seat.id,
                        BookingItem.details["show_id"].as_integer() == show.id,
                        or_(
                            Booking.status == "CONFIRMED",
                            and_(
                                Booking.status.in_(["INITIATED", "INVENTORY_HELD", "PAYMENT_PENDING"]),
                                or_(Booking.expires_at.is_(None), Booking.expires_at > now_utc),
                            ),
                        ),
                    ).first()
                    if conflict:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Seat {seat.row_code}{seat.seat_number} is already booked or reserved in an active checkout."
                        )

                    # Redis distributed lock for this seat on this show
                    lock_key = f"show_{show.id}:seat_{seat.id}"
                    # Only reuse a pre-acquired hold if caller explicitly supplies its matching lock_token
                    active_db_lock = None
                    if lock_token:
                        active_db_lock = db.query(SeatLock).filter(
                            SeatLock.resource_type == "MOVIE_SHOW",
                            SeatLock.resource_id == show.id,
                            SeatLock.identifier == f"seat_{seat.id}",
                            SeatLock.user_id == current_user.id,
                            SeatLock.lock_token == lock_token,
                            SeatLock.is_released == False,
                            SeatLock.expires_at > now_utc
                        ).first()

                    if not active_db_lock:
                        # Attempt to acquire Redis lock
                        got_lock = lock_service.acquire_lock(lock_key, effective_lock_token, expiry_seconds=hold_ttl)
                        if not got_lock:
                            raise HTTPException(
                                status_code=status.HTTP_409_CONFLICT,
                                detail=f"Seat {seat.row_code}{seat.seat_number} is held by another customer. Please choose another seat."
                            )
                        acquired_lock_keys.append(lock_key)

                        # Mark any prior expired unreleased SeatLock for this seat as released before inserting
                        db.query(SeatLock).filter(
                            SeatLock.resource_type == "MOVIE_SHOW",
                            SeatLock.resource_id == show.id,
                            SeatLock.identifier == f"seat_{seat.id}",
                            SeatLock.is_released == False,
                            SeatLock.expires_at <= now_utc
                        ).update({"is_released": True})

                        # Create DB SeatLock
                        exp_time = now_utc + datetime.timedelta(seconds=hold_ttl)
                        db_lock = SeatLock(
                            resource_type="MOVIE_SHOW",
                            resource_id=show.id,
                            identifier=f"seat_{seat.id}",
                            user_id=current_user.id,
                            lock_token=effective_lock_token,
                            expires_at=exp_time,
                            is_released=False
                        )
                        db.add(db_lock)

                    # Compute price strictly from database
                    unit_price = quantize_amount(seat.base_price * show.price_multiplier)
                    subtotal = unit_price * 1
                    total_amount += subtotal

                    validated_items.append({
                        "item_type": "SEAT",
                        "item_id": seat.id,
                        "name": f"Seat {seat.row_code}{seat.seat_number} ({seat.tier})",
                        "quantity": 1,
                        "unit_price": unit_price,
                        "subtotal": subtotal,
                        "details": {
                            "show_id": show.id,
                            "movie_title": show.movie.title if show.movie else "Movie",
                            "screen_name": show.screen.name if show.screen else "Screen",
                            "cinema_name": show.screen.cinema.name if show.screen and show.screen.cinema else "Cinema",
                            "row_code": seat.row_code,
                            "seat_number": seat.seat_number,
                            "tier": seat.tier
                        }
                    })

            # 2. DINING VERTICAL
            elif b_type == "DINING":
                for item in items:
                    table_id = int(item["item_id"])
                    details = item.get("details", {})
                    restaurant_id = int(details.get("restaurant_id") or item.get("restaurant_id", 0))
                    res_date_str = details.get("reservation_date")
                    res_time_str = details.get("reservation_time")
                    guest_count = int(item.get("quantity") or details.get("guest_count", 2))

                    if not restaurant_id or not res_date_str or not res_time_str:
                        raise HTTPException(status_code=400, detail="Dining booking requires restaurant_id, reservation_date, and reservation_time.")

                    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id, Restaurant.is_active == True).first()
                    if not restaurant:
                        raise HTTPException(status_code=404, detail="Restaurant not found or inactive.")

                    table = db.query(DiningTable).filter(
                        DiningTable.id == table_id,
                        DiningTable.restaurant_id == restaurant.id
                    ).with_for_update().first()
                    if not table or not table.is_active:
                        raise HTTPException(status_code=404, detail="Dining table not found or inactive.")

                    if table.capacity < guest_count:
                        raise HTTPException(status_code=400, detail=f"Table {table.table_number} capacity ({table.capacity}) is less than guests ({guest_count}).")

                    # Parse reservation start and end datetimes
                    try:
                        res_date = datetime.date.fromisoformat(str(res_date_str))
                    except ValueError:
                        res_date = datetime.date.today()

                    try:
                        res_time = datetime.datetime.strptime(str(res_time_str), "%H:%M:%S").time()
                    except ValueError:
                        try:
                            res_time = datetime.datetime.strptime(str(res_time_str), "%H:%M").time()
                        except ValueError:
                            res_time = datetime.time(19, 30)

                    duration_min = 90
                    buffer_min = 15
                    start_dt = datetime.datetime.combine(res_date, res_time)
                    end_dt = start_dt + datetime.timedelta(minutes=duration_min + buffer_min)

                    # DB Check for overlapping active reservations under row-level FOR UPDATE lock
                    existing_res = db.query(DiningReservation).filter(
                        DiningReservation.table_id == table.id,
                        DiningReservation.status.in_(["PENDING", "CONFIRMED", "SEATED"]),
                        (
                            ((DiningReservation.start_datetime < end_dt) & (DiningReservation.end_datetime > start_dt))
                            | (
                                (DiningReservation.start_datetime == None)
                                & (DiningReservation.reservation_date == res_date)
                                & (DiningReservation.reservation_time == res_time)
                            )
                        )
                    ).first()
                    if existing_res:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Table {table.table_number} already has an active reservation during this window."
                        )

                    # Redis distributed mutex lock on physical table and time slot
                    time_slot_key = res_time.strftime("%H_%M")
                    lock_key = f"dining_table_{table.id}:{res_date}:{time_slot_key}"
                    got_lock = lock_service.acquire_lock(lock_key, effective_lock_token, expiry_seconds=hold_ttl)
                    if not got_lock:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Table {table.table_number} is currently reserved or held by another guest for this time."
                        )
                    acquired_lock_keys.append(lock_key)

                    unit_price = Decimal("0.00")  # Standard table reservation
                    subtotal = Decimal("0.00")
                    total_amount += subtotal

                    validated_items.append({
                        "item_type": "TABLE",
                        "item_id": table.id,
                        "name": f"Table {table.table_number} ({table.zone})",
                        "quantity": guest_count,
                        "unit_price": unit_price,
                        "subtotal": subtotal,
                        "details": {
                            "restaurant_id": restaurant.id,
                            "restaurant_name": restaurant.name,
                            "table_number": table.table_number,
                            "reservation_date": str(res_date),
                            "reservation_time": str(res_time),
                            "start_datetime": start_dt.isoformat(),
                            "end_datetime": end_dt.isoformat(),
                            "guest_count": guest_count
                        }
                    })

            # 3. EVENT VERTICAL
            elif b_type == "EVENT":
                for item in items:
                    ticket_type_id = int(item["item_id"])
                    quantity = int(item.get("quantity", 1))
                    if quantity <= 0:
                        raise HTTPException(status_code=400, detail="Ticket quantity must be at least 1.")

                    tt = db.query(EventTicketType).filter(EventTicketType.id == ticket_type_id).first()
                    if not tt:
                        raise HTTPException(status_code=404, detail=f"Ticket type ID {ticket_type_id} not found.")
                    if tt.available_quantity < quantity:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Not enough tickets available for '{tt.name}'. Tickets were reserved by another customer."
                        )

                    # Distributed Redis lock for ticket inventory decrement
                    lock_key = f"event_ticket_{ticket_type_id}"
                    got_lock = lock_service.acquire_lock(lock_key, effective_lock_token, expiry_seconds=30)
                    if not got_lock:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="High demand detected. Ticket availability is updating; please retry in a moment."
                        )
                    acquired_lock_keys.append(lock_key)

                    # Atomic decrement in PostgreSQL
                    stmt = (
                        update(EventTicketType)
                        .where(
                            EventTicketType.id == ticket_type_id,
                            EventTicketType.available_quantity >= quantity
                        )
                        .values(available_quantity=EventTicketType.available_quantity - quantity)
                    )
                    res = db.execute(stmt)
                    # Release the short-lived mutex lock
                    try:
                        lock_service.release_lock(lock_key, effective_lock_token)
                        if lock_key in acquired_lock_keys:
                            acquired_lock_keys.remove(lock_key)
                    except Exception:
                        pass

                    if res.rowcount == 0:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Tickets sold out or insufficient quantity available."
                        )

                    unit_price = quantize_amount(tt.price)
                    subtotal = unit_price * quantity
                    total_amount += subtotal

                    validated_items.append({
                        "item_type": "TICKET",
                        "item_id": tt.id,
                        "name": f"{tt.name} Pass",
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "subtotal": subtotal,
                        "details": {
                            "event_id": tt.event_id,
                            "event_title": tt.event.title if tt.event else "Event",
                            "venue_name": tt.event.venue_name if tt.event else "Venue",
                            "tier_name": tt.name
                        }
                    })

            # 4. SPORTS & ACTIVITY VERTICALS
            elif b_type in ["SPORTS", "ACTIVITY"]:
                for item in items:
                    slot_id = int(item["item_id"])
                    quantity = int(item.get("quantity", 1))
                    if quantity <= 0:
                        raise HTTPException(status_code=400, detail="Participant quantity must be at least 1.")

                    slot = db.query(ActivitySlot).filter(ActivitySlot.id == slot_id).first()
                    if not slot:
                        raise HTTPException(status_code=404, detail=f"Slot ID {slot_id} not found.")
                    if (slot.capacity - slot.booked_count) < quantity or not slot.is_available:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Slot '{slot.activity.title if slot.activity else slot.id}' does not have enough remaining capacity. Capacity limit reached."
                        )

                    # Distributed Redis lock for slot capacity modification
                    lock_key = f"activity_slot_{slot_id}"
                    got_lock = lock_service.acquire_lock(lock_key, effective_lock_token, expiry_seconds=30)
                    if not got_lock:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Slot is currently being booked by another customer. Please retry."
                        )
                    acquired_lock_keys.append(lock_key)

                    # Atomic increment of booked_count
                    stmt = (
                        update(ActivitySlot)
                        .where(
                            ActivitySlot.id == slot_id,
                            ActivitySlot.is_available == True,
                            (ActivitySlot.capacity - ActivitySlot.booked_count) >= quantity
                        )
                        .values(booked_count=ActivitySlot.booked_count + quantity)
                    )
                    res = db.execute(stmt)
                    # Release the short-lived mutex lock
                    try:
                        lock_service.release_lock(lock_key, effective_lock_token)
                        if lock_key in acquired_lock_keys:
                            acquired_lock_keys.remove(lock_key)
                    except Exception:
                        pass

                    if res.rowcount == 0:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Selected slot is no longer available or does not have enough capacity."
                        )

                    unit_price = quantize_amount(slot.price_override if slot.price_override is not None else slot.activity.base_price)
                    subtotal = unit_price * quantity
                    total_amount += subtotal

                    validated_items.append({
                        "item_type": "SLOT",
                        "item_id": slot.id,
                        "name": f"{slot.activity.title} ({str(slot.start_time)[:5]})" if slot.activity else f"Slot #{slot.id}",
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "subtotal": subtotal,
                        "details": {
                            "activity_id": slot.activity_id,
                            "activity_title": slot.activity.title if slot.activity else "Activity",
                            "slot_date": str(slot.slot_date),
                            "start_time": str(slot.start_time),
                            "venue_name": slot.activity.venue.name if slot.activity and slot.activity.venue else None
                        }
                    })

            return quantize_amount(total_amount), validated_items, acquired_lock_keys, effective_lock_token

        except HTTPException:
            # Rollback Redis locks acquired during this failed validation
            for k in acquired_lock_keys:
                try:
                    lock_service.release_lock(k, effective_lock_token)
                except Exception:
                    pass
            if lock_token:
                BookingEngineService.release_user_lock_token(db, current_user.id, lock_token, commit=True)
            raise
        except Exception as e:
            for k in acquired_lock_keys:
                try:
                    lock_service.release_lock(k, effective_lock_token)
                except Exception:
                    pass
            if lock_token:
                BookingEngineService.release_user_lock_token(db, current_user.id, lock_token, commit=True)
            raise HTTPException(status_code=500, detail=f"Booking inventory validation failed: {str(e)}")

    @staticmethod
    def release_user_lock_token(
        db: Session,
        user_id: int,
        lock_token: Optional[str],
        commit: bool = False,
    ) -> int:
        """Releases any unreleased SeatLocks & Redis keys owned by user_id for a failed checkout lock_token."""
        if not lock_token:
            return 0
        locks = db.query(SeatLock).filter(
            SeatLock.lock_token == lock_token,
            SeatLock.user_id == user_id,
            SeatLock.is_released == False,
        ).all()
        released = 0
        for sl in locks:
            if sl.resource_type == "MOVIE_SHOW":
                rkey = f"show_{sl.resource_id}:{sl.identifier}"
            elif sl.resource_type == "DINING_TABLE":
                rkey = f"dining_table_{sl.resource_id}:{sl.identifier}"
            else:
                rkey = f"{sl.resource_type.lower()}_{sl.resource_id}:{sl.identifier}"
            try:
                lock_service.release_lock(rkey, sl.lock_token)
            except Exception:
                pass
            sl.is_released = True
            released += 1
        if commit and released > 0:
            db.commit()
        return released

    @staticmethod
    def release_inventory_for_booking(db: Session, booking: Booking) -> None:
        """
        Reverses inventory decrement/increment and releases active locks for a cancelled or expired booking.
        """
        for item in booking.items:
            # Revert Event Tickets
            if booking.booking_type == "EVENT" and item.item_type == "TICKET":
                db.execute(
                    update(EventTicketType)
                    .where(EventTicketType.id == item.item_id)
                    .values(available_quantity=EventTicketType.available_quantity + item.quantity)
                )

            # Revert Sports/Activity Slots
            elif booking.booking_type in ["SPORTS", "ACTIVITY"] and item.item_type == "SLOT":
                db.execute(
                    update(ActivitySlot)
                    .where(ActivitySlot.id == item.item_id)
                    .values(booked_count=ActivitySlot.booked_count - item.quantity)
                )

            # Revert Movie Seat Locks (DB + Redis)
            elif booking.booking_type == "MOVIE" and item.item_type == "SEAT":
                show_id = (item.details or {}).get("show_id")
                lock_query = db.query(SeatLock).filter(
                    SeatLock.resource_type == "MOVIE_SHOW",
                    SeatLock.identifier == f"seat_{item.item_id}",
                    SeatLock.user_id == booking.user_id,
                    SeatLock.is_released == False
                )
                if show_id:
                    lock_query = lock_query.filter(SeatLock.resource_id == int(show_id))
                for sl in lock_query.all():
                    try:
                        lock_service.release_lock(f"show_{sl.resource_id}:{sl.identifier}", sl.lock_token)
                    except Exception:
                        pass
                    sl.is_released = True

            # Revert Dining Reservations
            elif booking.booking_type == "DINING" and item.item_type == "TABLE":
                db.query(DiningReservation).filter(
                    DiningReservation.booking_id == booking.id
                ).update({"status": "CANCELLED"})

        # Release any remaining expired or user-held seat locks associated with items/fallback
        for sl in db.query(SeatLock).filter(
            SeatLock.user_id == booking.user_id,
            SeatLock.is_released == False
        ).all():
            if sl.resource_type == "MOVIE_SHOW":
                rkey = f"show_{sl.resource_id}:{sl.identifier}"
            elif sl.resource_type == "DINING_TABLE":
                rkey = f"dining_table_{sl.resource_id}:{sl.identifier}"
            else:
                rkey = f"{sl.resource_type.lower()}_{sl.resource_id}:{sl.identifier}"
            try:
                lock_service.release_lock(rkey, sl.lock_token)
            except Exception:
                pass
            sl.is_released = True

    @staticmethod
    def expire_stale_bookings(db: Session) -> int:
        """
        Scans for and transitions any bookings held in INITIATED, INVENTORY_HELD,
        or PAYMENT_PENDING past expires_at to EXPIRED, and releases held inventory.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        stale_bookings = db.query(Booking).filter(
            Booking.status.in_(["INITIATED", "INVENTORY_HELD", "PAYMENT_PENDING"]),
            Booking.expires_at != None,
            Booking.expires_at < now_utc
        ).all()

        count = 0
        for b in stale_bookings:
            b.status = "EXPIRED"
            BookingEngineService.release_inventory_for_booking(db, b)
            count += 1

        if count > 0:
            db.commit()
        return count
