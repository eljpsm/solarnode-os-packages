#!/usr/bin/env bash
#
# SolarNode Bluetooth setup radio helper script for the solarnode-bluetooth-setup
# package, which turns the BLE setup peripheral on and off.
#
# Invoked by the solarcfg wrapper:
#
#     solarcfg bluetooth <action>
#
# Output contract (consumed by the plugin):
#   status					-> "key: value" lines. "active: true|false" is whether the
#              					peripheral service is running (and so advertising);
#              					"enabled: true|false" is whether the service is enabled at boot
#              					(legacy always-on install mode); "discoverable: true|false" and
#								"powered: true|false" are the Bluetooth adapter state;
#								"adapter: hciN" is the adapter name. Always exits 0.
#   enable/disable/restart	->	human-readable result lines on STDOUT; errors on
#              					STDERR with a non-zero exit code.
#
# Exit codes: 0 success, 1 unsupported action, 3 systemctl failure.

CONF="/usr/share/solarnode/default/solarnode-bluetooth-setup"
VENDOR_CONF="/etc/default/solarnode-bluetooth-setup"
ENV_FILE="/etc/solarnode/bluetooth-setup.env"
[ -e "$CONF" ] && . "$CONF"
[ -e "$VENDOR_CONF" ] && . "$VENDOR_CONF"
[ -e "$ENV_FILE" ] && . "$ENV_FILE"

ADAPTER="${SN_BT_SETUP_PERIPHERAL_ADAPTER:-hci0}"
UNIT="solarnode-bt-setup-peripheral.service"

ACTION="$1"
shift 2>/dev/null

# Adapter properties are changed through bluetoothd over D-Bus, the same path
# the peripheral script uses, so bluetoothd's view of the adapter stays
# coherent. busctl ships with systemd and has reliable exit codes, unlike
# non-interactive bluetoothctl.
adapter_prop_get () {
	# prints "true" or "false", or nothing if the adapter is unavailable
	busctl get-property org.bluez "/org/bluez/$ADAPTER" org.bluez.Adapter1 "$1" 2>/dev/null \
		| awk '{print $2}'
}

adapter_prop_set () {
	busctl set-property org.bluez "/org/bluez/$ADAPTER" org.bluez.Adapter1 "$1" b "$2" >/dev/null 2>&1
}

unit_active () {
	systemctl is-active --quiet "$UNIT"
}

bool_word () {
	if [ "$1" = "true" ]; then echo true; else echo false; fi
}

do_status () {
	if unit_active; then
		echo "active: true"
	else
		echo "active: false"
	fi
	if systemctl is-enabled --quiet "$UNIT" 2>/dev/null; then
		echo "enabled: true"
	else
		echo "enabled: false"
	fi
	echo "discoverable: $(bool_word "$(adapter_prop_get Discoverable)")"
	echo "powered: $(bool_word "$(adapter_prop_get Powered)")"
	echo "adapter: $ADAPTER"
	exit 0
}

do_enable () {
	# The peripheral script powers the adapter and sets it discoverable and
	# pairable itself when it starts, so starting the unit is all that is needed.
	if unit_active; then
		echo "Bluetooth setup radio already enabled."
		exit 0
	fi
	if systemctl start "$UNIT"; then
		echo "Bluetooth setup radio enabled."
	else
		echo "Unable to start $UNIT." 1>&2
		exit 3
	fi
}

do_disable () {
	# Stop the peripheral (which unregisters the advertisement), then make sure
	# the adapter is not left discoverable, pairable, or powered. The adapter
	# steps are best-effort so that disable always succeeds, even when the
	# adapter is already off or not present.
	systemctl stop "$UNIT" || true
	adapter_prop_set Discoverable false || true
	adapter_prop_set Pairable false || true
	adapter_prop_set Powered false || true
	echo "Bluetooth setup radio disabled."
	exit 0
}

do_restart () {
	if systemctl restart "$UNIT"; then
		echo "Bluetooth setup radio restarted."
	else
		echo "Unable to restart $UNIT." 1>&2
		exit 3
	fi
}

case "$ACTION" in
	status)  do_status "$@";;
	enable)  do_enable "$@";;
	disable) do_disable "$@";;
	restart) do_restart "$@";;
	*)
		echo "Action '${ACTION}' not supported. Use one of: status, enable, disable, restart." 1>&2
		exit 1
esac
