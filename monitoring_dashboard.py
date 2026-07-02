# monitoring_dashboard.py
# prints live telemetry in the terminal. read only, never arms or moves anything,
# so it's safe to run whenever you're connected.

import time
from dronekit import connect

CONNECTION = "/dev/ttyAMA0"
BAUD = 921600


def main():
    print(f"connecting to {CONNECTION} ...")
    v = connect(CONNECTION, wait_ready=True, baud=BAUD)
    print("connected, streaming (ctrl-c to stop)\n")
    try:
        while True:
            loc = v.location.global_relative_frame
            gps = v.gps_0
            batt = v.battery
            print("\033[2J\033[H", end="")     # clear screen, cursor home
            print("PROMETHEUS TELEMETRY")
            print("-" * 30)
            print(f"mode         {v.mode.name}")
            print(f"armed        {v.armed}")
            print(f"gps fix      {gps.fix_type}  ({gps.satellites_visible} sats)")
            print(f"battery      {batt.voltage} V   {batt.level}%")
            print(f"altitude     {loc.alt:.1f} m")
            print(f"groundspeed  {v.groundspeed:.1f} m/s")
            print(f"heading      {v.heading}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        v.close()


if __name__ == "__main__":
    main()
