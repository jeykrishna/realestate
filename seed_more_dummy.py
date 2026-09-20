"""
Additional dummy properties — adds more sample listings beyond the initial
seed_dummy_data.py batch, for a fuller-looking admin properties list.
Run:  python seed_more_dummy.py
"""
import random

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.property import Property, PropertyCategory, PropertyStatus
from app.models.plot import Plot, PlotStatus
from app.models.plot_config import PlotConfig
from app.utils.id_gen import make_id

PROPERTIES = [
    {
        "name": "Marina Bay Commercial Complex",
        "city": "Chennai",
        "category": PropertyCategory.commercial,
        "description": "Prime commercial plots near OMR IT corridor, ideal for offices, showrooms, and retail chains.",
        "rows": 3,
        "cols": 4,
        "sqft": 1800,
        "price_per_sqft": 5200,
        "facing": "East",
    },
    {
        "name": "Silicon Valley Residency",
        "city": "Bangalore",
        "category": PropertyCategory.residential,
        "description": "Premium gated residential plots close to Electronic City, with clubhouse and landscaped gardens.",
        "rows": 5,
        "cols": 5,
        "sqft": 1500,
        "price_per_sqft": 6800,
        "facing": "North",
    },
    {
        "name": "Kaveri Organic Farms",
        "city": "Salem",
        "category": PropertyCategory.agriculture,
        "description": "Rich red-soil agricultural plots along the Kaveri basin, suited for organic farming and orchards.",
        "rows": 4,
        "cols": 4,
        "sqft": 5000,
        "price_per_sqft": 350,
        "facing": "South",
    },
    {
        "name": "HITEC City Residences",
        "city": "Hyderabad",
        "category": PropertyCategory.residential,
        "description": "Gated community plots minutes from HITEC City, with 40ft wide roads and underground utilities.",
        "rows": 4,
        "cols": 6,
        "sqft": 1350,
        "price_per_sqft": 4500,
        "facing": "West",
    },
    {
        "name": "Erode Textile Park Plots",
        "city": "Erode",
        "category": PropertyCategory.commercial,
        "description": "Industrial-commercial plots adjoining the textile export hub, ideal for warehousing and units.",
        "rows": 2,
        "cols": 5,
        "sqft": 3000,
        "price_per_sqft": 1800,
        "facing": "East",
    },
    {
        "name": "Vellore Green Estates",
        "city": "Vellore",
        "category": PropertyCategory.agriculture,
        "description": "Fertile farmland plots near Palar river basin, with borewell and year-round water access.",
        "rows": 3,
        "cols": 5,
        "sqft": 4500,
        "price_per_sqft": 300,
        "facing": "North",
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

        existing_names = {p.name for p in db.query(Property.name).all()}

        for spec in PROPERTIES:
            if spec["name"] in existing_names:
                print(f"Skipping (already exists): {spec['name']}")
                continue

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
                location={"lat": 9.9252 + random.uniform(-2, 2), "lng": 78.1198 + random.uniform(-2, 2)},
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

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
