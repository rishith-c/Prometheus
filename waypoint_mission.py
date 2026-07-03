# waypoint_mission.py
# flies a small gps mission: arm, take off, hit each waypoint, come home.
# same warning as always: SITL first, props off for the first live test.

from drone_controller import DroneController

TAKEOFF_ALT = 10        # meters

# (lat, lon, alt)  <-- replace with your own coordinates
WAYPOINTS = [
    (37.12345, -121.12345, 10),
    (37.12360, -121.12310, 10),
    (37.12330, -121.12290, 10),
]


def main():
    drone = DroneController()
    try:
        drone.arm()
        drone.takeoff(TAKEOFF_ALT)
        for lat, lon, alt in WAYPOINTS:
            drone.goto(lat, lon, alt)
        drone.rtl()
    finally:
        # always close the link, even if something above throws
        drone.close()


if __name__ == "__main__":
    main()
