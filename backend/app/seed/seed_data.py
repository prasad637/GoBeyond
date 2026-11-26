import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, Base, engine
from app.core.security import get_password_hash
from app.models import (
    User, UserProfile, Role, Permission, user_roles,
    Location, Partner, PartnerDocument,
    Movie, Cinema, Screen, Seat, MovieShow,
    Restaurant, RestaurantMenu, DiningTable,
    Event, EventTicketType,
    SportsVenue, Activity, ActivitySlot,
    Coupon
)

def run_seed():
    db = SessionLocal()
    try:
        print("Checking if database already seeded...")
        existing_admin = db.query(User).filter(User.email == "admin@gobeyond.com").first()
        if existing_admin:
            changes_made = False

            # 1. Idempotently repair any legacy UserProfile where city_id holds a LOCALITY id
            for prof in db.query(UserProfile).filter(
                UserProfile.locality_id.is_(None),
                UserProfile.city_id.isnot(None)
            ).all():
                loc_row = db.query(Location).filter(Location.id == prof.city_id).first()
                if loc_row and loc_row.type == "LOCALITY":
                    prof.locality_id = loc_row.id
                    if loc_row.parent_id:
                        prof.city_id = loc_row.parent_id
                    changes_made = True

            # 2. Idempotently replace off-theme / unavailable Unsplash stock URLs with curated local assets
            movie_poster_updates = {
                "devara-part-1": ("/images/seed/movie-devara.jpg", "photo-1536440136628"),
                "dune-part-two": ("/images/seed/movie-dune.jpg", "photo-1518709268805"),
                "pushpa-2-the-rule": ("/images/seed/movie-pushpa.jpg", "photo-1574375927938"),
            }
            for m_slug, (local_path, legacy_sub) in movie_poster_updates.items():
                mov = db.query(Movie).filter(Movie.slug == m_slug).first()
                if mov and (not mov.poster_url or legacy_sub in mov.poster_url):
                    mov.poster_url = local_path
                    changes_made = True

            for sv in db.query(SportsVenue).filter(SportsVenue.name == "Apex Turf Arena: Kondapur").all():
                imgs = list(sv.images or [])
                if not imgs or any("photo-1529900245534" in u for u in imgs):
                    sv.images = ["/images/seed/sports-turf.jpg"]
                    changes_made = True

            act_img_updates = {
                "floodlit-astroturf-football-apex": ("/images/seed/sports-turf.jpg", "photo-1529900245534"),
                "pitstop-high-speed-go-karting-madhapur": ("/images/seed/activity-gokart.jpg", "photo-1596727147705"),
            }
            for a_slug, (local_path, legacy_sub) in act_img_updates.items():
                act_row = db.query(Activity).filter(Activity.slug == a_slug).first()
                if act_row and (not act_row.image_url or legacy_sub in act_row.image_url):
                    act_row.image_url = local_path
                    changes_made = True

            # 3. Idempotently backfill ActivitySlot rows for seeded activities that lack slots
            today = datetime.date.today()
            slot_specs = {
                "pitstop-high-speed-go-karting-madhapur": ([11, 14, 17, 19, 21], 8),
                "mystery-rooms-haunted-mansion-gachibowli": ([12, 15, 18, 20], 6),
            }
            added_slots = 0
            for slug, (hours, cap) in slot_specs.items():
                act_obj = db.query(Activity).filter(Activity.slug == slug).first()
                if act_obj and db.query(ActivitySlot).filter(ActivitySlot.activity_id == act_obj.id).count() == 0:
                    dur_hrs = max(1, int(round((act_obj.duration_minutes or 60) / 60)))
                    for hour in hours:
                        db.add(ActivitySlot(
                            activity_id=act_obj.id,
                            slot_date=today,
                            start_time=datetime.time(hour, 0),
                            end_time=datetime.time(hour + dur_hrs, 0),
                            capacity=cap,
                            booked_count=0,
                            price_override=None,
                            is_available=True
                        ))
                        added_slots += 1
                        changes_made = True
            if changes_made:
                db.commit()
                print(f"Applied idempotent seed upgrades (added_slots={added_slots}).")
            else:
                print("Database already contains seed data. Skipping duplicate seed.")
            return

        print("Seeding Roles...")
        roles_data = [
            ("customer", "Standard consumer discovering and booking experiences"),
            ("partner_restaurant", "Dining partner managing restaurants, menus, and table reservations"),
            ("partner_cinema", "Cinema operator managing screens, movies, and showtimes"),
            ("partner_event", "Event organizer hosting concerts, comedy, and nightlife shows"),
            ("partner_sports", "Sports and recreational activity venue operator"),
            ("super_admin", "Global administrator with full control over the platform")
        ]
        role_objs = {}
        for name, desc in roles_data:
            role = Role(name=name, description=desc)
            db.add(role)
            db.flush()
            role_objs[name] = role

        print("Seeding Locations in Hyderabad...")
        hyd_city = Location(
            name="Hyderabad",
            slug="hyderabad",
            type="CITY",
            state="Telangana",
            country="India",
            latitude=17.3850,
            longitude=78.4867,
            is_active=True
        )
        db.add(hyd_city)
        db.flush()

        localities_data = [
            ("Jubilee Hills", "jubilee-hills", 17.4319, 78.4073),
            ("Banjara Hills", "banjara-hills", 17.4156, 78.4354),
            ("Gachibowli", "gachibowli", 17.4401, 78.3489),
            ("Hitec City", "hitec-city", 17.4435, 78.3772),
            ("Madhapur", "madhapur", 17.4483, 78.3915),
            ("Kondapur", "kondapur", 17.4699, 78.3578),
            ("Begumpet", "begumpet", 17.4447, 78.4664),
            ("Kukatpally", "kukatpally", 17.4947, 78.3996),
            ("Secunderabad", "secunderabad", 17.4399, 78.4983),
            ("Charminar", "charminar", 17.3616, 78.4747),
        ]
        locality_objs = {}
        for loc_name, loc_slug, lat, lon in localities_data:
            loc = Location(
                name=loc_name,
                slug=loc_slug,
                type="LOCALITY",
                parent_id=hyd_city.id,
                state="Telangana",
                country="India",
                latitude=lat,
                longitude=lon,
                is_active=True
            )
            db.add(loc)
            db.flush()
            locality_objs[loc_slug] = loc

        print("Seeding Users & Partners...")
        # 1. Super Admin
        admin_user = User(
            email="admin@gobeyond.com",
            phone="9000000001",
            full_name="Super Administrator",
            hashed_password=get_password_hash("Admin@123"),
            is_active=True,
            is_verified=True
        )
        admin_user.roles.append(role_objs["super_admin"])
        db.add(admin_user)
        db.flush()
        db.add(UserProfile(user_id=admin_user.id, city_id=hyd_city.id, preferred_language="English", bio="Go Beyond Platform Admin"))

        # 2. Customer
        customer_user = User(
            email="customer@gobeyond.com",
            phone="9876543210",
            full_name="Aarav Sharma",
            hashed_password=get_password_hash("Customer@123"),
            is_active=True,
            is_verified=True
        )
        customer_user.roles.append(role_objs["customer"])
        db.add(customer_user)
        db.flush()
        db.add(UserProfile(user_id=customer_user.id, city_id=hyd_city.id, locality_id=locality_objs["jubilee-hills"].id, preferred_language="English", bio="Movie buff and foodie in Hyderabad"))

        # 3. Cinema Partner
        cinema_partner_user = User(
            email="cinema.partner@gobeyond.com",
            phone="9000000002",
            full_name="Mahesh Cinema Ops",
            hashed_password=get_password_hash("Partner@123"),
            is_active=True,
            is_verified=True
        )
        cinema_partner_user.roles.append(role_objs["partner_cinema"])
        db.add(cinema_partner_user)
        db.flush()
        cinema_partner = Partner(
            user_id=cinema_partner_user.id,
            business_name="AMB Cinemas & Multiplexes LLP",
            partner_type="CINEMA",
            contact_email="amb.operations@gobeyond.com",
            contact_phone="9000000002",
            gstin="36AAAAA0000A1Z5",
            pan_number="ABCDE1234F",
            status="APPROVED",
            verified_at=datetime.datetime.now(datetime.timezone.utc),
            verified_by=admin_user.id
        )
        db.add(cinema_partner)
        db.flush()

        # 4. Restaurant Partner
        rest_partner_user = User(
            email="restaurant.partner@gobeyond.com",
            phone="9000000003",
            full_name="Sanjay Hospitality",
            hashed_password=get_password_hash("Partner@123"),
            is_active=True,
            is_verified=True
        )
        rest_partner_user.roles.append(role_objs["partner_restaurant"])
        db.add(rest_partner_user)
        db.flush()
        rest_partner = Partner(
            user_id=rest_partner_user.id,
            business_name="Culinary Heritage Brands Pvt Ltd",
            partner_type="RESTAURANT",
            contact_email="dining.ops@gobeyond.com",
            contact_phone="9000000003",
            gstin="36BBBBB0000B1Z6",
            pan_number="BCDEF2345G",
            status="APPROVED",
            verified_at=datetime.datetime.now(datetime.timezone.utc),
            verified_by=admin_user.id
        )
        db.add(rest_partner)
        db.flush()

        # 5. Event Partner
        event_partner_user = User(
            email="event.partner@gobeyond.com",
            phone="9000000004",
            full_name="Kiran Live Events",
            hashed_password=get_password_hash("Partner@123"),
            is_active=True,
            is_verified=True
        )
        event_partner_user.roles.append(role_objs["partner_event"])
        db.add(event_partner_user)
        db.flush()
        event_partner = Partner(
            user_id=event_partner_user.id,
            business_name="LiveBeat Entertainments India",
            partner_type="EVENT",
            contact_email="events.india@gobeyond.com",
            contact_phone="9000000004",
            gstin="36CCCCC0000C1Z7",
            pan_number="CDEFG3456H",
            status="APPROVED",
            verified_at=datetime.datetime.now(datetime.timezone.utc),
            verified_by=admin_user.id
        )
        db.add(event_partner)
        db.flush()

        # 6. Sports Partner
        sports_partner_user = User(
            email="sports.partner@gobeyond.com",
            phone="9000000005",
            full_name="Vikram Turf Sports",
            hashed_password=get_password_hash("Partner@123"),
            is_active=True,
            is_verified=True
        )
        sports_partner_user.roles.append(role_objs["partner_sports"])
        db.add(sports_partner_user)
        db.flush()
        sports_partner = Partner(
            user_id=sports_partner_user.id,
            business_name="Apex Arenas & Sports Complex",
            partner_type="SPORTS",
            contact_email="sports.apex@gobeyond.com",
            contact_phone="9000000005",
            gstin="36DDDDD0000D1Z8",
            pan_number="DEFGH4567I",
            status="APPROVED",
            verified_at=datetime.datetime.now(datetime.timezone.utc),
            verified_by=admin_user.id
        )
        db.add(sports_partner)
        db.flush()

        print("Seeding Cinemas, Screens & Seats...")
        cinema_1 = Cinema(
            partner_id=cinema_partner.id,
            location_id=locality_objs["gachibowli"].id,
            name="AMB Cinemas: Gachibowli",
            address="Sarath City Capital Mall, Gachibowli - Miyapur Rd, Whitefields, Kondapur, Hyderabad",
            city="Hyderabad",
            latitude=17.4580,
            longitude=78.3620,
            amenities=["Dolby Atmos", "Laser 4K Projection", "Platinum Recliner Lounge", "M-Ticket FastTrack", "Valet Parking"],
            is_active=True
        )
        cinema_2 = Cinema(
            partner_id=cinema_partner.id,
            location_id=locality_objs["kukatpally"].id,
            name="PVR Inox: Nexus Mall, Kukatpally",
            address="Nexus Hyderabad Mall, Kukatpally Housing Board Colony, Hyderabad",
            city="Hyderabad",
            latitude=17.4930,
            longitude=78.3910,
            amenities=["IMAX with Laser", "4DX", "Dolby Atmos", "Gourmet Food", "Wheelchair Accessible"],
            is_active=True
        )
        db.add_all([cinema_1, cinema_2])
        db.flush()

        # Screens & Seats for AMB Cinemas
        screen_1 = Screen(cinema_id=cinema_1.id, name="Screen 1 (Laser 4K Atmos)", screen_type="2D", total_seats=48)
        screen_2 = Screen(cinema_id=cinema_1.id, name="Screen 2 (VIP Recliners)", screen_type="2D", total_seats=24)
        db.add_all([screen_1, screen_2])
        db.flush()

        # Populate layout for screen_1: Rows A to D (12 seats per row)
        for r_idx, r_code in enumerate(["A", "B", "C", "D"]):
            tier = "RECLINER" if r_code == "A" else ("PREMIUM" if r_code in ["B", "C"] else "CLASSIC")
            base_p = 450.0 if tier == "RECLINER" else (300.0 if tier == "PREMIUM" else 200.0)
            for s_num in range(1, 13):
                s = Seat(screen_id=screen_1.id, row_code=r_code, seat_number=s_num, tier=tier, base_price=base_p)
                db.add(s)

        # Movies
        today = datetime.date.today()
        m1 = Movie(
            title="Devara: Part 1",
            slug="devara-part-1",
            description="A fearless warrior from a coastal community embarks on an epic journey to protect his people from ruthless power-hungry syndicates.",
            duration_minutes=178,
            language="Telugu",
            genre="Action / Drama / Epic",
            censor_rating="UA",
            release_date=today - datetime.timedelta(days=10),
            poster_url="/images/seed/movie-devara.jpg",
            backdrop_url="https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=1200&auto=format&fit=crop&q=80",
            trailer_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            rating=4.7,
            vote_count=18450,
            is_active=True
        )
        m2 = Movie(
            title="Dune: Part Two",
            slug="dune-part-two",
            description="Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.",
            duration_minutes=166,
            language="English",
            genre="Sci-Fi / Adventure",
            censor_rating="UA",
            release_date=today - datetime.timedelta(days=20),
            poster_url="/images/seed/movie-dune.jpg",
            backdrop_url="https://images.unsplash.com/photo-1509198397868-475647b2a1e5?w=1200&auto=format&fit=crop&q=80",
            trailer_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            rating=4.9,
            vote_count=24100,
            is_active=True
        )
        m3 = Movie(
            title="Pushpa 2: The Rule",
            slug="pushpa-2-the-rule",
            description="The explosive saga continues as Pushpa Raj expands his red sandalwood empire while clashing with SP Bhanwar Singh Shekhawat.",
            duration_minutes=185,
            language="Telugu",
            genre="Action / Crime / Thriller",
            censor_rating="A",
            release_date=today + datetime.timedelta(days=5),
            poster_url="/images/seed/movie-pushpa.jpg",
            backdrop_url="https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?w=1200&auto=format&fit=crop&q=80",
            trailer_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            rating=4.8,
            vote_count=31200,
            is_active=True
        )
        db.add_all([m1, m2, m3])
        db.flush()

        # Shows for today and tomorrow
        show1 = MovieShow(
            movie_id=m1.id,
            screen_id=screen_1.id,
            show_date=today,
            start_time=datetime.time(14, 30),
            end_time=datetime.time(17, 30),
            price_multiplier=1.0,
            status="SCHEDULED"
        )
        show2 = MovieShow(
            movie_id=m1.id,
            screen_id=screen_1.id,
            show_date=today,
            start_time=datetime.time(18, 45),
            end_time=datetime.time(21, 45),
            price_multiplier=1.1,
            status="SCHEDULED"
        )
        show3 = MovieShow(
            movie_id=m2.id,
            screen_id=screen_1.id,
            show_date=today,
            start_time=datetime.time(22, 15),
            end_time=datetime.time(1, 0),
            price_multiplier=1.0,
            status="SCHEDULED"
        )
        show4 = MovieShow(
            movie_id=m3.id,
            screen_id=screen_1.id,
            show_date=today,
            start_time=datetime.time(10, 30),
            end_time=datetime.time(13, 30),
            price_multiplier=1.2,
            status="SCHEDULED"
        )
        db.add_all([show1, show2, show3, show4])

        print("Seeding Restaurants, Menus & Tables...")
        r1 = Restaurant(
            partner_id=rest_partner.id,
            location_id=locality_objs["banjara-hills"].id,
            name="Paradise Heritage Biryani",
            slug="paradise-heritage-banjara-hills",
            cuisines=["Hyderabadi", "Dum Biryani", "Mughlai", "Kebabs"],
            cost_for_two=900,
            address="Road No. 3, Banjara Hills, Hyderabad",
            phone="+91 40 6677 8899",
            timings="11:30 AM - 11:30 PM",
            images=[
                "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=800&auto=format&fit=crop&q=80",
                "https://images.unsplash.com/photo-1589302168068-964664d93dc0?w=800&auto=format&fit=crop&q=80"
            ],
            rating=4.5,
            review_count=3420,
            has_buffet=False,
            has_alcohol=False,
            is_pure_veg=False,
            is_active=True
        )
        r2 = Restaurant(
            partner_id=rest_partner.id,
            location_id=locality_objs["jubilee-hills"].id,
            name="Farzi Modern Cafe & Brewery",
            slug="farzi-modern-cafe-jubilee-hills",
            cuisines=["Modern Indian", "Molecular Gastronomy", "Global Fusion", "Cocktails"],
            cost_for_two=2400,
            address="Road No. 36, Jubilee Hills, Hyderabad",
            phone="+91 40 7788 9900",
            timings="12:00 PM - 12:00 AM",
            images=[
                "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&auto=format&fit=crop&q=80",
                "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800&auto=format&fit=crop&q=80"
            ],
            rating=4.7,
            review_count=1920,
            has_buffet=False,
            has_alcohol=True,
            is_pure_veg=False,
            is_active=True
        )
        r3 = Restaurant(
            partner_id=rest_partner.id,
            location_id=locality_objs["hitec-city"].id,
            name="Roast: The Caffeine Capital",
            slug="roast-the-caffeine-capital-hitec-city",
            cuisines=["Artisanal Coffee", "Continental", "Gourmet Bakery", "European"],
            cost_for_two=1200,
            address="Near Mindspace Circle, Hitec City, Hyderabad",
            phone="+91 40 8899 0011",
            timings="8:00 AM - 11:00 PM",
            images=[
                "https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=800&auto=format&fit=crop&q=80"
            ],
            rating=4.6,
            review_count=840,
            has_buffet=False,
            has_alcohol=False,
            is_pure_veg=False,
            is_active=True
        )
        db.add_all([r1, r2, r3])
        db.flush()

        # Menus for Paradise
        db.add_all([
            RestaurantMenu(restaurant_id=r1.id, category="Biryani", item_name="Special Mutton Dum Biryani", description="Slow-cooked tender goat meat with long-grain aromatic Basmati rice, saffron, and traditional spices.", price=480.0, is_veg=False, is_bestseller=True),
            RestaurantMenu(restaurant_id=r1.id, category="Biryani", item_name="Nizami Chicken Dum Biryani", description="Fragrant basmati rice cooked with marinated chicken pieces and royal Awadhi spices.", price=390.0, is_veg=False, is_bestseller=True),
            RestaurantMenu(restaurant_id=r1.id, category="Starters", item_name="Apollo Fish Hyderabad Style", description="Spicy boneless fish fillet tossed in curry leaves, yogurt, and green chillies.", price=440.0, is_veg=False, is_bestseller=True),
            RestaurantMenu(restaurant_id=r1.id, category="Desserts", item_name="Double Ka Meetha with Rabri", description="Traditional Hyderabadi fried bread pudding soaked in saffron milk and dry fruits.", price=180.0, is_veg=True, is_bestseller=False),
            # Farzi Cafe menus
            RestaurantMenu(restaurant_id=r2.id, category="Fusion Starters", item_name="Dal Chawal Arancini", description="Wild mushroom & lentil risotto spheres with tomato chutney.", price=380.0, is_veg=True, is_bestseller=True),
            RestaurantMenu(restaurant_id=r2.id, category="Mains", item_name="Smoked Butter Chicken Pav", description="Pulled tandoori chicken simmered in rich makhani gravy.", price=520.0, is_veg=False, is_bestseller=True),
            # Roast menus
            RestaurantMenu(restaurant_id=r3.id, category="Coffee", item_name="Cortado with Single-Origin Beans", description="Double shot espresso cut with equal amount of warm silky milk.", price=260.0, is_veg=True, is_bestseller=True),
            RestaurantMenu(restaurant_id=r3.id, category="Bakery", item_name="Almond Frangipane Croissant", description="Flaky butter croissant filled with almond frangipane paste.", price=290.0, is_veg=True, is_bestseller=True),
        ])

        # Tables for Paradise
        for t_no in range(1, 9):
            zone = "Indoor AC" if t_no <= 4 else ("Outdoor Terrace" if t_no <= 6 else "Royal Family Cabana")
            cap = 2 if t_no % 3 == 0 else (4 if t_no % 2 == 0 else 6)
            db.add(DiningTable(restaurant_id=r1.id, table_number=f"T-{t_no}", capacity=cap, zone=zone, is_active=True))

        for t_no in range(1, 7):
            zone = "Rooftop Lounge" if t_no <= 3 else "Indoor Bar Area"
            cap = 4 if t_no <= 4 else 8
            db.add(DiningTable(restaurant_id=r2.id, table_number=f"FZ-{t_no}", capacity=cap, zone=zone, is_active=True))

        print("Seeding Events & Ticket Tiers...")
        ev1 = Event(
            partner_id=event_partner.id,
            location_id=locality_objs["gachibowli"].id,
            title="Sunburn Arena featuring Alan Walker — Hyderabad",
            slug="sunburn-arena-alan-walker-hyderabad",
            category="CONCERT",
            description="The global EDM sensation Alan Walker returns to Hyderabad with the iconic WalkerWorld Tour! Expect cutting-edge stage visuals, laser choreographies, and greatest festival anthems.",
            artist_names="Alan Walker, Support Acts",
            venue_name="GMR Arena, Rajiv Gandhi International Airport Ground",
            venue_address="Near Shamshabad, Hyderabad, Telangana",
            start_datetime=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=12, hours=4),
            end_datetime=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=12, hours=9),
            banner_url="https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=1200&auto=format&fit=crop&q=80",
            is_featured=True,
            is_active=True
        )
        ev2 = Event(
            partner_id=event_partner.id,
            location_id=locality_objs["hitec-city"].id,
            title="Zakir Khan Live: Tathastu International Tour",
            slug="zakir-khan-live-hyderabad",
            category="COMEDY",
            description="Sakht Launda Zakir Khan brings his blockbuster comedy special 'Tathastu' to Hyderabad for an unforgettable evening of raw, poignant, and laugh-out-loud storytelling.",
            artist_names="Zakir Khan",
            venue_name="Shilpakala Vedika Auditorium",
            venue_address="Hitec City, Madhapur, Hyderabad",
            start_datetime=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=6, hours=2),
            end_datetime=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=6, hours=5),
            banner_url="https://images.unsplash.com/photo-1585699324551-f6c309eedeca?w=1200&auto=format&fit=crop&q=80",
            is_featured=True,
            is_active=True
        )
        ev3 = Event(
            partner_id=event_partner.id,
            location_id=locality_objs["begumpet"].id,
            title="Hyderabad Sufi & Qawwali Night by the Lake",
            slug="hyderabad-sufi-qawwali-night",
            category="CULTURAL",
            description="An ethereal evening celebrating ancient mystic Sufi compositions, whirling melodies, and classical harmonium improvisations under the starry Hyderabad sky.",
            artist_names="Nizami Brothers & Ensemble",
            venue_name="The Waterfront Promenade",
            venue_address="Necklace Road, Begumpet, Hyderabad",
            start_datetime=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=8, hours=3),
            end_datetime=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=8, hours=7),
            banner_url="https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=1200&auto=format&fit=crop&q=80",
            is_featured=False,
            is_active=True
        )
        db.add_all([ev1, ev2, ev3])
        db.flush()

        # Ticket tiers for Sunburn
        db.add_all([
            EventTicketType(event_id=ev1.id, name="Early Bird GA", description="General Admission entry to the main dance arena", price=1499.0, total_quantity=500, available_quantity=480, max_per_booking=6),
            EventTicketType(event_id=ev1.id, name="VIP Front Stage", description="Elevated front stage viewing deck with dedicated bars and express entry", price=2999.0, total_quantity=200, available_quantity=190, max_per_booking=6),
            EventTicketType(event_id=ev1.id, name="Platinum Lounge Table Pass", description="Exclusive hospitality cabana with unlimited hors d'oeuvres & premium beverage service", price=8999.0, total_quantity=50, available_quantity=45, max_per_booking=4),
        ])

        # Ticket tiers for Zakir Khan
        db.add_all([
            EventTicketType(event_id=ev2.id, name="Silver Seating", description="Balcony seating with clear stage view", price=799.0, total_quantity=300, available_quantity=295, max_per_booking=4),
            EventTicketType(event_id=ev2.id, name="Gold Middle Stalls", description="Central auditorium seating close to the stage", price=1499.0, total_quantity=250, available_quantity=240, max_per_booking=4),
            EventTicketType(event_id=ev2.id, name="Diamond Front Rows", description="First 5 rows with meet & greet opportunity", price=2499.0, total_quantity=50, available_quantity=48, max_per_booking=2),
        ])

        print("Seeding Sports Venues & Recreational Activities...")
        venue1 = SportsVenue(
            partner_id=sports_partner.id,
            location_id=locality_objs["hitec-city"].id,
            name="Gamepoint Arena: Hitec City",
            sport_types=["Badminton", "Box Cricket", "Pickleball", "Table Tennis"],
            address="Behind Cyber Towers, Hitec City, Hyderabad",
            amenities=["BWF Approved Synthetic Courts", "Day/Night LED Floodlights", "Showers & Lockers", "Pro Shop", "Physiotherapy Room"],
            images=["https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?w=800&auto=format&fit=crop&q=80"],
            rating=4.8,
            is_active=True
        )
        venue2 = SportsVenue(
            partner_id=sports_partner.id,
            location_id=locality_objs["kondapur"].id,
            name="Apex Turf Arena: Kondapur",
            sport_types=["Football 5-a-side", "Box Cricket Turf", "Volleyball"],
            address="RTO Road, Near Botanical Gardens, Kondapur, Hyderabad",
            amenities=["FIFA 2-Star Astroturf", "Floodlights", "Bleacher Seating", "Refreshment Kiosk"],
            images=["/images/seed/sports-turf.jpg"],
            rating=4.7,
            is_active=True
        )
        db.add_all([venue1, venue2])
        db.flush()

        act1 = Activity(
            partner_id=sports_partner.id,
            location_id=locality_objs["hitec-city"].id,
            venue_id=venue1.id,
            title="BWF Synthetic Badminton Court (1 Hour)",
            slug="bwf-synthetic-badminton-court-gamepoint",
            category="SPORTS",
            description="Book high-performance BWF approved 8-layer synthetic badminton courts with professional shock absorption and shadowless glare-free LED lighting.",
            base_price=450.0,
            duration_minutes=60,
            image_url="https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?w=800&auto=format&fit=crop&q=80",
            min_age=6,
            is_active=True
        )
        act2 = Activity(
            partner_id=sports_partner.id,
            location_id=locality_objs["kondapur"].id,
            venue_id=venue2.id,
            title="Floodlit 5-a-Side Astroturf Football (1 Hour)",
            slug="floodlit-astroturf-football-apex",
            category="SPORTS",
            description="High-speed synthetic turf ideal for competitive 5-a-side football matches and box cricket tournaments with boundary nets and match timers.",
            base_price=1200.0,
            duration_minutes=60,
            image_url="/images/seed/sports-turf.jpg",
            min_age=8,
            is_active=True
        )
        act3 = Activity(
            partner_id=sports_partner.id,
            location_id=locality_objs["madhapur"].id,
            title="Pitstop High-Speed Go-Karting & Simulator",
            slug="pitstop-high-speed-go-karting-madhapur",
            category="ADVENTURE",
            description="Experience heart-pounding acceleration on a 650m asphalt race track with SODIKART 270cc engine karts and professional computerized lap timing.",
            base_price=699.0,
            duration_minutes=30,
            image_url="/images/seed/activity-gokart.jpg",
            min_age=12,
            is_active=True
        )
        act4 = Activity(
            partner_id=sports_partner.id,
            location_id=locality_objs["gachibowli"].id,
            title="Mystery Rooms: The Insidious Haunted Mansion Escape",
            slug="mystery-rooms-haunted-mansion-gachibowli",
            category="GAMING_ZONE",
            description="A real-life adrenaline adventure where you are locked in a cryptic chamber. Solve riddles, crack secret codes, and escape within 60 minutes!",
            base_price=800.0,
            duration_minutes=60,
            image_url="https://images.unsplash.com/photo-1511512578047-dfb367046420?w=800&auto=format&fit=crop&q=80",
            min_age=10,
            is_active=True
        )
        db.add_all([act1, act2, act3, act4])
        db.flush()

        # Slots for badminton for today
        for hour in [6, 7, 8, 17, 18, 19, 20]:
            db.add(ActivitySlot(
                activity_id=act1.id,
                slot_date=today,
                start_time=datetime.time(hour, 0),
                end_time=datetime.time(hour + 1, 0),
                capacity=4,
                booked_count=0,
                price_override=None,
                is_available=True
            ))

        # Slots for football turf
        for hour in [18, 19, 20, 21, 22]:
            db.add(ActivitySlot(
                activity_id=act2.id,
                slot_date=today,
                start_time=datetime.time(hour, 0),
                end_time=datetime.time(hour + 1, 0),
                capacity=1,
                booked_count=0,
                price_override=None,
                is_available=True
            ))

        # Slots for go-karting (act3)
        for hour in [11, 14, 17, 19, 21]:
            db.add(ActivitySlot(
                activity_id=act3.id,
                slot_date=today,
                start_time=datetime.time(hour, 0),
                end_time=datetime.time(hour + 1, 0),
                capacity=8,
                booked_count=0,
                price_override=None,
                is_available=True
            ))

        # Slots for escape room (act4)
        for hour in [12, 15, 18, 20]:
            db.add(ActivitySlot(
                activity_id=act4.id,
                slot_date=today,
                start_time=datetime.time(hour, 0),
                end_time=datetime.time(hour + 1, 0),
                capacity=6,
                booked_count=0,
                price_override=None,
                is_available=True
            ))

        print("Seeding Promotional Coupons...")
        db.add_all([
            Coupon(
                code="BEYOND50",
                description="Flat 50% discount up to ₹150 on your bookings",
                discount_type="PERCENTAGE",
                discount_value=50.0,
                min_order_value=250.0,
                max_discount=150.0,
                valid_from=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
                valid_until=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=90),
                usage_limit=10000,
                used_count=0,
                is_active=True
            ),
            Coupon(
                code="WELCOME100",
                description="Flat ₹100 instant cash discount on first booking",
                discount_type="FLAT",
                discount_value=100.0,
                min_order_value=300.0,
                max_discount=100.0,
                valid_from=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
                valid_until=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=180),
                usage_limit=50000,
                used_count=0,
                is_active=True
            ),
            Coupon(
                code="HYDEXPLORE",
                description="20% off up to ₹300 across all Hyderabad events and dining",
                discount_type="PERCENTAGE",
                discount_value=20.0,
                min_order_value=500.0,
                max_discount=300.0,
                valid_from=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1),
                valid_until=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=60),
                usage_limit=25000,
                used_count=0,
                is_active=True
            ),
        ])

        db.commit()
        print("SEEDING COMPLETED SUCCESSFULLY!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
