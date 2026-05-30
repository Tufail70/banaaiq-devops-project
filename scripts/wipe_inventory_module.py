"""Wipe all inventory rows (usage_logs, inventory_assignments, inventory_items)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from app import app, db
from models import UsageLog, InventoryAssignment, InventoryItem

with app.app_context():
    ul_before = UsageLog.query.count()
    ia_before = InventoryAssignment.query.count()
    ii_before = InventoryItem.query.count()
    print(f"Before: UsageLog={ul_before}, InventoryAssignment={ia_before}, InventoryItem={ii_before}")
    UsageLog.query.delete()
    InventoryAssignment.query.delete()
    InventoryItem.query.delete()
    db.session.commit()
    ul_after = UsageLog.query.count()
    ia_after = InventoryAssignment.query.count()
    ii_after = InventoryItem.query.count()
    print(f"After:  UsageLog={ul_after}, InventoryAssignment={ia_after}, InventoryItem={ii_after}")
    print("Done.")
