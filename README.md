# Autonomous GPS Quadcopter

A 1.85kg quadcopter built from scratch for GPS waypoint navigation, position hold, and autonomous missions controlled from a Raspberry Pi.

## What This Is

This project documents a full autonomous drone build, from the carbon fiber frame and electronics all the way through the Python flight control software. The drone runs ArduCopter firmware on a Matek F405-Wing V2 flight controller, with a Raspberry Pi 4 as a companion computer that sends MAVLink commands over UART. You define GPS waypoints in Python, and the drone flies them autonomously.

The repo contains everything needed to reproduce this build: the complete parts list, wiring diagrams, frame assembly instructions, flight controller parameters, sensor calibration procedures, safety protocols, and the Python software for controlling the drone and monitoring telemetry.

**Total hardware cost: roughly $250 to $400 depending on where you source parts.**

Built by [Rishith Chennupati](https://github.com/Cyntax1).

### Project Status

This project is in active development.

**Done:** ArduCopter V4.6.3 firmware flashed, ESC and motor configuration, GPS module connected and tested, frame design finalized.

**In progress:** Sensor calibrations, frame assembly, Raspberry Pi MAVLink integration.

**Upcoming:** First test flight, autonomous mission testing, computer vision integration.

## How It Works

The system has three layers:

1. **Flight controller** (Matek F405-Wing V2): Runs ArduCopter firmware. Handles all the real-time flight stabilization using data from the onboard IMU, barometer, GPS, and compass. It controls the four ESC/motor combos through DShot600 protocol at high speed.

2. **Companion computer** (Raspberry Pi 4): Runs the Python software. Connects to the flight controller over UART at 921600 baud using the MAVLink protocol via DroneKit. This is where you write mission logic, like "take off to 10 meters, fly to these three GPS coordinates, then return home."

3. **Ground station** (optional): QGroundControl or Mission Planner on your laptop for monitoring, parameter tuning, and manual override.

The reason for this split is that the flight controller needs to run a tight real-time control loop (hundreds of times per second) for stability, while the Raspberry Pi handles higher-level decisions like waypoint sequencing and telemetry logging that do not need real-time guarantees.

### Flight Performance

| Spec | Value |
|------|-------|
| Total weight | 1.85 kg (all-up) |
| Thrust-to-weight ratio | 1.89:1 |
| Hover flight time | 12 to 15 minutes |
| Aggressive flight time | 8 to 10 minutes |
| Max thrust | 3500g (875g per motor) |
| Frame size | 450mm diagonal |
| Propellers | 11x7 inches |
| GPS accuracy | 2 to 3 meters |

## Hardware You Need

| Component | Model | Approx. Cost |
|-----------|-------|-------------|
| Flight controller | Matek F405-Wing V2 (STM32 F405, 168MHz) | ~$40 |
| ESC | Diatone Mamba F40 4-in-1 (40A, DShot600) | ~$45 |
| Motors | D2830-12 Brushless x4 (1000 to 1200 KV) | ~$60 |
| Battery | 3000mAh 4S LiPo (14.8V, 60C) | ~$35 |
| GPS module | Beitian BN-880 (Ublox M8N with compass) | ~$20 |
| Companion computer | Raspberry Pi 4 (2 to 4 GB) | ~$35 |
| Frame | Custom carbon fiber rod (450mm, 10x 18mm rods) | ~$25 |
| Propellers | 11x7 inch x4 | ~$10 |

See [hardware/bill-of-materials.md](hardware/bill-of-materials.md) for the complete parts list with links and exact costs.

## Project Structure

```
Autonomous-Drone/
├── config/
│   └── arducopter-params.param      # Flight controller parameter file
├── docs/
│   ├── build-guide.md               # Step-by-step assembly
│   ├── hardware-specs.md            # Detailed component specs
│   ├── flight-controller-setup.md   # ArduCopter configuration
│   ├── mavlink-setup.md             # Raspberry Pi UART wiring and setup
│   ├── calibration-guide.md         # Accelerometer, compass, ESC calibration
│   ├── troubleshooting.md           # Common issues and fixes
│   └── safety.md                    # Safety protocols and checklists
├── hardware/
│   ├── bill-of-materials.md         # Full parts list with costs
│   ├── frame/
│   │   └── frame-assembly.md        # Frame construction
│   └── wiring-diagrams/
│       └── wiring-guide.md          # All electrical connections
└── software/
    ├── requirements.txt             # Python dependencies
    ├── setup.sh                     # Raspberry Pi setup script
    ├── drone_controller.py          # Core DroneKit controller class
    ├── waypoint_mission.py          # Autonomous GPS waypoint missions
    └── monitoring_dashboard.py      # Live terminal telemetry display
```

### Software Architecture

The Python code is organized around two main scripts:

- **drone_controller.py**: A `DroneController` class that wraps DroneKit with clean methods for `arm()`, `takeoff(altitude)`, `goto(lat, lon, alt)`, `rtl()`, and `land()`. It also has a `get_telemetry()` method that returns a dictionary of all current vehicle state (GPS, battery, heading, speed, etc.).

- **waypoint_mission.py**: Uploads a list of GPS waypoints to the flight controller as MAVLink commands (takeoff, navigate to each waypoint, then return to launch), switches to AUTO mode, and monitors progress until the mission completes.

- **monitoring_dashboard.py**: Connects over MAVLink and prints a live-updating terminal dashboard showing GPS position, altitude, heading, speed, battery voltage, and system status. Useful for keeping an eye on the drone during flights.

## Setup

### 1. Build the Hardware

Follow the [Build Guide](docs/build-guide.md) for step-by-step assembly instructions. The [Wiring Guide](hardware/wiring-diagrams/wiring-guide.md) covers all electrical connections between the flight controller, ESC, GPS, and Raspberry Pi.

### 2. Flash the Flight Controller

1. Download [QGroundControl](http://qgroundcontrol.com/) on your Mac (or use Mission Planner on Windows)
2. Connect the Matek F405-Wing V2 via USB
3. Flash ArduCopter V4.6.3 firmware
4. Load the parameter file: go to Config, then Full Parameter List, then Load from file, and select `config/arducopter-params.param`
5. Reboot the flight controller

The parameter file configures the frame type (Quad X), ESC protocol (DShot600), GPS on UART3, MAVLink on UART2 for the Raspberry Pi, battery monitoring with failsafe voltages, and arming checks.

See [Flight Controller Setup](docs/flight-controller-setup.md) for a detailed walkthrough.

### 3. Calibrate Sensors

Before flying, you must calibrate three things:

1. **Accelerometer**: 6-position calibration (level, nose up, nose down, left side, right side, upside down)
2. **Compass**: Outdoor calibration, rotating the drone through all orientations
3. **ESC throttle range**: So the ESCs know the full stick range

Follow the [Calibration Guide](docs/calibration-guide.md) for each procedure.

### 4. Set Up the Raspberry Pi

On the Raspberry Pi (running Raspberry Pi OS Lite):

```bash
git clone https://github.com/rishith-c/Autonomous-Drone.git
cd Autonomous-Drone

chmod +x software/setup.sh
./software/setup.sh
```

The setup script updates the system, installs Python build tools, installs DroneKit and MAVProxy, and enables UART. After it finishes, you need to disable the serial login shell through `raspi-config` (Interface Options, then Serial Port, then set login shell to No and hardware enabled to Yes), then reboot.

See [MAVLink Setup](docs/mavlink-setup.md) for the UART wiring between the Pi and the flight controller.

### 5. Test the Connection

After the Pi is wired to the flight controller and both are powered on:

```bash
cd Autonomous-Drone
python3 software/drone_controller.py
```

This connects over MAVLink and prints the current telemetry (GPS, battery, mode, etc.). If it works, you are ready to fly.

### Using the Software from a Mac (Development and Simulation)

You can develop and test the Python software on your Mac using the DroneKit SITL (Software In The Loop) simulator, which does not require any hardware:

```bash
# Clone the repo
git clone https://github.com/rishith-c/Autonomous-Drone.git
cd Autonomous-Drone

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r software/requirements.txt

# Start a simulated drone
dronekit-sitl copter --home=37.12345,-121.12345,0,0

# In another terminal, test the controller
python3 -c "
from dronekit import connect
vehicle = connect('tcp:127.0.0.1:5760', wait_ready=True)
print(f'Mode: {vehicle.mode.name}')
print(f'GPS: {vehicle.gps_0}')
vehicle.close()
"
```

### Running a Waypoint Mission

Edit the `WAYPOINTS` list in `software/waypoint_mission.py` with your GPS coordinates, then run:

```bash
python3 software/waypoint_mission.py
```

The script uploads the mission (takeoff, waypoints, return to launch), arms the motors, switches to AUTO mode, and prints telemetry as the drone flies each waypoint.

## Photos

<!-- Add photo: completed drone from above showing the quad X motor layout -->
<!-- Add photo: electronics stack showing flight controller, ESC, GPS module, and Raspberry Pi -->
<!-- Add photo: carbon fiber frame during assembly -->
<!-- Add photo: wiring closeup between flight controller and ESC -->
<!-- Add photo: terminal output from the monitoring dashboard during a flight -->

## Safety

Read [docs/safety.md](docs/safety.md) before flying. Key points:

- Always have a manual RC transmitter as backup (or a ground station with manual override)
- Check battery failsafe voltages are set (14.0V low, 13.2V critical in the parameter file)
- Calibrate sensors before every new flying location
- Never fly over people
- Start with low-altitude hover tests before attempting waypoint missions

## Future Plans

- FPV camera for first-person view
- RC receiver for manual backup control
- Obstacle avoidance sensors
- Computer vision with OpenCV (object tracking, precision landing)
- Multi-drone coordination

## Resources

- [ArduPilot Documentation](https://ardupilot.org/copter/)
- [DroneKit-Python Docs](https://dronekit-python.readthedocs.io/)
- [MAVLink Protocol](https://mavlink.io/en/)
- [Matek F405-Wing V2 Docs](http://www.mateksys.com/?portfolio=f405-wing-v2)
- [QGroundControl](http://qgroundcontrol.com/)

## License

MIT License. See [LICENSE](LICENSE).
