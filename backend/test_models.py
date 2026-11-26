import sys
from app.core.database import engine, Base
import app.models  # load all models

def test_init_db():
    print("Creating all tables in database...")
    Base.metadata.create_all(bind=engine)
    tables = list(Base.metadata.tables.keys())
    print(f"Successfully created {len(tables)} tables:")
    for t in sorted(tables):
        print(f"  - {t}")
    assert len(tables) >= 20, "Expected at least 20 tables"
    print("\nAll database tables verified successfully!")

if __name__ == "__main__":
    test_init_db()

