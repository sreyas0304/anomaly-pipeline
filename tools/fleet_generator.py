import json
import random
import time
import uuid
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError

# ==========================================
# CONFIGURATION
# ==========================================


STREAM_NAME = 'fleet-telemetry-stream'
AWS_REGION = 'us-east-1'
BATCH_SIZE = 25
SLEEP_SECONDS = 1
NUM_ITERATIONS = 1000

try:
    kinesis = boto3.client('kinesis', region_name=AWS_REGION)
    USE_KINESIS = True
    print(f"Connected to AWS Kinesis region: {AWS_REGION}")
except Exception as e:
    USE_KINESIS = False
    print("AWS credentials not found. Defaulting to console print output.")

# ==========================================
# VEHICLE CLASS
# ==========================================
class Vehicle:
    def __init__(self, vin, driver_id, fleet_group, lat, lon, anomaly_profile=None):
        self.vin = vin
        self.driver_id = driver_id
        self.fleet_group = fleet_group
        self.anomaly_profile = anomaly_profile  # 'overheat', 'blowout', 'reckless', 'timeout', 'fuel_drain', 'signal_loss', or None

        # Static Gateway Meta
        self.imei = str(random.randint(300000000000000, 399999999999999))
        self.firmware = "v4.2.1"
        self.odometer = random.uniform(50000, 200000)

        # Dynamic Telemetry State
        self.lat = lat
        self.lon = lon
        self.heading = random.randint(0, 359)
        self.speed_mph = random.uniform(55.0, 70.0)
        self.engine_rpm = int(self.speed_mph * 30)
        self.coolant_temp_c = random.uniform(85.0, 90.0)
        self.tires = {
            "steer_left": 105.0, "steer_right": 105.0,
            "drive_left_outer": 105.0, "drive_left_inner": 105.0,
            "drive_right_outer": 105.0, "drive_right_inner": 105.0
        }

        self.stopped = False
        self.active_dtcs = []
        self.signal_loss_iter = 0  # Used by signal_loss profile
        self.in_signal_blackout = False  # Tracks dark window for signal_loss

        # Fix: fuel_drain trucks start with low fuel so thresholds are hit within 1000 iterations
        if anomaly_profile == 'fuel_drain':
            self.fuel_level = random.uniform(20.0, 40.0)
        else:
            self.fuel_level = random.uniform(20.0, 100.0)

    def _get_gps_drift(self):
        """Returns lon/lat drift based on fleet region (simulates regional highway direction)."""
        region = self.fleet_group
        if "West-Coast" in region:
            return -0.0001, 0.00005   # Heading north-west
        elif "Pacific-Northwest" in region:
            return -0.00008, 0.0001   # Heading north
        elif "Southwest" in region:
            return 0.0001, -0.00005   # Heading east-south
        elif "Mountain" in region:
            return 0.00012, 0.00003   # Heading east
        elif "Midwest" in region:
            return 0.0001, 0.00002    # Heading east
        elif "Great-Plains" in region:
            return 0.00008, -0.00003  # Heading south-east
        elif "South-Central" in region:
            return 0.00015, 0.00001   # Heading east
        elif "Southeast" in region:
            return 0.0001, 0.00005    # Heading north-east
        elif "Mid-Atlantic" in region:
            return 0.00005, 0.0001    # Heading north
        elif "Northeast" in region:
            return 0.00003, 0.00012   # Heading north-north-east
        else:
            return -0.0001, 0.0       # Default westward

    def update_state(self):
        if self.stopped:
            return

        # 1. Normal State Drift
        self.speed_mph += random.uniform(-2.0, 2.0)
        self.speed_mph = max(0, min(self.speed_mph, 85.0))
        self.engine_rpm = int((self.speed_mph * 30) + random.uniform(-100, 100))
        self.coolant_temp_c += random.uniform(-0.5, 0.5)
        self.fuel_level -= 0.01
        self.odometer += (self.speed_mph / 3600)

        lon_drift, lat_drift = self._get_gps_drift()
        self.lon += lon_drift
        self.lat += lat_drift

        for tire in self.tires:
            self.tires[tire] += random.uniform(-0.2, 0.2)

        # 2. Anomaly Injection
        if self.anomaly_profile == 'reckless':
            if random.random() < 0.05:
                self.speed_mph = max(0, self.speed_mph - random.uniform(20, 40))
            # Fix: increased from 2% → 10% so lambda sees ~100 CRITICAL RPM events per run
            if random.random() < 0.10:
                self.engine_rpm = random.randint(7000, 8500)

        elif self.anomaly_profile == 'blowout':
            self.tires['drive_left_outer'] -= random.uniform(0.5, 2.0)
            # Fix: lambda has no tire pressure check — inject DTC when pressure is critically low
            if self.tires['drive_left_outer'] < 80.0 and "C0110" not in self.active_dtcs:
                self.active_dtcs.append("C0110")  # Tire Pressure Monitor System Fault

        elif self.anomaly_profile == 'overheat':
            self.coolant_temp_c += random.uniform(0.2, 1.5)
            if self.coolant_temp_c > 105.0 and "P0115" not in self.active_dtcs:
                self.active_dtcs.append("P0115")

        elif self.anomaly_profile == 'timeout':
            # Fix: spike RPM + add fault DTC before going permanently silent
            if random.random() < 0.01:
                self.engine_rpm = random.randint(7000, 9000)
                if "P0700" not in self.active_dtcs:
                    self.active_dtcs.append("P0700")  # Transmission Control System Malfunction
                self.stopped = True

        elif self.anomaly_profile == 'fuel_drain':
            # Abnormally fast fuel consumption — fuel sensor / leak anomaly
            self.fuel_level -= random.uniform(0.05, 0.2)
            if self.fuel_level < 10.0 and "P0087" not in self.active_dtcs:
                self.active_dtcs.append("P0087")  # Fuel System Pressure Too Low

        elif self.anomaly_profile == 'signal_loss':
            # Fix: track dark window in state; generate_payload() sends degraded-signal records
            # instead of None so lambda can detect CRITICAL cell signal during blackout
            self.signal_loss_iter += 1
            self.in_signal_blackout = (self.signal_loss_iter % 50) < 5

    def generate_payload(self):
        self.update_state()

        if self.stopped:
            return None

        # Fix: signal_loss trucks send CRITICAL-range cell signal during blackout windows
        # instead of returning None — lambda can now detect the outage
        # Fix: all other trucks use (-85, -60) so healthy trucks never cross WARN (-90)
        if self.anomaly_profile == 'signal_loss' and self.in_signal_blackout:
            cell_dbm = random.randint(-100, -98)  # CRITICAL range
        else:
            cell_dbm = random.randint(-85, -60)   # Safe range — no false positives

        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat()[:-6] + "Z",
            "gateway_meta": {
                "imei": self.imei,
                "cell_signal_dbm": cell_dbm,
                "firmware_version": self.firmware
            },
            "vehicle": {
                "vin": self.vin,
                "driver_id": self.driver_id,
                "fleet_group": self.fleet_group,
                "ignition_status": "ON",
                "odometer_miles": round(self.odometer, 1)
            },
            "telemetry": {
                "gps": {
                    "lat": round(self.lat, 4),
                    "lon": round(self.lon, 4),
                    "heading_degrees": self.heading,
                    "satellites_locked": random.randint(6, 12)
                },
                "speed_mph": round(self.speed_mph, 1),
                "engine_rpm": self.engine_rpm,
                "throttle_position_percent": round(max(0, (self.speed_mph / 85.0) * 100), 1),
                "brake_pedal_status": 1 if self.speed_mph < 40 else 0,
                "coolant_temp_c": round(self.coolant_temp_c, 1),
                "fuel_level_percent": round(self.fuel_level, 1),
                "tire_pressures_psi": {k: round(v, 1) for k, v in self.tires.items()},
                "active_dtc_codes": self.active_dtcs
            }
        }


