import bluetooth
import struct
import collections
from micropython import const

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_GATTS_READ_REQUEST = const(4)
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_DESCRIPTOR_RESULT = const(13)
_IRQ_GATTC_DESCRIPTOR_DONE = const(14)
_IRQ_GATTC_READ_RESULT = const(15)
_IRQ_GATTC_READ_DONE = const(16)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)
_IRQ_GATTC_INDICATE = const(19)
_IRQ_GATTS_INDICATE_DONE = const(20)
_IRQ_MTU_EXCHANGED = const(21)
_IRQ_L2CAP_ACCEPT = const(22)
_IRQ_L2CAP_CONNECT = const(23)
_IRQ_L2CAP_DISCONNECT = const(24)
_IRQ_L2CAP_RECV = const(25)
_IRQ_L2CAP_SEND_READY = const(26)
_IRQ_CONNECTION_UPDATE = const(27)
_IRQ_ENCRYPTION_UPDATE = const(28)
_IRQ_GET_SECRET = const(29)
_IRQ_SET_SECRET = const(30)

_ADV_IND = const(0x00)
_ADV_DIRECT_IND = const(0x01)

_ADV_TYPE_NAME = const(0x09)

WEDO2_SERVICE_UUID = bluetooth.UUID("00004f0e-1212-efde-1523-785feabcd123")
NORDIC_LED_BUTTON_SERVICE = bluetooth.UUID("00001523-1212-efde-1523-785feabcd123")
Sensor_Value_UUID = bluetooth.UUID("00001560-1212-efde-1523-785feabcd123")
Value_format_UUID = bluetooth.UUID("00001561-1212-efde-1523-785feabcd123")
Input_Command_UUID = bluetooth.UUID("00001563-1212-efde-1523-785feabcd123")
Output_Command_UUID = bluetooth.UUID("00001565-1212-efde-1523-785feabcd123")
Attached_UUID = bluetooth.UUID("00001527-1212-EFDE-1523-785FEABCD123")
Attached_Config_UUID = b'\x02)'

NOTIFY_ENABLE = const(1)

IO_TYPE_MOTOR = const(1)
IO_TYPE_VOLTAGE = const(20)
IO_TYPE_CURRENT = const(21)
IO_TYPE_PIEZO_TONE_PLAYER = const(22)
IO_TYPE_RGB_LIGHT = const(23)
IO_TYPE_TILT_SENSOR = const(34)
IO_TYPE_MOTION_SENSOR = const(35)
IO_TYPE_GENERIC = const(0)

MOTOR_COMMAND_ID = const(0x01)
INPUT_VALUE_COMMAND_ID = const(0x0)
INPUT_FORMAT_COMMAND_ID = const(0x1)

MOTOR_BREAK = const(127)
MOTOR_DRIFT = const(0)


def decode_field(payload, adv_type):
    i = 0
    result = []
    while i + 1 < len(payload):
        if payload[i + 1] == adv_type:
            result.append(payload[i + 2 : i + payload[i] + 1])
        i += 1 + payload[i]
    return result


def decode_name(payload):
    n = decode_field(payload, _ADV_TYPE_NAME)
    return str(n[0], "utf-8") if n else ""


