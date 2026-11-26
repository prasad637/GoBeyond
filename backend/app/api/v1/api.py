from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    locations,
    movies,
    dining,
    events,
    sports,
    activities,
    bookings,
    payments,
    partners,
    admin,
    notifications,
    discovery
)

api_router = APIRouter()
api_router.include_router(discovery.router, prefix="/discovery", tags=["Discovery & Search Engine"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & User Access"])
api_router.include_router(locations.router, prefix="/locations", tags=["Geolocation & Localities"])
api_router.include_router(movies.router, prefix="/movies", tags=["Movies & Cinema Booking"])
api_router.include_router(dining.router, prefix="/dining", tags=["Dining & Table Reservations"])
api_router.include_router(events.router, prefix="/events", tags=["Concerts & Live Events"])
api_router.include_router(sports.router, prefix="/sports", tags=["Sports Turfs & Arenas"])
api_router.include_router(activities.router, prefix="/activities", tags=["Recreational & Adventure Activities"])
api_router.include_router(bookings.router, prefix="/bookings", tags=["Centralized Booking Engine"])
api_router.include_router(payments.router, prefix="/payments", tags=["Razorpay Payment Gateway & Verification"])
api_router.include_router(partners.router, prefix="/partners", tags=["Partner Portal & QR Verification"])
api_router.include_router(admin.router, prefix="/admin", tags=["Super Admin Operations & Catalog Management"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["User & Partner Notifications"])
