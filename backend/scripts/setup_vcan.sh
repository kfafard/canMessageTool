#!/usr/bin/env bash
set -e
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
echo "vcan0 ready"