class Wedo2:
    def __init__(self):
        self.reset()

        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self.ble_handler)

    def reset(self):
        self.address = None
        self._addr_type = None
        self.conn_handle = None
        self.wedo_start_handle = None
        self.wedo_end_handle = None
        self.nordic_start_handle = None
        self.nordic_end_handle = None
        self.sensor_value_handle = None
        self.value_format_handle = None
        self.input_command_handle = None
        self.output_command_handle = None
        self.attached_handle = None
        self.attached_end_handle = None
        self.attached_config_dsc_handle = None
        self.connect_id_motor = None
        self.connect_id_voltage = None
        self.connect_id_current = None
        self.connect_id_piezo = None
        self.connect_id_rgb_light = None
        self.connect_id_tilt_sensor = None
        self.connect_id_motion_sensor = None
        self.connect_id_generic = None
        self.tried_discovering_noridc = False
        self.callbacks = []

    def scan(self):
        print("scanning..")
        # https://stackoverflow.com/a/66307619
        self.ble.gap_scan(5000, 1280000, 11250, True)

    def ble_handler(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            addr = bytes(addr)
            adv_data = bytes(adv_data)
            name = decode_name(adv_data) or "?"
            # scan_results
            print(
                "address: {}, rssi: {}, adv_data = {}, name = {}".format(
                    addr, rssi, adv_data, name
                )
            )
            if name == "LPF2 Smart Hub":
                self.address = addr
                self._addr_type = addr_type
                self.ble.gap_scan(None)
        elif event == _IRQ_SCAN_DONE:
            print("scan is over")
            if self.address:
                # connect
                print("connecting to address {}".format(self.address))
                self.ble.gap_connect(self._addr_type, self.address)
        elif event == _IRQ_PERIPHERAL_CONNECT:
            conn_handle, addr_type, addr = data
            addr = bytes(addr)
            print("device is connected: address = {}".format(addr))
            if addr == self.address:
                print("setting conn_handle")
                self.conn_handle = conn_handle
                print("discovering services..")
                self.ble.gattc_discover_services(self.conn_handle)
        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            print("device is disconnected")
            self.reset()
        elif event == _IRQ_GATTC_SERVICE_RESULT:
            conn_handle, start_handle, end_handle, uuid = data
            uuid = bytes(uuid)
            print("found service for conn_handle={}, uuid={}".format(conn_handle, uuid))
            if conn_handle == self.conn_handle:
                if uuid == bytes(WEDO2_SERVICE_UUID):
                    print("found wedo2 service!")
                    self.wedo_start_handle = start_handle
                    self.wedo_end_handle = end_handle

                elif uuid == bytes(NORDIC_LED_BUTTON_SERVICE):
                    print("found nordic led button service")
                    self.nordic_start_handle = start_handle
                    self.nordic_end_handle = end_handle

        elif event == _IRQ_GATTC_SERVICE_DONE:
            print("discovering services ended")
            print("discovering characteristics for wedo2 service..")
            self.ble.gattc_discover_characteristics(
                self.conn_handle, self.wedo_start_handle, self.wedo_end_handle
            )
            # Service query complete.
        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Connected device returned a characteristic.
            conn_handle, end_handle, value_handle, properties, uuid = data
            uuid = bytes(uuid)
            print("found char uuid={}".format(uuid))
            if conn_handle == self.conn_handle:
                if uuid == bytes(Sensor_Value_UUID):
                    print("sensor_value_handle = {}".format(value_handle))
                    self.sensor_value_handle = value_handle
                elif uuid == bytes(Value_format_UUID):
                    print("value_format_handle = {}".format(value_handle))
                    self.value_format_handle = value_handle
                elif uuid == bytes(Input_Command_UUID):
                    print("input_command_handle = {}".format(value_handle))
                    self.input_command_handle = value_handle
                elif uuid == bytes(Output_Command_UUID):
                    print("output_command_handle = {}".format(value_handle))
                    self.output_command_handle = value_handle
                elif uuid == bytes(Attached_UUID):
                    print("attached uuid handle = {}".format(value_handle))
                    self.attached_handle = value_handle
                    self.attached_end_handle = end_handle

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            # Characteristic query complete.
            print("discovering chars ended")
            if all(
                [
                    self.sensor_value_handle,
                    self.value_format_handle,
                    self.input_command_handle,
                    self.output_command_handle,
                ]
            ):
                print("succeeded to find all chars")
            else:
                print("Failed to find wedo2 service characteristic.")

            if self.attached_handle is None and not self.tried_discovering_noridc:
                self.tried_discovering_noridc = True
                print("discovering characteristics for nordic led btton service..")
                self.ble.gattc_discover_characteristics(
                    self.conn_handle, self.nordic_start_handle, self.nordic_end_handle
                )
            else:
                if self.attached_handle is None:
                    print("Failed to find nordic service chars")
                else:
                    print("found noridc chars")
                    #discover descriptors
                    self.ble.gattc_discover_descriptors(self.conn_handle,
                        self.attached_handle,
                        self.attached_end_handle
                    )

            #self.ble.
        elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
            # Called for each descriptor found by gattc_discover_descriptors().
            conn_handle, dsc_handle, uuid = data
            uuid = bytes(uuid)
            print("got dsc_handle = {} for uuid = {}".format(dsc_handle, uuid))
            if uuid == Attached_Config_UUID:
                self.attached_config_dsc_handle = dsc_handle
        elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
            # Called once service discovery is complete.
            # Note: Status will be zero on success, implementation-specific value otherwise.
            conn_handle, status = data
            self.discover_hub_idx()

        elif event == _IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            print("write to handle={} done, status={}".format(value_handle, status))
        elif event == _IRQ_GATTC_NOTIFY:
            conn_handle, value_handle, notify_data = data
            notify_data = bytes(notify_data)
            print("got notify, value_handle={}, notify_data={}".format(value_handle, notify_data))
            if conn_handle == self.conn_handle:
                self.notify_callback(value_handle, notify_data)
        elif event == _IRQ_GATTC_READ_RESULT:
            conn_handle, value_handle, char_data = data
            char_data = bytes(char_data)
            print("got read result for value_handle={}, char_data={}".format(value_handle, char_data))
        elif event == _IRQ_GATTC_READ_DONE:
            conn_handle, value_handle, status = data
            print("read done for value_handle={}, status={}".format(value_handle, status))
        elif event == _IRQ_GATTC_INDICATE:
            # A server has sent an indicate request.
            conn_handle, value_handle, notify_data = data
            print("got gattc indicate")
        elif event == _IRQ_GATTS_INDICATE_DONE:
            # A client has acknowledged the indication.
            # Note: Status will be zero on successful acknowledgment, implementation-specific value otherwise.
            conn_handle, value_handle, status = data
            print("got indicate done")

    def is_connected(self):
        return all(
            [
                self.conn_handle,
                self.sensor_value_handle,
                self.value_format_handle,
                self.input_command_handle,
                self.output_command_handle,
            ]
        )

    def disconnect(self):
        self.ble.gap_disconnect(self.conn_handle)
        self.reset()

    def notify_callback(self, value_handle, data):
        print("notify_callback: value_handle = {}, notify_data = {}".format(value_handle, data))
        if value_handle == self.attached_handle:
            if len(data) < 2:
                print("Something went wrong when retrieving attached io data")

            connect_id = data[0:1][0]
            attached = data[1:2][0]

            if attached == 1:
                hub_index = data[2:3][0]
                io_type = data[3:4][0]
                print("attached connect_id={}, hub_index={}, io_type={}".format(
                    connect_id, hub_index, io_type))
                if io_type == IO_TYPE_CURRENT:
                    self.connect_id_current = connect_id
                elif io_type == IO_TYPE_GENERIC:
                    self.connect_id_generic = connect_id
                elif io_type == IO_TYPE_MOTION_SENSOR:
                    self.connect_id_motion_sensor = connect_id
                elif io_type == IO_TYPE_MOTOR:
                    self.connect_id_motor = connect_id
                elif io_type == IO_TYPE_PIEZO_TONE_PLAYER:
                    self.connect_id_piezo = connect_id
                elif io_type == IO_TYPE_RGB_LIGHT:
                    self.connect_id_rgb_light = connect_id
                elif io_type == IO_TYPE_TILT_SENSOR:
                    self.connect_id_tilt_sensor = connect_id
                elif io_type == IO_TYPE_VOLTAGE:
                    self.connect_id_voltage = connect_id

    def discover_hub_idx(self):
        self.ble.gattc_write(self.conn_handle, self.attached_config_dsc_handle, struct.pack('<h', NOTIFY_ENABLE), 1)

    def input_command(self, command):
        self.ble.gattc_write(self.conn_handle, self.input_command_handle, command, mode=1)

    def output_command(self, hub_idx, command_id, command_data):
        command = struct.pack('BBB', hub_idx, command_id, len(command_data)) + command_data
        self.ble.gattc_write(self.conn_handle, self.output_command_handle, command,
            1) #mode=1

    def _motor_power(self, power, offset):
        #TODO: get the hub_idx automatically from the service data
        # from https://github.com/jannopet/LEGO-WeDo-2.0-Python-SDK
        is_positive = power >= 0
        power = abs(power)

        actual_power = ((100.0 - offset) / 100.0) * power + offset
        actual_result_int = round(actual_power)

        if not is_positive:
            actual_result_int = -actual_result_int

        command_data = struct.pack('b', actual_result_int)
        self.output_command(self.connect_id_motor, MOTOR_COMMAND_ID, command_data)

    def motor_turn(self, power):
        self._motor_power(power, 35)

    def motor_break(self):
        self._motor_power(MOTOR_BREAK, 0)

    def motor_drift(self):
        self._motor_power(MOTOR_DRIFT, 0)

w = Wedo2()
w.scan()
