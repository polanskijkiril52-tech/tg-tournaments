from passlib.context import CryptContext

from app.db import SessionLocal, Base, engine
from app.models import User, Tournament

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    user = db.query(User).filter(User.username == "admin").first()
    if not user:
        user = User(
            username="admin",
            password_hash=pwd.hash("admin123"),
            is_admin=True,
            telegram_id=None,
            first_name="Admin",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    tournament = db.query(Tournament).filter(User.username == "admin").first()
    if not db.query(Tournament).filter(Tournament.title == "Demo Cup").first():
        tournament = Tournament(
            title="Demo Cup",
            game="Dota 2",
            format="5v5",
            description="Тестовый турнир после восстановления базы",
            status="open",
            created_by_id=user.id,
        )
        db.add(tournament)
        db.commit()

    print("OK: seeded postgres")
finally:
    db.close()
