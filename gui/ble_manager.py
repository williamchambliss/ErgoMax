import asyncio
import threading
import json
import traceback
from bleak import BleakScanner, BleakClient

# UUID Constants
SERVICE_UUID = "19B10000-E8F2-537E-4F6C-D104768A1214"
SENSOR_CHAR_UUID = "19B10001-E8F2-537E-4F6C-D104768A1214"
HAPTIC_CHAR_UUID = "19B10002-E8F2-537E-4F6C-D104768A1214"
DEVICE_NAME = "Ergomax_Node"

class BLEManager:
    def __init__(self, data_callback, status_callback):
        self.data_callback = data_callback      # Callback function(packet_dict)
        self.status_callback = status_callback  # Callback function(status_str)
        self.client = None
        self.loop = None
        self.thread = None
        self.is_running = False
        self.connection_status = "Disconnected"
        self._command_queue = asyncio.Queue()

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

    def _run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main_ble_loop())

    async def _main_ble_loop(self):
        while self.is_running:
            self._set_status("Scanning...")
            try:
                device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=5.0)
                if not device:
                    self._set_status("Disconnected (Device not found)")
                    await asyncio.sleep(2.0)
                    continue

                self._set_status("Connecting...")
                async with BleakClient(device, disconnected_callback=self._on_disconnected) as client:
                    self.client = client
                    self._set_status("Connected")
                    
                    # Start notifications
                    await client.start_notify(SENSOR_CHAR_UUID, self._on_notification_received)
                    
                    # Maintain connection and process write commands from queue
                    while self.is_running and client.is_connected:
                        try:
                            # Wait for a command to send to haptic characteristic
                            cmd = await asyncio.wait_for(self._command_queue.get(), timeout=1.0)
                            if client.is_connected:
                                await client.write_gatt_char(HAPTIC_CHAR_UUID, cmd)
                            self._command_queue.task_done()

                        except asyncio.TimeoutError:
                            continue
                        except Exception as e:
                            print(f"Error sending haptic command: {e}")
                            
                    await client.stop_notify(SENSOR_CHAR_UUID)
            except Exception as e:
                print(f"BLE Main Loop Exception: {e}")
                traceback.print_exc()
                self._set_status("Disconnected (Error)")
                await asyncio.sleep(3.0)

        self._set_status("Disconnected")

    def _on_disconnected(self, client):
        self._set_status("Disconnected")

    def _set_status(self, status):
        self.connection_status = status
        if self.status_callback:
            self.status_callback(status)

    def _on_notification_received(self, sender, data):
        try:
            # Parse packed array of 4 bytes: Data[0]=L, Data[1]=MB, Data[2]=UB_L, Data[3]=UB_R
            if len(data) >= 4:
                packet = {
                    "L": int(data[0]),
                    "MB": int(data[1]),
                    "UB_L": int(data[2]),
                    "UB_R": int(data[3])
                }
                if self.data_callback:
                    self.data_callback(packet)
            else:
                print(f"BLE notification payload too short: {len(data)} bytes")
        except Exception as e:
            print(f"Error parsing BLE notification: {e}")


    def send_haptic_command(self, cmd_bytes):
        """Thread-safe method to queue haptic command bytes to be sent via BLE"""
        if self.loop and self.is_running:
            self.loop.call_soon_threadsafe(self._command_queue.put_nowait, cmd_bytes)
            return True
        return False