# ==========================================
# FLEET DEFINITION  (25 trucks, 10 regions)
# ==========================================
#
# Region mapping:
#   West-Coast        → CA, OR corridors      (I-5 / US-101)
#   Pacific-Northwest → WA, northern OR       (I-5 North / US-2)
#   Southwest         → AZ, NV, NM            (I-10 / I-40)
#   Mountain          → CO, UT, ID, MT        (I-70 / I-15)
#   Midwest           → IL, OH, MI, MN        (I-90 / I-80)
#   Great-Plains      → KS, NE, ND, SD        (I-70 / US-83)
#   South-Central     → TX, OK, LA, AR        (I-10 / I-20)
#   Southeast         → FL, GA, SC, NC, TN    (I-75 / I-95)
#   Mid-Atlantic      → VA, MD, PA, NJ        (I-95 / I-81)
#   Northeast         → NY, CT, MA, NH, ME    (I-95 / I-90)
#
# Anomaly distribution (25 trucks):
#   None (healthy)   : 10  (40%)
#   reckless         :  4  (16%)
#   blowout          :  3  (12%)
#   overheat         :  3  (12%)
#   timeout          :  2  ( 8%)
#   fuel_drain       :  2  ( 8%)
#   signal_loss      :  1  ( 4%)
# ==========================================

