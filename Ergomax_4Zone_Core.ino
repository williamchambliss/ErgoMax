#include <ArduinoBLE.h>

// ==========================================
// 1. 4-ZONE HARDWARE MAPPING
// ==========================================
const int NUM_ZONES = 4;

// Index order: [0]=Lower Back, [1]=Mid Back, [2]=Left Shoulder, [3]=Right Shoulder
const int SENSOR_PINS[NUM_ZONES] = {A0, A1, A2, A3};
const int HAPTIC_PINS[NUM_ZONES] = {3, 5, 6, 9}; // All must be PWM capable

// ==========================================
// 2. BLE SERVICE & CHARACTERISTIC DEFINITIONS
// ==========================================
BLEService ergomaxService("19B10000-E8F2-537E-4F6C-D104768A1214");

// TX: Broadcasts all 4 sensors at once as an array of 4 bytes (Values: 0 to 255)
BLECharacteristic txDataCharacteristic("19B10001-E8F2-537E-4F6C-D104768A1214", BLERead | BLENotify, 4);

// RX: Accepts a 4-byte array from PC to independently adjust intensities (Values: 0 to 255)
BLECharacteristic rxHapticCharacteristic("19B10002-E8F2-537E-4F6C-D104768A1214", BLEWrite, 4);

// ==========================================
// 3. RUNTIME DATA STRUCTURES & TIMING
// ==========================================
byte currentSensorPayload[NUM_ZONES] = {0, 0, 0, 0};
byte lastSensorPayload[NUM_ZONES]    = {0, 0, 0, 0};

unsigned long lastSampleTime = 0;
const unsigned long SAMPLE_RATE_MS = 50; // Poll and stream at 20Hz

void setup() {
  Serial.begin(9600);

  // Configure Sensors & Pins
  // Zone 0 is an FSR with an external pulldown resistor. 
  // Zones 1, 2, 3 are currently buttons wired to GND (Leveraging Internal Pullups)
  pinMode(SENSOR_PINS[0], INPUT);
  for (int i = 1; i < NUM_ZONES; i++) {
    pinMode(SENSOR_PINS[i], INPUT_PULLUP); 
  }

  // Configure Haptic Channels
  for (int i = 0; i < NUM_ZONES; i++) {
    pinMode(HAPTIC_PINS[i], OUTPUT);
    analogWrite(HAPTIC_PINS[i], 0); // Start off
  }

  // Init BLE Radio
  if (!BLE.begin()) {
    Serial.println("Hardware Error: BLE subsystem failed to start.");
    while (1);
  }

  BLE.setLocalName("Ergomax_Node");
  BLE.setAdvertisedService(ergomaxService);
  
  ergomaxService.addCharacteristic(txDataCharacteristic);
  ergomaxService.addCharacteristic(rxHapticCharacteristic);
  BLE.addService(ergomaxService);

  // Seed baseline byte buffers
  txDataCharacteristic.writeValue(currentSensorPayload, 4);
  
  BLE.advertise();
  Serial.println("Ergomax 4-Zone Node Active. Awaiting PC Handshake...");
}

void loop() {
  BLEDevice pcClient = BLE.central();

  if (pcClient) {
    Serial.print("Secure data link open with PC: ");
    Serial.println(pcClient.address());

    while (pcClient.connected()) {
      unsigned long currentTime = millis();

      // --- TASK A: SYNCHRONIZED SENSOR STREAMING (TX) ---
      if (currentTime - lastSampleTime >= SAMPLE_RATE_MS) {
        lastSampleTime = currentTime;
        bool dataHasChanged = false;

        for (int i = 0; i < NUM_ZONES; i++) {
          int rawAnalog = analogRead(SENSOR_PINS[i]);

          // Handle Mixed Inputs: Convert 10-bit analog range (0-1023) down to a single byte (0-255)
          byte compressedByte;
          
          if (i == 0) {
            // Zone 0: True FSR. Map normal analog resolution.
            compressedByte = rawAnalog >> 2; // Fast divide-by-4 conversion
          } else {
            // Zones 1, 2, 3: Temporary Buttons.
            // INPUT_PULLUP forces pin HIGH (approx 1023) when idle. Pressed pulls to GND (0).
            // We invert this logic so 0 = no pressure, 255 = max button down force.
            compressedByte = (rawAnalog < 500) ? 255 : 0;
          }

          currentSensorPayload[i] = compressedByte;

          // Check if this sensor value shifted noticeably compared to last cycle
          if (abs(currentSensorPayload[i] - lastSensorPayload[i]) > 2) {
            dataHasChanged = true;
          }
        }

        // Push packet only if there is fresh physical movement/pressure updates
        if (dataHasChanged) {
          txDataCharacteristic.writeValue(currentSensorPayload, 4);
          memcpy(lastSensorPayload, currentSensorPayload, 4);
        }
      }

      // --- TASK B: INDEPENDENT ACTUATOR INGESTION (RX) ---
      if (rxHapticCharacteristic.written()) {
        const byte* inboundTargetIntensity = rxHapticCharacteristic.value();
        
        Serial.print("Inbound Haptic Frame Executed -> ");
        for (int i = 0; i < NUM_ZONES; i++) {
          // Direct variable speed PWM control mapped cleanly across all 4 quadrants
          analogWrite(HAPTIC_PINS[i], inboundTargetIntensity[i]);
          
          Serial.print("[Z"); Serial.print(i); Serial.print(":");
          Serial.print(inboundTargetIntensity[i]); Serial.print("] ");
        }
        Serial.println();
      }
    }

    // Fail-Safe: Terminate all vibrating channels immediately if connection drops
    Serial.println("Link dropped. Safety disarm triggered.");
    for (int i = 0; i < NUM_ZONES; i++) {
      analogWrite(HAPTIC_PINS[i], 0);
    }
  }
}
