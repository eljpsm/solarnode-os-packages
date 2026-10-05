#!/usr/bin/python3

# SPDX-License-Identifier: LGPL-2.1-or-later
# Utils and example classes have been sourced from BlueZ with
# modification to class paths.
# https://github.com/bluez/bluez

import array
import json
import logging
import os
import signal
import socket
import sys
from typing import Optional

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"

BLUEZ_ADAPTER_IFACE = "org.bluez.Adapter1"
BLUEZ_AGENTMANAGER_IFACE = "org.bluez.AgentManager1"

GATT_SERVICE_IFACE = "org.bluez.GattService1"
GATT_CHRC_IFACE = "org.bluez.GattCharacteristic1"
GATT_DESC_IFACE = "org.bluez.GattDescriptor1"

LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"

BUS_NAME = "org.bluez"
GATT_MANAGER_IFACE = "org.bluez.GattManager1"

AGENT_INTERFACE = "org.bluez.Agent1"
AGENT_PATH = "/net/solarnetwork/node/setup/agent"

# Default address/port of the SolarNode STOMP setup server
# (net.solarnetwork.node.setup.stomp); change here if the upstream bundle
# is reconfigured.
SN_STOMP_ADDRESS = "127.0.0.1"
SN_STOMP_PORT = 8780
# The node's identity, whose nodeId we advertise.
SN_IDENTITY_PATH = "/etc/solarnode/identity.json"
SN_LABEL_CONF_PATHS = (
    "/usr/share/solarnode/default/sn-system",
    "/etc/default/sn-system",
)
SN_LABEL_KEY = "CFG_SOLARNODE_LABEL="
SN_LABEL_DEFAULT = "SolarNode"

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("SN_BT_SETUP_PERIPHERAL_LOG_LEVEL", "INFO").upper())
logHandler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)

bus: Optional[dbus.SystemBus] = None
mainloop: Optional[GLib.MainLoop] = None

exit_status = 0


def fail_and_quit(message, *args) -> None:
    """
    Log a critical failure, mark the process as failed, and stop the main loop.
    """
    global exit_status
    exit_status = 1
    logger.critical(message, *args)
    assert mainloop is not None
    mainloop.quit()


class InvalidArgsException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.freedesktop.DBus.Error.InvalidArgs"


class NotSupportedException(dbus.exceptions.DBusException):
    _dbus_error_name = "org.bluez.Error.NotSupported"


class Service(dbus.service.Object):
    """
    org.bluez.GattService1 interface implementation.
    """

    PATH_BASE = "/net/solarnetwork/node/setup/service"

    def __init__(self, bus, index, uuid, primary):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                "UUID": self.uuid,
                "Primary": self.primary,
                "Characteristics": dbus.Array(
                    self.get_characteristic_paths(), signature="o"
                ),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)

    def get_characteristic_paths(self):
        return [chrc.get_path() for chrc in self.characteristics]

    def get_characteristics(self):
        return self.characteristics

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_SERVICE_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_SERVICE_IFACE]


