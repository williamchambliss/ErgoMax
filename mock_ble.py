import time
import threading

class MockBLEManager:
    def __init__(self, data_callback, status_callback):
        self.data_callback = data_callback
        self.status_callback = status_callback
        self.is_running = False
        self.thread = None
        self.connection_status = "Disconnected"

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self._mock_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        self._set_status("Disconnected")

    def _set_status(self, status):
        self.connection_status = status
        if self.status_callback:
            self.status_callback(status)

    def _mock_loop(self):
        self._set_status("Scanning...")
        time.sleep(2.0)
        if not self.is_running:
            return
            
        self._set_status("Connecting...")
        time.sleep(1.5)
        if not self.is_running:
            return
            
        self._set_status("Connected")
        
        start_time = time.time()
        while self.is_running:
            elapsed = int(time.time() - start_time)
            
            # Base values (representing uncalibrated state around 30, calibrated active target is 150+)
            # Unpressed pressure is around 30.
            # Pressed pressure is around 200.
            packet = {"L": 30, "MB": 0, "UB_L": 0, "UB_R": 0}
            
            # Posture cycle every 20 seconds for dev testing
            cycle = (elapsed // 20) % 7
            
            if cycle == 0:
                # Good Alignment (all sensors have pressure)
                packet = {"L": 220, "MB": 255, "UB_L": 255, "UB_R": 255}
            elif cycle == 1:
                # Slouched Shoulders (L and MB active, UB inactive)
                packet = {"L": 225, "MB": 255, "UB_L": 35, "UB_R": 30}
            elif cycle == 2:
                # Bottom Forward (L inactive, MB/UB active)
                packet = {"L": 25, "MB": 255, "UB_L": 255, "UB_R": 255}
            elif cycle == 3:
                # Left-leaning Tilt (UB_L active, UB_R inactive, L/MB active)
                packet = {"L": 210, "MB": 255, "UB_L": 255, "UB_R": 30}
            elif cycle == 4:
                # Right-leaning Tilt (UB_R active, UB_L inactive, L/MB active)
                packet = {"L": 215, "MB": 255, "UB_L": 35, "UB_R": 255}
            elif cycle == 5:
                # Away / No Contact (all inactive, testing Active Rest vs Away)
                packet = {"L": 30, "MB": 0, "UB_L": 0, "UB_R": 0}
            elif cycle == 6:
                # Mixed / Good Alignment again
                packet = {"L": 210, "MB": 255, "UB_L": 255, "UB_R": 255}
                
            if self.data_callback:
                self.data_callback(packet)
                
            time.sleep(1.0)

    def send_haptic_command(self, cmd_bytes):
        print(f"[MOCK BLE DEVICE] Received haptic command: {list(cmd_bytes)}")
        return True

