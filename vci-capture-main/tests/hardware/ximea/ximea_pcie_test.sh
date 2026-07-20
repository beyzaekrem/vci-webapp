#!/usr/bin/env bash
#
# PCIe diagnostics for XIMEA cameras behind PLX switches
# Safe: read-only, no config changes
#

echo "=== XIMEA PCIe devices ==="
XIMEA_DEVS=$(lspci -nn | grep -i ximea | awk '{print $1}')

if [ -z "$XIMEA_DEVS" ]; then
  echo "No XIMEA devices found"
  exit 0
fi

echo "$XIMEA_DEVS"

echo
echo "=== XIMEA camera PCIe summary ==="
printf "%-10s %-15s %-20s\n" "Camera" "UpstreamPort" "LinkStatus"
printf "%-10s %-15s %-20s\n" "------" "-------------" "----------"

for dev in $XIMEA_DEVS; do
  SYSDEV="/sys/bus/pci/devices/0000:$dev"
  PARENT=$(basename "$(readlink -f "$SYSDEV/..")")

  LINK=$(sudo lspci -vv -s "$dev" | grep "LnkSta:" | sed 's/^[[:space:]]*//')

  printf "%-10s %-15s %-20s\n" "$dev" "$PARENT" "$LINK"
done

echo
echo "=== Detailed PCIe link info for XIMEA endpoints ==="

for dev in $XIMEA_DEVS; do
  echo
  echo "--- Endpoint $dev ---"
  sudo lspci -vv -s "$dev" | grep -E "LnkCap|LnkSta"
done

echo
echo "=== Upstream PCIe bridge details ==="

for dev in $XIMEA_DEVS; do
  SYSDEV="/sys/bus/pci/devices/0000:$dev"
  PARENT=$(basename "$(readlink -f "$SYSDEV/..")")

  echo
  echo "--- $dev <- $PARENT ---"
  sudo lspci -vv -s "$PARENT" | grep -E "LnkCap|LnkSta"
done

echo
echo "=== Kernel PCIe bandwidth messages ==="
sudo dmesg | grep -i "PCIe bandwidth"

echo
echo "=== Done ==="