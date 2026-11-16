// Builds on every board in platformio.ini. It only proves the toolchain; it is never flashed.
#include <Arduino.h>

static const int kPin = 2;

void setup() {
  Serial.begin(115200);
  pinMode(kPin, OUTPUT);
}

void loop() {
  digitalWrite(kPin, !digitalRead(kPin));
  Serial.println("jorah-bench");
  delay(500);
}
