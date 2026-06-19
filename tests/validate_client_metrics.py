"""Seed client data and validate the KPI aggregation pipeline."""
import sys, json, random
sys.path.insert(0, '.')
from database import SessionLocal, init_db
from models import IntegrationClient, Facility, Vehicle, Objective, DriverProfile, Recommendation, SimEvent, ClientSimulation, Shipment
from routes.client_dashboard import _compute_client_metrics
from sqlalchemy import func, select
from datetime import datetime, timedelta

random.seed(42)
init_db()
session = SessionLocal()

# Find or create client
client = session.query(IntegrationClient).filter(IntegrationClient.id == 1).first()
if not client:
    client = IntegrationClient(id=1, name='Demo Client', company_name='Demo Logistics', firebase_uid=None)
    session.add(client)
    session.flush()

cid = client.id
now = datetime.utcnow()

# Clean existing client data
session.query(Recommendation).filter(Recommendation.vehicle_id.in_(
    select(Vehicle.id).where(Vehicle.client_id == cid)
)).delete(synchronize_session='fetch')
session.query(SimEvent).filter(SimEvent.client_id == cid).delete()
session.query(Shipment).filter(Shipment.client_id == cid).delete()
session.query(Objective).filter(Objective.client_id == cid).delete()
session.query(Vehicle).filter(Vehicle.client_id == cid).delete()
session.query(DriverProfile).filter(DriverProfile.client_id == cid).delete()
session.query(Facility).filter(Facility.client_id == cid).delete()
session.query(ClientSimulation).filter(ClientSimulation.client_id == cid).delete()
session.flush()

# Create facilities
facilities = []
for name, city, ftype, lat, lon, cap, inv in [
    ('Mumbai Hub', 'Mumbai', 'warehouse', 19.0760, 72.8777, 500, 320),
    ('Chennai Port', 'Chennai', 'port', 13.0827, 80.2707, 400, 150),
    ('Delhi DC', 'Delhi', 'warehouse', 28.7041, 77.1025, 600, 480),
    ('Kolkata DC', 'Kolkata', 'warehouse', 22.5726, 88.3639, 300, 210),
]:
    f = Facility(name=name, city=city, facility_type=ftype, latitude=lat, longitude=lon,
                 base_capacity_units=cap, current_inventory_units=inv,
                 initial_inventory_units=cap, client_id=cid)
    session.add(f)
    facilities.append(f)
session.flush()

# Create drivers
drivers = []
for name, bias, conf in [
    ('Raj Kumar', 0.8, 0.7),
    ('Priya Sharma', 0.6, 0.5),
    ('Amit Singh', 0.9, 0.8),
]:
    d = DriverProfile(name=name,
                      accept_recommendation_bias=bias, confidence=conf,
                      override_rating=0.5, client_id=cid)
    session.add(d)
    drivers.append(d)
session.flush()

# Create vehicles
vehicles = []
for i, (ident, vtype, status, home_fid, driver_idx) in enumerate([
    ('MH-01-AB-1234', 'truck', 'in_transit', facilities[0].id, 0),
    ('TN-01-CD-5678', 'truck', 'in_transit', facilities[1].id, 1),
    ('DL-01-EF-9012', 'truck', 'waiting', facilities[2].id, 2),
    ('WB-01-GH-3456', 'truck', 'in_transit', facilities[3].id, 0),
]):
    v = Vehicle(identifier=ident, vehicle_type=vtype, status=status,
                payload_capacity_units=100, home_facility_id=home_fid,
                current_facility_id=home_fid, average_speed_kmph=55.0, client_id=cid,
                driver_profile_id=drivers[driver_idx].id,
                default_objective_id=None)
    session.add(v)
    vehicles.append(v)
session.flush()

# Create objectives
objectives = []
for name, commodity, origin_fid, dest_fid, sla, priority in [
    ('Rice Supply', 'rice', facilities[0].id, facilities[2].id, 2160, 1),
    ('Medicine Delivery', 'medicine', facilities[1].id, facilities[3].id, 1440, 3),
    ('Wheat Distribution', 'wheat', facilities[2].id, facilities[1].id, 2880, 2),
    ('Perishable Goods', 'dairy', facilities[0].id, facilities[3].id, 720, 3),
]:
    o = Objective(name=name, commodity=commodity, origin_facility_id=origin_fid,
                  destination_facility_id=dest_fid, dispatch_interval_minutes=480,
                  sla_minutes=sla, priority=priority,
                  assigned_vehicle_ids=[vehicles[i].id], client_id=cid)
    session.add(o)
    objectives.append(o)
session.flush()

# Create recommendations with real costs
actions = ['continue', 'reroute_warehouse', 'reroute_port', 'wait', 'defer_dispatch']
statuses = ['accepted', 'accepted', 'accepted', 'accepted', 'ignored', 'ignored', 'suggested']
cities = ['Chennai', 'Mumbai', 'Delhi', 'Kolkata']
risk_types = ['port', 'weather', 'demand', 'route']
recs = []
for i in range(15):
    action = random.choice(actions)
    status = random.choice(statuses)
    baseline = round(random.uniform(800, 2500), 2)
    recommended = round(random.uniform(500, baseline - 50), 2) if action != 'continue' else baseline
    impact = round(baseline - recommended, 2)
    score = {
        'overload_penalty': round(random.uniform(0, 50), 2),
        'travel_cost': round(random.uniform(300, 800), 2),
        'added_travel_minutes': random.randint(0, 180),
        'baseline_duration_minutes': random.randint(720, 4320),
        'ai_confidence': round(random.uniform(0.7, 0.95), 2),
    }
    r = Recommendation(
        simulation_time=now - timedelta(hours=random.randint(0, 48)),
        vehicle_id=random.choice(vehicles).id,
        objective_id=random.choice(objectives).id,
        current_facility_id=random.choice(facilities).id,
        original_destination_id=random.choice(facilities).id,
        recommended_destination_id=random.choice(facilities).id,
        action=action,
        explanation=f"AI evaluated {random.choice(risk_types)} risk at {random.choice(cities)}",
        structured_explanation={"insights": ["Risk avoided", "Cost optimized"],
                               "impact": ["Reduced transit time"]},
        counterfactual="Without intervention, delay would have been 8-12 hours.",
        score_breakdown=score,
        baseline_cost=baseline,
        recommended_cost=recommended,
        financial_impact_usd=impact,
        status=status,
        confidence=round(random.uniform(0.70, 0.98), 2),
    )
    session.add(r)
    recs.append(r)
