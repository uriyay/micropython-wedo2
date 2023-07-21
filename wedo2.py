import bluetooth
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

WEDO2_SERVICE_UUID = bluetooth.UUID('00004f0e-1212-efde-1523-785feabcd123')
Sensor_Value_UUID = bluetooth.UUID('00001560-1212-efde-1523-785feabcd123')
Value_format_UUID = bluetooth.UUID('00001561-1212-efde-1523-785feabcd123')
Input_Command_UUID = bluetooth.UUID('00001563-1212-efde-1523-785feabcd123')
Output_Command_UUID = bluetooth.UUID('00001565-1212-efde-1523-785feabcd123')

scan_results = []

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
        self.start_handle = None
        self.end_handle = None
        self.sensor_value_handle = None
        self.value_format_handle = None
        self.input_command_handle = None
        self.output_command_handle = None

    def scan(self):
        print('scanning..')
        #https://stackoverflow.com/a/66307619
        self.ble.gap_scan(5000, 1280000, 11250, True)

    def ble_handler(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            addr = bytes(addr)
            adv_data = bytes(adv_data)
            name = decode_name(adv_data) or '?'
            #scan_results
            print("address: {}, rssi: {}, adv_data = {}, name = {}".format(addr, rssi, adv_data, name))
            if name == 'LPF2 Smart Hub':
                self.address = addr
                self._addr_type = addr_type
                self.ble.gap_scan(None)
        elif event == _IRQ_SCAN_DONE:
            print('scan is over')
            if self.address:
                #connect
                print('connecting to address {}'.format(self.address))
                self.ble.gap_connect(self._addr_type, self.address)
        elif event == _IRQ_PERIPHERAL_CONNECT :
            conn_handle, addr_type, addr = data
            addr = bytes(addr)
            print('device is connected: address = {}'.format(addr))
            if addr == self.address:
                print('setting conn_handle')
                self.conn_handle = conn_handle
                print('discovering services..')
                self.ble.gattc_discover_services(self.conn_handle)
        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            print('device is disconnected')
            self.reset()
        elif event == _IRQ_GATTC_SERVICE_RESULT:
            conn_handle, start_handle, end_handle, uuid = data
            uuid = bytes(uuid)
            print('found service for conn_handle={}, uuid={}'.format(conn_handle, uuid))
            if conn_handle == self.conn_handle and uuid == bytes(WEDO2_SERVICE_UUID):
                print('found wedo2 service!')
                self.start_handle = start_handle
                self.end_handle = end_handle
        elif event == _IRQ_GATTC_SERVICE_DONE:
            print('discovering services ended')
            # Service query complete.
            if self.start_handle and self.end_handle:
                print('discovering characteristics for wedo2 service..')
                self.ble.gattc_discover_characteristics(
                    self.conn_handle, self.start_handle, self.end_handle
                )
            else:
                print("Failed to find wedo2 service")
        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            # Connected device returned a characteristic.
            conn_handle, def_handle, value_handle, properties, uuid = data
            uuid = bytes(uuid)
            print('found char uuid={}'.format(uuid))
            if conn_handle == self.conn_handle and uuid == bytes(Sensor_Value_UUID):
                print('sensor_value_handle = {}'.format(value_handle))
                self.sensor_value_handle = value_handle
            elif conn_handle == self._conn_handle and uuid == bytes(Value_format_UUID):
                print('value_format_handle = {}'.format(value_handle))
                self.value_format_handle = value_handle
            elif conn_handle == self._conn_handle and uuid == bytes(Input_Command_UUID):
                print('input_command_handle = {}'.format(value_handle))
                self.input_command_handle = value_handle
            elif conn_handle == self._conn_handle and uuid == bytes(Output_Command_UUID):
                print('output_command_handle = {}'.format(value_handle))
                self.output_command_handle = value_handle

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            # Characteristic query complete.
            print('discovering chars ended')
            if all([self.sensor_value_handle,
                    self.value_format_handle,
                    self.input_command_handle,
                    self.output_command_handle]):
                print('succeeded to find all chars')
            else:
                print("Failed to find wedo2 service characteristic.")

        elif event == _IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            print("write to handle={} done".format(value_handle))

        elif event == _IRQ_GATTC_NOTIFY:
            conn_handle, value_handle, notify_data = data
            notify_data = bytes(notify_data)
            if conn_handle == self.conn_handle:
                self.notify_callback(value_handle, notify_data)

    def is_connected(self):
        return all([
            self.conn_handle,
            self.sensor_value_handle,
            self.value_format_handle,
            self.input_command_handle,
            self.output_command_handle])

    #def input_command(self,
