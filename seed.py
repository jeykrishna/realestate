"""
Seed script — creates a default Super Admin account.
Run once after migrations:  python seed.py
"""
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.utils.id_gen import make_id


def seed():
    db = SessionLocal()
    try:
        if db.query(User).filter(User.role == UserRole.admin).first():
            print("Admin already exists — skipping seed.")
            return

        admin = User(
            id=make_id("usr"),
            name="Vigneshwar",
            email="vigneshwarsivalingam@gmail.com",
            phone="9876543210",
            role=UserRole.admin,
            property_ids=[],
        )
        db.add(admin)
        db.commit()
        print(f"Admin created: {admin.email}  (id: {admin.id})")
        print("Use POST /api/v1/auth/send-otp with this email to log in.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
