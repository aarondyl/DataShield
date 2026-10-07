"""Exercise Product Twin writes against an Alembic-migrated database."""

from pathlib import Path
import sys

from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import engine
from app.models import Company, Product, ProductTwinVersion
from app.understanding.schemas import Fact
from app.understanding.twin import add_manual_fact, current_view


with Session(engine) as db:
    company = Company(name="Product Twin migration smoke test")
    db.add(company)
    db.flush()
    product = Product(company_id=company.id, name="Twin smoke product")
    db.add(product)
    db.commit()
    version = add_manual_fact(db, product.id, "features", Fact(name="login", status="PRESENT", confidence=1),
                              "Verified migration write")
    assert version.version_number == 1
    assert current_view(db, product.id)["facts"][0]["name"] == "login"
    assert db.get(ProductTwinVersion, version.id).product_id == product.id