class Characteristic(dbus.service.Object):
    """
    org.bluez.GattCharacteristic1 interface implementation.
    """

    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + "/char" + str(index)
        self.bus = bus
        self.uuid = uuid
        self.service = service
        self.flags = flags
        self.descriptors = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                "Service": self.service.get_path(),
                "UUID": self.uuid,
                "Flags": self.flags,
                "Descriptors": dbus.Array(self.get_descriptor_paths(), signature="o"),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_descriptor(self, descriptor):
        self.descriptors.append(descriptor)

    def get_descriptor_paths(self):
        return [desc.get_path() for desc in self.descriptors]

    def get_descriptors(self):
        return self.descriptors

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_CHRC_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_CHRC_IFACE]

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options) -> list[int]:
        logger.info("Default ReadValue called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options) -> None:
        logger.info("Default WriteValue called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StartNotify(self) -> None:
        logger.info("Default StartNotify called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_CHRC_IFACE)
    def StopNotify(self) -> None:
        logger.info("Default StopNotify called, returning error")
        raise NotSupportedException()

    @dbus.service.signal(DBUS_PROP_IFACE, signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


class Descriptor(dbus.service.Object):
    """
    org.bluez.GattDescriptor1 interface implementation.
    """

    def __init__(self, bus, index, uuid, flags, characteristic):
        self.path = characteristic.path + "/desc" + str(index)
        self.bus = bus
        self.uuid = uuid
        self.flags = flags
        self.chrc = characteristic
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        return {
            GATT_DESC_IFACE: {
                "Characteristic": self.chrc.get_path(),
                "UUID": self.uuid,
                "Flags": self.flags,
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != GATT_DESC_IFACE:
            raise InvalidArgsException()

        return self.get_properties()[GATT_DESC_IFACE]

    @dbus.service.method(GATT_DESC_IFACE, in_signature="a{sv}", out_signature="ay")
    def ReadValue(self, options) -> list[int]:
        logger.info("Default ReadValue called, returning error")
        raise NotSupportedException()

    @dbus.service.method(GATT_DESC_IFACE, in_signature="aya{sv}")
    def WriteValue(self, value, options) -> None:
        logger.info("Default WriteValue called, returning error")
        raise NotSupportedException()


class Advertisement(dbus.service.Object):
    """
    A BlueZ advertisement.
    """

    PATH_BASE = "/net/solarnetwork/node/setup/advertisement"

    def __init__(self, bus, index, advertising_type):
        self.path = self.PATH_BASE + str(index)
        self.bus = bus
        self.ad_type = advertising_type
        self.service_uuids = None
        self.manufacturer_data = None
        self.solicit_uuids = None
        self.service_data = None
        self.local_name = None
        self.include_tx_power = None
        self.data = None
        dbus.service.Object.__init__(self, bus, self.path)

    def get_properties(self):
        properties = dict()
        properties["Type"] = self.ad_type
        if self.service_uuids is not None:
            properties["ServiceUUIDs"] = dbus.Array(self.service_uuids, signature="s")
        if self.solicit_uuids is not None:
            properties["SolicitUUIDs"] = dbus.Array(self.solicit_uuids, signature="s")
        if self.manufacturer_data is not None:
            properties["ManufacturerData"] = dbus.Dictionary(
                self.manufacturer_data, signature="qv"
            )
        if self.service_data is not None:
            properties["ServiceData"] = dbus.Dictionary(
                self.service_data, signature="sv"
            )
        if self.local_name is not None:
            properties["LocalName"] = dbus.String(self.local_name)
        if self.include_tx_power is not None:
            properties["IncludeTxPower"] = dbus.Boolean(self.include_tx_power)

        if self.data is not None:
            properties["Data"] = dbus.Dictionary(self.data, signature="yv")
        return {LE_ADVERTISEMENT_IFACE: properties}

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service_uuid(self, uuid):
        if not self.service_uuids:
            self.service_uuids = []
        self.service_uuids.append(uuid)

    def add_solicit_uuid(self, uuid):
        if not self.solicit_uuids:
            self.solicit_uuids = []
        self.solicit_uuids.append(uuid)

    def add_manufacturer_data(self, manuf_code, data):
        if not self.manufacturer_data:
            self.manufacturer_data = dbus.Dictionary({}, signature="qv")
        self.manufacturer_data[manuf_code] = dbus.Array(data, signature="y")

    def add_service_data(self, uuid, data):
        if not self.service_data:
            self.service_data = dbus.Dictionary({}, signature="sv")
        self.service_data[uuid] = dbus.Array(data, signature="y")

    def add_local_name(self, name):
        self.local_name = dbus.String(name)

    def add_data(self, ad_type, data):
        if not self.data:
            self.data = dbus.Dictionary({}, signature="yv")
        self.data[ad_type] = dbus.Array(data, signature="y")

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        logger.info("GetAll")
        if interface != LE_ADVERTISEMENT_IFACE:
            raise InvalidArgsException()
        logger.info("returning props")
        return self.get_properties()[LE_ADVERTISEMENT_IFACE]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        logger.info("%s: Released!", self.path)


def register_ad_cb():
    logger.info("Advertisement registered")


def register_ad_error_cb(error):
    fail_and_quit("Failed to register advertisement: %s", error)


class CharacteristicUserDescriptionDescriptor(Descriptor):
    """
    Read-only CUD descriptor exposing the parent characteristic's description.
    """

    CUD_UUID = "2901"

    def __init__(self, bus, index, characteristic):
        self.value = array.array("B", characteristic.description.encode()).tolist()
        Descriptor.__init__(self, bus, index, self.CUD_UUID, ["read"], characteristic)

    def ReadValue(self, options):
        return self.value


class UartAdvertisement(Advertisement):
    """
    Generic UUART advertisement. The ``service_uuid`` argument must match the
    UUID of the GATT service we're exposing, pass ``UartService.uuid`` so the
    two stay coupled at the call site.
    """

    def __init__(self, bus, index, local_name, service_uuid):
        Advertisement.__init__(self, bus, index, "peripheral")
        self.add_service_uuid(service_uuid)

        self.add_local_name(local_name)
        self.include_tx_power = True


class TxCharacteristic(Characteristic):
    """
    Notify characteristic that streams bytes from the STOMP server back to
    subscribed centrals.

    Notifications are broadcast to all subscribers, with multiple concurrent
    centrals their STOMP streams will interleave on the BLE side. In practice
    SolarNode setup is one-central-at-a-time.
    """

    uuid = "7d2fd14d-8897-48de-9719-15aa4edb5d57"
    description = "STOMP server responses (notify)."

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, self.uuid, ["notify"], service)
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))
        self.notifying = False

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True
        logger.info("StartNotify")

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False
        logger.info("StopNotify")

    def push(self, data: bytes) -> None:
        if not self.notifying:
            logger.debug("push: no subscriber, dropping %d bytes", len(data))
            return
        value = dbus.Array(data, signature="y")
        self.PropertiesChanged(GATT_CHRC_IFACE, {"Value": value}, [])


class RxCharacteristic(Characteristic):
    """
    Write characteristic. Each connected central gets its own TCP socket to
    the SolarNetwork STOMP server. Bytes received from the server are pushed
    back to the central via ``TxCharacteristic`` (Notify). Reads are driven
    by ``GLib.io_add_watch`` so the main loop is never blocked on TCP I/O.

    Failure-mode sentinels pushed to the central: ``\\x07`` if the STOMP
    backend refuses the connection, ``\\x18`` if a previously-open session
    is torn down (server FIN, OSError, or HUP/ERR on the io watch).
    """

    uuid = "7d2fd14c-8897-48de-9719-15aa4edb5d57"
    description = "Submit frames to SolarNetwork STOMP server."

    def __init__(self, bus, index, service, tx: "TxCharacteristic"):
        Characteristic.__init__(self, bus, index, self.uuid, ["write"], service)
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))
        self.tx = tx
        self.central_sockets = {}  # device path, socket
        self.central_watches = {}  # device path, GLib source id

    def _open_socket(self, device: str) -> Optional[socket.socket]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Tight TCP keepalive so a hung or FIN-lost STOMP server gets
        # detected in ~45 s instead of the default Linux ~2 h. Pairs
        # with `on_device_connect`'s "kill stale socket" guard: that
        # one handles the central-side teardown, this handles the
        # server side. Linux-specific options are best-effort,
        # wrapped so a future port to a kernel without TCP_KEEPIDLE
        # still gets bare-minimum SO_KEEPALIVE.
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        except (OSError, AttributeError) as e:
            logger.warning("Couldn't tune TCP keepalive for %s: %s", device, e)
        try:
            sock.connect((SN_STOMP_ADDRESS, SN_STOMP_PORT))
        except OSError as e:
            logger.warning("STOMP connect failed for %s: %s", device, e)
            return None

        self.central_sockets[device] = sock
        source_id = GLib.io_add_watch(
            sock.fileno(),
            GLib.PRIORITY_DEFAULT,
            GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
            lambda fd, condition: self._on_readable(device, condition),
        )
        self.central_watches[device] = source_id
        logger.info("STOMP socket opened for %s", device)
        return sock

    def _on_readable(self, device: str, condition: int) -> bool:
        # GLib I/O watch callback: return True to stay armed, False to detach.
        sock = self.central_sockets.get(device)
        if sock is None:
            return False

        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            logger.info("STOMP HUP/ERR for %s (condition=%s)", device, condition)
            self.tx.push(b"\x18")
            self._close_socket(device)
            return False

        try:
            data = sock.recv(4096)
        except OSError as e:
            logger.warning("STOMP recv failed for %s: %s", device, e)
            self.tx.push(b"\x18")
            self._close_socket(device)
            return False

        if not data:
            logger.info("STOMP closed by peer for %s", device)
            self.tx.push(b"\x18")
            self._close_socket(device)
            return False

        logger.debug(
            "received (%d bytes):\n%s",
            len(data),
            data.decode("utf-8", errors="replace"),
        )
        self.tx.push(data)
        return True

    def _close_socket(self, device: str) -> None:
        # Detach the GLib watch before closing the fd: otherwise GLib observes
        # the closed fd, fires IO_HUP, and re-enters this method.
        source_id = self.central_watches.pop(device, None)
        if source_id is not None:
            GLib.source_remove(source_id)
        sock = self.central_sockets.pop(device, None)
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def WriteValue(self, value, options):
        device = options["device"]
        logger.debug("WRITE from %s (%d bytes)", device, len(value))

        sock = self.central_sockets.get(device) or self._open_socket(device)
        if sock is None:
            self.tx.push(b"\x07")
            return

        # dbus.Byte is an int subclass, so bytes() round-trips the BLE write
        # without re-encoding (values >= 0x80 stay one byte each).
        byte_value = bytes(value)
        logger.debug(
            "sent (%d bytes):\n%s",
            len(byte_value),
            byte_value.decode("utf-8", errors="replace"),
        )
        try:
            sock.sendall(byte_value)
        except OSError as e:
            logger.warning("STOMP send failed for %s: %s", device, e)
            self._close_socket(device)
            self.tx.push(b"\x18")

    def on_device_disconnect(self, device: str) -> None:
        if device in self.central_sockets:
            logger.info("Central disconnected, closing STOMP socket: %s", device)
            self._close_socket(device)

    def on_device_connect(self, device: str) -> None:
        # Defense-in-depth against missed disconnect signals: if we still
        # hold a TCP socket for this device path from a previous BLE
        # session, the SolarNode STOMP server may still treat that
        # session as active and reject the next CONNECT with
        # "Already connected." Tear it down so the next WriteValue
        # lazy-opens a fresh socket.
        if device in self.central_sockets:
            logger.info(
                "Central reconnected; tearing down stale STOMP socket: %s",
                device,
            )
            self._close_socket(device)

    def close_all(self) -> None:
        for device in list(self.central_sockets):
            self._close_socket(device)


class UartService(Service):
    """
    UART-style service that bridges BLE writes and Notify with the
    SolarNetwork STOMP server.
    """

    uuid = "7d2fd14b-8897-48de-9719-15aa4edb5d57"

    def __init__(self, bus, index):
        Service.__init__(self, bus, index, self.uuid, True)
        self.tx = TxCharacteristic(bus, 0, self)
        self.add_characteristic(self.tx)
        self.rx = RxCharacteristic(bus, 1, self, self.tx)
        self.add_characteristic(self.rx)


def set_trusted(path):
    assert bus is not None
    props = dbus.Interface(
        bus.get_object("org.bluez", path), "org.freedesktop.DBus.Properties"
    )
    props.Set("org.bluez.Device1", "Trusted", True)


class SmartAgent(dbus.service.Object):
    """
    BlueZ agent registered as NoInputNoOutput, auto-trusts pairing requests
    without prompting. The interactive prompt variant (BlueZ's upstream
    simple-agent shape) is intentionally omitted: under systemd there is no
    TTY, so prompting via input() would EOFError on the first pairing attempt.
    """

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Release(self):
        # BlueZ calls Release when our agent registration is being dropped,
        # usually because bluetoothd is going away.
        fail_and_quit("Agent registration released by BlueZ")

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        logger.info("AuthorizeService (%s, %s)", device, uuid)

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        logger.info("RequestPinCode (%s)", device)
        set_trusted(device)
        return ""

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        logger.info("RequestPasskey (%s)", device)
        set_trusted(device)
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_INTERFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        logger.info("DisplayPasskey (%s, %06u entered %u)", device, passkey, entered)

    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        logger.info("DisplayPinCode (%s, %s)", device, pincode)

    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        logger.info("RequestConfirmation (%s, %06d)", device, passkey)
        set_trusted(device)

    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        logger.info("RequestAuthorization (%s)", device)

    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Cancel(self):
        logger.info("Cancel")


class Application(dbus.service.Object):
    """
    org.bluez.GattApplication1 interface implementation.
    """

    PATH = "/net/solarnetwork/node/setup/app"

    def __init__(self, bus, services=()):
        self.path = self.PATH
        self.services = list(services)
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    @dbus.service.method(DBUS_OM_IFACE, out_signature="a{oa{sa{sv}}}")
    def GetManagedObjects(self):
        response = {}
        logger.info("GetManagedObjects")

        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
                descs = chrc.get_descriptors()
                for desc in descs:
                    response[desc.get_path()] = desc.get_properties()

        return response


def register_app_cb():
    logger.info("GATT application registered")


def register_app_error_cb(error):
    fail_and_quit("Failed to register application: %s", error)


def find_adapter(bus):
    """
    Returns the D-Bus path of the BlueZ adapter to use.

    Honors ``SN_BT_SETUP_PERIPHERAL_ADAPTER`` (e.g. ``SN_BT_SETUP_PERIPHERAL_ADAPTER=hci0``) to disambiguate
    when multiple adapters are present; otherwise returns the first adapter
    that advertises org.bluez.GattManager1.

    The solarcfg helper (cfg.d/bluetooth.sh) applies the same rule when it
    reports or turns off the adapter, so keep the two in step.
    """
    remote_om = dbus.Interface(bus.get_object(BUS_NAME, "/"), DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()

    preferred = os.environ.get("SN_BT_SETUP_PERIPHERAL_ADAPTER")
    if preferred:
        preferred_path = "/org/bluez/" + preferred
        props = objects.get(preferred_path)
        if props is None:
            logger.critical(
                "SN_BT_SETUP_PERIPHERAL_ADAPTER=%s not found on bus", preferred
            )
            return None
        if GATT_MANAGER_IFACE not in props:
            logger.critical(
                "SN_BT_SETUP_PERIPHERAL_ADAPTER=%s lacks GattManager1", preferred
            )
            return None
        logger.info(
            "Using adapter %s (from SN_BT_SETUP_PERIPHERAL_ADAPTER)", preferred_path
        )
        return preferred_path

    for o, props in objects.items():
        if GATT_MANAGER_IFACE in props.keys():
            logger.info("Using adapter %s", o)
            return o

    return None


def read_node_id() -> Optional[int]:
    """
    Returns the ``nodeId`` from ``/etc/solarnode/identity.json``, or ``None``
    when the node has not been registered yet.

    Raises ``OSError`` if the file exists but cannot be read.
    """
    try:
        with open(SN_IDENTITY_PATH) as f:
            identity = json.load(f)
    except FileNotFoundError:
        return None
    except (ValueError, UnicodeDecodeError) as e:
        logger.warning("Ignoring unparsable %s: %s", SN_IDENTITY_PATH, e)
        return None

    node_id = identity.get("nodeId") if isinstance(identity, dict) else None
    if not isinstance(node_id, int) or isinstance(node_id, bool):
        return None

    return node_id


def read_node_label() -> str:
    """
    Returns ``CFG_SOLARNODE_LABEL`` from the sn-system configuration, so the
    name we advertise matches the pretty hostname identity-configure.sh derives
    from the same value.
    """
    label = SN_LABEL_DEFAULT

    for path in SN_LABEL_CONF_PATHS:
        try:
            with open(path) as f:
                lines = f.readlines()
        except OSError:
            continue
        for line in lines:
            if line.strip().startswith(SN_LABEL_KEY):
                value = line.strip().split("=", 1)[1].strip().strip("\"'")
                if value:
                    label = value

    return label


def set_state(state, adapter_props):
    logger.info("Setting host state to %s...", "ON" if state else "OFF")
    value = dbus.Boolean(bool(state))
    for prop in ("Powered", "Discoverable", "Pairable"):
        adapter_props.Set(BLUEZ_ADAPTER_IFACE, prop, value)


def main() -> int:
    global bus
    global mainloop

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter = find_adapter(bus)
    if not adapter:
        # bluetoothd may still be coming up, or the adapter may not be attached
        # yet...
        logger.critical("GattManager1 interface not found")
        return 1

    adapter_obj = bus.get_object(BUS_NAME, adapter)
    adapter_props = dbus.Interface(adapter_obj, DBUS_PROP_IFACE)

    # Get the required local_name.
    try:
        node_id = read_node_id()
    except OSError as e:
        logger.critical("Cannot read %s: %s", SN_IDENTITY_PATH, e)
        set_state(False, adapter_props)
        return 1

    if node_id is None:
        # A node that hasn't been registered yet has nothing to advertise, and
        # no amount of retrying changes that.
        logger.info("Node has not been registered yet, not advertising")
        set_state(False, adapter_props)
        return 0

    local_name = f"{read_node_label()} {node_id}"
    logger.info("Advertising as %s", local_name)

    set_state(True, adapter_props)

    # Get manager objects.
    service_manager = dbus.Interface(adapter_obj, GATT_MANAGER_IFACE)
    ad_manager = dbus.Interface(adapter_obj, LE_ADVERTISING_MANAGER_IFACE)

    obj = bus.get_object(BUS_NAME, "/org/bluez")

    agent = SmartAgent(bus, AGENT_PATH)

    service = UartService(bus, 0)
    app = Application(bus, [service])

    # Advertisement carries the service UUID so centrals can discover us.
    advertisement = UartAdvertisement(bus, 0, local_name, service.uuid)

    def on_device_properties_changed(interface, changed, invalidated, path=None):
        if interface != "org.bluez.Device1":
            return
        if path is None or "Connected" not in changed:
            return
        if changed["Connected"]:
            service.rx.on_device_connect(path)
        else:
            service.rx.on_device_disconnect(path)

    device_signal_match = bus.add_signal_receiver(
        on_device_properties_changed,
        signal_name="PropertiesChanged",
        dbus_interface=DBUS_PROP_IFACE,
        arg0="org.bluez.Device1",
        path_keyword="path",
    )

    loop = GLib.MainLoop()
    mainloop = loop

    # Register the agent.
    agent_manager = dbus.Interface(obj, BLUEZ_AGENTMANAGER_IFACE)
    agent_manager.RegisterAgent(agent, "NoInputNoOutput")
    logger.info("Agent registered")

    # Register the advertisement.
    ad_manager.RegisterAdvertisement(
        advertisement.get_path(),
        {},
        reply_handler=register_ad_cb,
        error_handler=register_ad_error_cb,
    )
    logger.info("Advertisement registered")

    logger.info("Registering GATT application...")
    service_manager.RegisterApplication(
        app.get_path(),
        {},
        reply_handler=register_app_cb,
        error_handler=register_app_error_cb,
    )
    agent_manager.RequestDefaultAgent(AGENT_PATH)

    def _on_shutdown_signal():
        logger.info("Shutdown signal received")
        loop.quit()
        return False

    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, _on_shutdown_signal)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, _on_shutdown_signal)

    logger.info("Entered mainloop")
    try:
        loop.run()
    finally:
        logger.info("Shutting down...")
        service.rx.close_all()
        try:
            device_signal_match.remove()
        except dbus.exceptions.DBusException as e:
            logger.warning("Failed to remove device signal receiver: %s", e)
        for name, action in (
            (
                "advertisement",
                lambda: ad_manager.UnregisterAdvertisement(advertisement.get_path()),
            ),
            (
                "application",
                lambda: service_manager.UnregisterApplication(app.get_path()),
            ),
            ("agent", lambda: agent_manager.UnregisterAgent(AGENT_PATH)),
        ):
            try:
                action()
                logger.info("%s unregistered", name)
            except dbus.exceptions.DBusException as e:
                logger.warning("Failed to unregister %s: %s", name, e)
        # The radio is only meant to be reachable while this peripheral runs,
        # so leave the adapter off (not discoverable, not pairable, not
        # powered) rather than lingering in the state set_state(True) put it
        # in at startup.
        try:
            set_state(False, adapter_props)
        except dbus.exceptions.DBusException as e:
            logger.warning("Failed to turn adapter off: %s", e)
        logger.info("Shutdown complete")

    return exit_status


if __name__ == "__main__":
    sys.exit(main())
