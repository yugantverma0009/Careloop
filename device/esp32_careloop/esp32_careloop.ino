/*
 * esp32_careloop.ino — CareLoop ESP32 + MAX30102 Wearable Firmware
 *
 * SENSORS:
 * - SparkFun MAX3010x Pulse and Proximity Sensor Library
 * - I2C pins (ESP32): SDA = GPIO 21, SCL = GPIO 22
 *
 * PROTOCOL:
 * - UTC time synced via NTP (pool.ntp.org)
 * - HTTP POST to /device/readings with header X-Device-Key
 * - Quality status: "Good" (when beats detected), "Questionable" otherwise.
 *
 * NOTE: Optical sensor readings are sensitive to motion, pressure, and ambient light.
 * All readings are prototype values, not a certified medical device.
 */

#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "MAX30105.h"
#include "heartRate.h"

// --- CONFIGURATION ---
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASS     = "YOUR_WIFI_PASSWORD";
const char* API_URL       = "http://192.168.1.10:8000/device/readings"; // Server IP
const char* DEVICE_ID     = "ESP32-DEMO-01";
const char* DEVICE_KEY    = "demo-device-key-change-me";

MAX30105 sensor;
float bpmAvg = 0.0;
long lastBeat = 0;
byte beats = 0;
unsigned long lastSend = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("\nCareLoop ESP32 Wearable Sensor Initializing...");

  Wire.begin(21, 22);
  if (!sensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("❌ MAX30105 sensor not found. Please check wiring (SDA=21, SCL=22).");
    while (1);
  }

  sensor.setup(); // Default LED configuration
  sensor.setPulseAmplitudeRed(0x0A);
  sensor.setPulseAmplitudeGreen(0);

  Serial.printf("Connecting to Wi-Fi '%s'...", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\n✅ Connected! IP: %s\n", WiFi.localIP().toString().c_str());

  // Device sends UTC epoch seconds; CareLoop server converts to Asia/Kolkata (IST)
  configTime(0, 0, "pool.ntp.org");
  Serial.println("Synchronizing NTP time...");
}

void sendReading(const char* mtype, float val, const char* unit, const char* quality) {
  if (WiFi.status() != WL_CONNECTED) return;

  time_t now;
  time(&now);
  if (now < 1700000000) {
    Serial.println("⚠️ NTP time not synchronized yet; skipping send.");
    return;
  }

  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);

  String body = String("{\"device_id\":\"") + DEVICE_ID +
                "\",\"measurement_type\":\"" + mtype +
                "\",\"value\":" + String(val, 1) +
                ",\"unit\":\"" + unit +
                "\",\"measured_at\":" + String((long)now) +
                ",\"quality\":\"" + quality + "\"}";

  int code = http.POST(body);
  Serial.printf("📡 POST %s -> %s (HTTP %d)\n", mtype, body.c_str(), code);
  http.end();
}

void loop() {
  long ir = sensor.getIR();
  bool fingerDetected = (ir > 50000);

  if (fingerDetected && checkForBeat(ir)) {
    long delta = millis() - lastBeat;
    lastBeat = millis();
    float bpm = 60.0 / (delta / 1000.0);

    if (bpm > 30.0 && bpm < 220.0) {
      bpmAvg = (beats == 0) ? bpm : (bpmAvg * 0.8f + bpm * 0.2f);
      if (beats < 255) beats++;
    }
  }

  // Transmit sensor readings every 60 seconds
  if (millis() - lastSend > 60000) {
    lastSend = millis();
    if (fingerDetected && beats >= 5) {
      sendReading("Heart_Rate", bpmAvg, "bpm", "Good");
    } else {
      // Missing or questionable contact
      sendReading("Heart_Rate", 0.0, "bpm", "Questionable");
    }
  }
}