def build_fleet():
    return [

        # ── WEST COAST (CA / OR — I-5 corridor) ──────────────────────────
        Vehicle("WC1TRUCK0000000001", "EMP-1001", "West-Coast", 37.3688, -122.0363, anomaly_profile=None),         # Oakland — Healthy
        Vehicle("WC1TRUCK0000000002", "EMP-1002", "West-Coast", 34.0522, -118.2437, anomaly_profile='reckless'),   # Los Angeles — Reckless
        Vehicle("WC1TRUCK0000000003", "EMP-1003", "West-Coast", 38.5816, -121.4944, anomaly_profile='overheat'),   # Sacramento — Overheat

        # ── PACIFIC NORTHWEST (WA / northern OR — I-5 North) ─────────────
        Vehicle("PN1TRUCK0000000004", "EMP-1004", "Pacific-Northwest", 47.6062, -122.3321, anomaly_profile=None),       # Seattle — Healthy
        Vehicle("PN1TRUCK0000000005", "EMP-1005", "Pacific-Northwest", 45.5051, -122.6750, anomaly_profile='blowout'),  # Portland — Blowout

        # ── SOUTHWEST (AZ / NV / NM — I-10 / I-40) ──────────────────────
        Vehicle("SW1TRUCK0000000006", "EMP-1006", "Southwest", 33.4484, -112.0740, anomaly_profile=None),          # Phoenix — Healthy
        Vehicle("SW1TRUCK0000000007", "EMP-1007", "Southwest", 36.1699, -115.1398, anomaly_profile='fuel_drain'),   # Las Vegas — Fuel Drain
        Vehicle("SW1TRUCK0000000008", "EMP-1008", "Southwest", 35.0844, -106.6504, anomaly_profile='reckless'),     # Albuquerque — Reckless

        # ── MOUNTAIN (CO / UT / ID / MT — I-70 / I-15) ──────────────────
        Vehicle("MT1TRUCK0000000009", "EMP-1009", "Mountain", 39.7392, -104.9903, anomaly_profile=None),           # Denver — Healthy
        Vehicle("MT1TRUCK0000000010", "EMP-1010", "Mountain", 40.7608, -111.8910, anomaly_profile='signal_loss'),  # Salt Lake City — Signal Loss
        Vehicle("MT1TRUCK0000000011", "EMP-1011", "Mountain", 43.6150, -116.2023, anomaly_profile='timeout'),      # Boise — Timeout

        # ── MIDWEST (IL / OH / MI / MN — I-90 / I-80) ───────────────────
        Vehicle("MW1TRUCK0000000012", "EMP-1012", "Midwest", 41.8781, -87.6298, anomaly_profile=None),             # Chicago — Healthy
        Vehicle("MW1TRUCK0000000013", "EMP-1013", "Midwest", 44.9778, -93.2650, anomaly_profile='blowout'),        # Minneapolis — Blowout
        Vehicle("MW1TRUCK0000000014", "EMP-1014", "Midwest", 41.4993, -81.6944, anomaly_profile='overheat'),       # Cleveland — Overheat

        # ── GREAT PLAINS (KS / NE / ND / SD — I-70 / US-83) ─────────────
        Vehicle("GP1TRUCK0000000015", "EMP-1015", "Great-Plains", 39.0997, -94.5786, anomaly_profile=None),        # Kansas City — Healthy
        Vehicle("GP1TRUCK0000000016", "EMP-1016", "Great-Plains", 41.2565, -95.9345, anomaly_profile='reckless'),  # Omaha — Reckless

        # ── SOUTH CENTRAL (TX / OK / LA / AR — I-10 / I-20) ─────────────
        Vehicle("SC1TRUCK0000000017", "EMP-1017", "South-Central", 29.7604, -95.3698, anomaly_profile=None),       # Houston — Healthy
        Vehicle("SC1TRUCK0000000018", "EMP-1018", "South-Central", 32.7767, -96.7970, anomaly_profile='fuel_drain'), # Dallas — Fuel Drain
        Vehicle("SC1TRUCK0000000019", "EMP-1019", "South-Central", 35.4676, -97.5164, anomaly_profile='reckless'), # Oklahoma City — Reckless

        # ── SOUTHEAST (FL / GA / SC / NC / TN — I-75 / I-95) ────────────
        Vehicle("SE1TRUCK0000000020", "EMP-1020", "Southeast", 33.7490, -84.3880, anomaly_profile=None),           # Atlanta — Healthy
        Vehicle("SE1TRUCK0000000021", "EMP-1021", "Southeast", 25.7617, -80.1918, anomaly_profile='blowout'),      # Miami — Blowout
        Vehicle("SE1TRUCK0000000022", "EMP-1022", "Southeast", 35.2271, -80.8431, anomaly_profile='timeout'),      # Charlotte — Timeout

        # ── MID-ATLANTIC (VA / MD / PA / NJ — I-95 / I-81) ──────────────
        Vehicle("MA1TRUCK0000000023", "EMP-1023", "Mid-Atlantic", 39.9526, -75.1652, anomaly_profile=None),        # Philadelphia — Healthy
        Vehicle("MA1TRUCK0000000024", "EMP-1024", "Mid-Atlantic", 38.9072, -77.0369, anomaly_profile='overheat'),  # Washington DC — Overheat

        # ── NORTHEAST (NY / CT / MA / NH / ME — I-95 / I-90) ────────────
        Vehicle("NE1TRUCK0000000025", "EMP-1025", "Northeast", 40.7128, -74.0060, anomaly_profile=None),           # New York — Healthy
    ]


# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("Initializing National Fleet Telemetry Generator...")
    print(f"Fleet size: 25 trucks | Regions: 10 | Iterations: {NUM_ITERATIONS}\n")

    fleet = build_fleet()

    # Print fleet summary at startup
    print(f"{'VIN':<22} {'Region':<20} {'Start Location':<22} {'Anomaly'}")
    print("-" * 85)
    location_labels = {
        "WC1TRUCK0000000001": "Oakland, CA",       "WC1TRUCK0000000002": "Los Angeles, CA",
        "WC1TRUCK0000000003": "Sacramento, CA",    "PN1TRUCK0000000004": "Seattle, WA",
        "PN1TRUCK0000000005": "Portland, OR",      "SW1TRUCK0000000006": "Phoenix, AZ",
        "SW1TRUCK0000000007": "Las Vegas, NV",     "SW1TRUCK0000000008": "Albuquerque, NM",
        "MT1TRUCK0000000009": "Denver, CO",        "MT1TRUCK0000000010": "Salt Lake City, UT",
        "MT1TRUCK0000000011": "Boise, ID",         "MW1TRUCK0000000012": "Chicago, IL",
        "MW1TRUCK0000000013": "Minneapolis, MN",   "MW1TRUCK0000000014": "Cleveland, OH",
        "GP1TRUCK0000000015": "Kansas City, KS",   "GP1TRUCK0000000016": "Omaha, NE",
        "SC1TRUCK0000000017": "Houston, TX",       "SC1TRUCK0000000018": "Dallas, TX",
        "SC1TRUCK0000000019": "Oklahoma City, OK", "SE1TRUCK0000000020": "Atlanta, GA",
        "SE1TRUCK0000000021": "Miami, FL",         "SE1TRUCK0000000022": "Charlotte, NC",
        "MA1TRUCK0000000023": "Philadelphia, PA",  "MA1TRUCK0000000024": "Washington, DC",
        "NE1TRUCK0000000025": "New York, NY",
    }
    for truck in fleet:
        anomaly = truck.anomaly_profile or "healthy"
        loc = location_labels.get(truck.vin, "Unknown")
        print(f"{truck.vin:<22} {truck.fleet_group:<20} {loc:<22} {anomaly}")

    print("\nStarting telemetry stream...\n")

    for iteration in range(NUM_ITERATIONS):
        records = []
        active_regions = set()

        for truck in fleet:
            payload = truck.generate_payload()
            if payload:
                records.append({
                    'Data': json.dumps(payload),
                    'PartitionKey': payload['vehicle']['vin']
                })
                active_regions.add(payload['vehicle']['fleet_group'])

        if not records:
            print("All vehicles have stopped. Ending simulation.")
            break

        if USE_KINESIS:
            try:
                response = kinesis.put_records(Records=records, StreamName=STREAM_NAME)
                failed = response.get('FailedRecordCount', 0)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Iter {iteration+1:04d} | "
                      f"Records: {len(records):2d}/25 | Regions active: {len(active_regions):2d}/10 | Failed: {failed}")
            except ClientError as e:
                print(f"Failed to send to Kinesis: {e}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Iter {iteration+1:04d} | "
                  f"Records: {len(records):2d}/25 | Regions active: {len(active_regions):2d}/10 (Console Mode)")
            if iteration == 0:
                # Print one full sample payload on first iteration
                print(json.dumps(json.loads(records[0]['Data']), indent=2))

        time.sleep(SLEEP_SECONDS)


if __name__ == '__main__':
    main()