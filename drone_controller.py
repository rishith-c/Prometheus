# drone_controller.py
# thin wrapper around dronekit so the mission scripts stay readable.
# the pi runs this and talks to the matek flight controller over MAVLink.
#
# heads up, this arms and flies a real drone. test in SITL first, and do your
# first real runs with the PROPS OFF. it waits for a gps lock and for the FC to
# report armable before arming, so it won't just spin up blind.

import time
from dronekit import connect, VehicleMode, LocationGlobalRelative


class DroneController:
    def __init__(self, connection="/dev/ttyAMA0", baud=921600):
        print(f"connecting to {connection} ...")
        self.vehicle = connect(connection, wait_ready=True, baud=baud)
        print("connected")

    def wait_until_armable(self, timeout=60):
        # don't arm until the FC is happy (gps, ekf, prearm). give up if it never is.
        start = time.time()
        while not self.vehicle.is_armable:
            if time.time() - start > timeout:
                raise TimeoutError("never became armable, check gps / ekf / prearm messages")
            print("  waiting for vehicle to be armable ...")
            time.sleep(1)

    def arm(self):
        self.wait_until_armable()
        self.vehicle.mode = VehicleMode("GUIDED")
        self.vehicle.armed = True
        while not self.vehicle.armed:
            print("  arming ...")
            time.sleep(1)
        print("armed")

    def takeoff(self, target_alt):
        print(f"taking off to {target_alt} m")
        self.vehicle.simple_takeoff(target_alt)
        # hold here until we're basically at height, otherwise goto fires too early
        while True:
            alt = self.vehicle.location.global_relative_frame.alt
            print(f"  altitude {alt:.1f} m")
            if alt >= target_alt * 0.95:
                print("reached target altitude")
                break
            time.sleep(1)

    def goto(self, lat, lon, alt, wait=True, threshold=1.5):
        target = LocationGlobalRelative(lat, lon, alt)
        print(f"going to {lat}, {lon} at {alt} m")
        self.vehicle.simple_goto(target)
        if not wait:
            return
        # block until we're within threshold meters (or the mode changes on us)
        while self.vehicle.mode.name == "GUIDED":
            d = self._distance_m(target)
            print(f"  {d:.1f} m to waypoint")
            if d <= threshold:
                print("  reached waypoint")
                break
            time.sleep(1)

    def rtl(self):
        print("returning to launch")
        self.vehicle.mode = VehicleMode("RTL")

    def close(self):
        self.vehicle.close()
        print("connection closed")

    def _distance_m(self, target):
        # rough meters between where we are and the target. fine for short hops.
        loc = self.vehicle.location.global_relative_frame
        dlat = (target.lat - loc.lat) * 1.113195e5
        dlon = (target.lon - loc.lon) * 1.113195e5
        return (dlat ** 2 + dlon ** 2) ** 0.5
