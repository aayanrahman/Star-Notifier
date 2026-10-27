// Star Notifier: BLE demo on a breadboard ESP32.
//
// The ESP32 advertises as "Star-Notifier". The Mac (firmware/mac/notify.py)
// connects and writes a short command to one characteristic:
//
//   done  -> strobe burst (Claude finished)
//   wait  -> slow breathing until the next command (Claude needs you)
//   off   -> LED off
//   test  -> same as done
//
// Works with the ESP32 Arduino core 2.x and 3.x. Needs a chip with Bluetooth LE:
// ESP32, C3, S3 or C6 (the S2 has no Bluetooth).

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

// LED wiring: GPIO -> 220-330 ohm resistor -> LED long leg, short leg -> GND.
// Many dev boards also have a built-in LED on GPIO 2.
const int LED_PIN = 2;
const bool LED_ACTIVE_LOW = false;  // set true if your LED lights when the pin is LOW

const char *DEVICE_NAME = "Star-Notifier";
#define SERVICE_UUID "12dfac1e-0b86-4adf-8fc9-59cbe90f7db7"
#define COMMAND_UUID "9887946c-c769-4e25-95b7-fc4080034d02"

enum Mode { OFF, STROBE, BREATHE, BLINK_TWICE };

// Written from the BLE task, read in loop().
volatile Mode pendingMode = OFF;
volatile bool hasPending = false;

Mode mode = OFF;
uint32_t modeStart = 0;

void request(Mode m) {
  pendingMode = m;
  hasPending = true;
}

void setLed(uint8_t brightness) {
  analogWrite(LED_PIN, LED_ACTIVE_LOW ? 255 - brightness : brightness);
}

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *server) override {
    Serial.println("Mac connected");
    request(BLINK_TWICE);
  }
  void onDisconnect(BLEServer *server) override {
    Serial.println("Mac disconnected, advertising again");
    server->startAdvertising();
  }
};

class CommandCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *c) override {
    String cmd = String(c->getValue().c_str());  // getValue() is std::string on core 2.x, String on 3.x
    cmd.trim();
    cmd.toLowerCase();
    Serial.printf("Command: %s\n", cmd.c_str());

    if (cmd == "done" || cmd == "test") request(STROBE);
    else if (cmd == "wait") request(BREATHE);
    else if (cmd == "off") request(OFF);
  }
};

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  setLed(0);

  BLEDevice::init(DEVICE_NAME);
  BLEServer *server = BLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());

  BLEService *service = server->createService(SERVICE_UUID);
  BLECharacteristic *command = service->createCharacteristic(
      COMMAND_UUID, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  command->setCallbacks(new CommandCallbacks());
  service->start();

  BLEAdvertising *advertising = BLEDevice::getAdvertising();
  advertising->addServiceUUID(SERVICE_UUID);
  advertising->setScanResponse(true);
  BLEDevice::startAdvertising();

  Serial.println("Advertising as Star-Notifier");
  request(BLINK_TWICE);  // quick hello so you know it booted
}

void loop() {
  if (hasPending) {
    hasPending = false;
    mode = pendingMode;
    modeStart = millis();
  }

  uint32_t t = millis() - modeStart;

  switch (mode) {
    case OFF:
      setLed(0);
      break;

    case STROBE: {
      // 3 bursts of 8 fast flashes, then off.
      const uint32_t flash = 80, flashes = 8, gap = 250;
      const uint32_t burst = flash * flashes + gap;
      if (t >= burst * 3) {
        mode = OFF;
        break;
      }
      uint32_t inBurst = t % burst;
      setLed(inBurst < flash * flashes && inBurst % flash < 30 ? 255 : 0);
      break;
    }

    case BREATHE: {
      // 2 s fade in and out; squaring makes the fade look smoother to the eye.
      float phase = (1.0f - cosf(2.0f * PI * (t % 2000) / 2000.0f)) / 2.0f;
      setLed((uint8_t)(phase * phase * 255));
      break;
    }

    case BLINK_TWICE:
      if (t >= 400) {
        mode = OFF;
        break;
      }
      setLed(t % 200 < 100 ? 255 : 0);
      break;
  }

  delay(5);
}
