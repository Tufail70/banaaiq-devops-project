"""One-shot script: wipe all BOQ data from DB. Safe to re-run."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load .env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

from app import app, db
from models import BOQActual, BOQPackage, EngineerPackage, BOQ

with app.app_context():
    print(f"Before: BOQActual={BOQActual.query.count()}, BOQPackage={BOQPackage.query.count()}, EngineerPackage={EngineerPackage.query.count()}, BOQ={BOQ.query.count()}")
    BOQActual.query.delete()
    BOQPackage.query.delete()
    EngineerPackage.query.delete()
    BOQ.query.delete()
    db.session.commit()
    print(f"After:  BOQActual={BOQActual.query.count()}, BOQPackage={BOQPackage.query.count()}, EngineerPackage={EngineerPackage.query.count()}, BOQ={BOQ.query.count()}")
    print("Wipe complete.")