session.flush()

# Create SimEvents
event_types = ['dispatch', 'load_complete', 'arrive', 'unload_complete', 'rest_complete']
for i in range(25):
    e = SimEvent(
        scheduled_time=now - timedelta(hours=random.randint(0, 72)),
        processed_time=now - timedelta(hours=random.randint(0, 48)),
        event_type=random.choice(event_types),
        vehicle_id=random.choice(vehicles).id if random.random() > 0.2 else None,
        objective_id=random.choice(objectives).id if random.random() > 0.3 else None,
        facility_id=random.choice(facilities).id if random.random() > 0.3 else None,
        client_id=cid,
        payload={"leg": random.choice(['outbound', 'return']),
                 "impact_score": round(random.uniform(0, 1), 2)} if random.random() > 0.3 else {},
    )
    session.add(e)
session.commit()

print("=" * 60)
print("DATA SEEDED")
print("=" * 60)
print(f"Client: {client.company_name} (id={cid})")
print(f"Facilities: {len(facilities)}")
print(f"Vehicles: {len(vehicles)}")
print(f"Drivers: {len(drivers)}")
print(f"Objectives: {len(objectives)}")
print(f"Recommendations: {len(recs)}")

# === METRICS ===
metrics = _compute_client_metrics(cid, session)
print("\n" + "=" * 60)
print("COMPUTED CLIENT METRICS (from _compute_client_metrics)")
print("=" * 60)
for k, v in metrics.items():
    print(f"  {k}: {v}")

# === RECOMMENDATIONS ===
all_recs = session.query(Recommendation).filter(
    Recommendation.vehicle_id.in_(select(Vehicle.id).where(Vehicle.client_id == cid))
).all()
print("\n" + "=" * 60)
print(f"RECOMMENDATIONS (total: {len(all_recs)})")
print("=" * 60)
for r in all_recs:
    print(f"  Rec #{r.id:3d} | {r.action:<20s} | {r.status:<10s} | "
          f"baseline={r.baseline_cost:>8.2f} | recommended={r.recommended_cost:>8.2f} | "
          f"impact={r.financial_impact_usd:>8.2f} | conf={r.confidence:.0%}")

# === Show which recs contribute to financial_costs_saved
accepted = [r for r in all_recs if r.status == 'accepted']
print(f"\n  --- Accepted ({len(accepted)}): contributing to financial_costs_saved_usd ---")
total_saved = sum(max(0, r.financial_impact_usd or 0) for r in accepted)
for r in accepted:
    saved = max(0, r.financial_impact_usd or 0)
    print(f"  Rec #{r.id}: impact={saved:.2f}")
print(f"  TOTAL financial_costs_saved_usd = {total_saved:.2f}")

ignored = [r for r in all_recs if r.status == 'ignored']
print(f"\n  --- Ignored ({len(ignored)}): contributing to financial_costs_incurred_usd ---")
total_incurred = sum((r.recommended_cost or 0) for r in accepted) + sum((r.baseline_cost or 0) for r in ignored)
for r in ignored:
    print(f"  Rec #{r.id}: baseline_cost={r.baseline_cost:.2f}")
print(f"  TOTAL financial_costs_incurred_usd = {total_incurred:.2f}")

# === REROUTE COUNT ===
reroutes = [r for r in accepted if r.action and "reroute" in r.action.lower()]
print(f"\n  --- Reroute count from accepted -> {len(reroutes)} ---")
for r in reroutes:
    print(f"  Rec #{r.id}: action={r.action}")

# === EVENTS ===
events = session.query(SimEvent).filter(SimEvent.client_id == cid).order_by(
    SimEvent.processed_time.desc()).limit(20).all()
print("\n" + "=" * 60)
print(f"SIM EVENTS (showing last 20 of {session.query(func.count(SimEvent.id)).filter(SimEvent.client_id == cid).scalar()})")
print("=" * 60)
for e in events:
    payload_preview = str(e.payload)[:120] if e.payload else "{}"
    print(f"  Event #{e.id:3d} | {e.event_type:<18s} | time={e.processed_time} | "
          f"payload={payload_preview}")

# === ACTIVE TRUCKS ===
active = session.query(func.count(Vehicle.id)).filter(
    Vehicle.client_id == cid, Vehicle.status == 'in_transit'
).scalar()
print(f"\n  Active trucks (in_transit): {active}")

# Verification
print("\n" + "=" * 60)
print("VERIFICATION SUMMARY")
print("=" * 60)
nonzero = {k: v for k, v in metrics.items() if v > 0}
zero = {k: v for k, v in metrics.items() if v == 0}
print(f"\n  NON-ZERO KPIs ({len(nonzero)}):")
for k, v in nonzero.items():
    print(f"    {k}: {v}")
print(f"\n  ZERO KPIs ({len(zero)}):")
for k, v in zero.items():
    print(f"    {k}: {v} (expected — engine not running, only DB-derived available)")

session.close()
print("\nDone.")
