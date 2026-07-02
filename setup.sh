#!/usr/bin/env bash
# quick pi setup. installs the python deps. run: chmod +x setup.sh && ./setup.sh
set -e

echo "installing python deps ..."
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install -r requirements.txt

echo
echo "one manual step (raspi-config is interactive, can't script it cleanly):"
echo "  sudo raspi-config  ->  Interface Options  ->  Serial Port"
echo "    login shell over serial : NO"
echo "    serial hardware enabled : YES"
echo "then reboot. the FC is on /dev/ttyAMA0 (aka /dev/serial0) at 921600 baud."
