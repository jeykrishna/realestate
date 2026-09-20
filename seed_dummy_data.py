"""
Dummy data seeder for local development — creates sample properties, plots,
plot configs, and enquiries so the frontend has something to render.
Run after seed.py:  python seed_dummy_data.py
"""
import random

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.property import Property, PropertyCategory, PropertyStatus
from app.models.plot import Plot, PlotStatus
from app.models.plot_config import PlotConfig
from app.models.enquiry import Enquiry, EnquiryStatus
from app.utils.id_gen import make_id

PROPERTIES = [
    {
        "name": "VIP Paradise Phase 2",
        "city": "Madurai",
        "category": PropertyCategory.residential,
        "description": "Gated residential plots with wide roads, underground drainage, and 24x7 security near Madurai city limits.",
        "rows": 4,
        "cols": 6,
        "sqft": 1200,
        "price_per_sqft": 2500,
        "facing": "East",
    },
    {
        "name": "Green Acres Farmlands",
        "city": "Coimbatore",
        "category": PropertyCategory.agriculture,
        "description": "Fertile agricultural plots ideal for farming and weekend farmhouses, with borewell access and road frontage.",
        "rows": 3,
        "cols": 5,
        "sqft": 4000,
        "price_per_sqft": 400,
        "facing": "North",
    },
    {
        "name": "Trichy Business Hub",
        "city": "Tiruchirappalli",
        "category": PropertyCategory.commercial,
        "description": "Commercial plots on the main highway, perfect for showrooms, warehouses, and retail outlets.",
        "rows": 2,
        "cols": 4,
        "sqft": 2000,
        "price_per_sqft": 3500,
        "facing": "South",
    },
]

PLOT_STATUS_WEIGHTS = [
    (PlotStatus.available, 0.6),
    (PlotStatus.booked, 0.3),
    (PlotStatus.reserved, 0.1),
]


def weighted_status() -> PlotStatus:
    r = random.random()
    cumulative = 0.0
    for status, weight in PLOT_STATUS_WEIGHTS:
        cumulative += weight
        if r <= cumulative:
            return status
    return PlotStatus.available


def seed():
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.role == UserRole.admin).first()
        if not owner:
            print("No admin user found — run seed.py first.")
            return

        if db.query(Property).count() > 0:
            print("Properties already exist — skipping dummy data seed.")
            return

        for spec in PROPERTIES:
            prop_id = make_id("prop")
            rows, cols = spec["rows"], spec["cols"]
            total_plots = rows * cols

            prop = Property(
                id=prop_id,
                slug=spec["name"].lower().replace(" ", "-"),
                name=spec["name"],
                city=spec["city"],
                category=spec["category"],
                description=spec["description"],
                location={"lat": 9.9252 + random.uniform(-0.5, 0.5), "lng": 78.1198 + random.uniform(-0.5, 0.5)},
                hero_image="/static/uploads/land-plot-aerial.jpg",
                gallery=[
                    "/static/uploads/land-plot-aerial.jpg",
                    "/static/uploads/residential-plots.jpg",
                ],
                amenities=["Underground Drainage", "Street Lights", "Compound Wall", "24x7 Security"],
                price_range={"min": spec["sqft"] * spec["price_per_sqft"], "max": int(spec["sqft"] * spec["price_per_sqft"] * 1.4)},
                sqft_range={"min": spec["sqft"], "max": int(spec["sqft"] * 1.4)},
                total_plots=total_plots,
                available_plots=total_plots,
                status=PropertyStatus.active,
                owner_id=owner.id,
                plot_area_sqft=spec["sqft"],
                dimensions_label="30 X 40",
                boundary_wall=True,
                ownership_type="Freehold",
                transaction_type="Sale",
                construction_done=False,
                facing=spec["facing"],
                gated_community=spec["category"] == PropertyCategory.residential,
                corner_plot=False,
                price_per_sqft=spec["price_per_sqft"],
                starting_price=spec["sqft"] * spec["price_per_sqft"],
            )
            db.add(prop)

            config = PlotConfig(
                id=make_id("cfg"),
                property_id=prop_id,
                layout_type="grid",
                rows=rows,
                cols=cols,
                roads=[],
                labels={},
            )
            db.add(config)

            available_count = 0
            for r in range(rows):
                for c in range(cols):
                    status = weighted_status()
                    if status == PlotStatus.available:
                        available_count += 1
                    plot = Plot(
                        id=make_id("plt"),
                        property_id=prop_id,
                        plot_number=f"{spec['name'][:2].upper()}-{r * cols + c + 1:03d}",
                        sqft=spec["sqft"] + random.choice([-100, 0, 100, 200]),
                        dimensions={"width": 30, "height": 40},
                        facing=random.choice(["East", "West", "North", "South"]),
                        road_width=random.choice([20, 30, 40]),
                        price=spec["sqft"] * spec["price_per_sqft"] + random.randint(-50000, 200000),
                        status=status,
                        grid_row=r,
                        grid_col=c,
                        col_span=1,
                        row_span=1,
                    )
                    db.add(plot)

            prop.available_plots = available_count
            print(f"Created property: {prop.name} ({prop.city}) — {total_plots} plots, {available_count} available")

        db.flush()

        # A couple of sample enquiries against the first property
        first_prop_id = db.query(Property.id).first()[0]
        sample_enquiries = [
            {"name": "Ravi Kumar", "email": "ravi.kumar@example.com", "phone": "9123456780", "city": "Chennai", "message": "Interested in a corner plot, please share pricing."},
            {"name": "Priya Shankar", "email": "priya.shankar@example.com", "phone": "9123456781", "city": "Madurai", "message": "Can I visit the site this weekend?"},
        ]
        for e in sample_enquiries:
            db.add(Enquiry(
                id=make_id("enq"),
                property_id=first_prop_id,
                name=e["name"],
                email=e["email"],
                phone=e["phone"],
                city=e["city"],
                message=e["message"],
                status=EnquiryStatus.new,
            ))

        db.commit()
        print("Dummy data seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
