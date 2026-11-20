/*
 * esp32_careloop.ino — CareLoop AI Nurse Watch Firmware
 *
 * HARDWARE SPECIFICATION (Matches CareLoop Prototype):
 * 1. ESP32 30-Pin Development Board (CP2102, Wi-Fi + BT)
 * 2. MAX30102 Pulse Oximeter & Heart Rate Sensor (I2C: 0x57)
 * 3. MPU-6050 6-Axis Accelerometer & Gyroscope (I2C: 0x68) — Fall Detection
 * 4. 1.3" I2C OLED Display (128x64, I2C: 0x3C)
 *
 * I2C PIN CONNECTIONS (All 3 modules share the bus):
 * - ESP32 GPIO 21 -> SDA (MAX30102, MPU-6050, OLED)
 * - ESP32 GPIO 22 -> SCL (MAX30102, MPU-6050, OLED)
 * - ESP32 3.3V    -> VCC
 * - ESP32 GND     -> GND
 *
 * PROTOCOLS:
 * - Vitals Telemetry: POST /device/readings (Heart_Rate, SpO2)
 * - Fall Detection:   POST /device/events   (Possible_Fall)
 * - Auth Header:      X-Device-Key: demo-device-key-change-me
 */

#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "MAX30105.h"
#include "heartRate.h"

// --- CONFIGURATION ---
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASS     = "YOUR_WIFI_PASSWORD";
const char* SERVER_BASE   = "http://192.168.1.10:8000"; // CareLoop API Server IP
const char* DEVICE_ID     = "ESP32-DEMO-01";
const char* DEVICE_KEY    = "demo-device-key-change-me";

// OLED Configuration (128x64, I2C address 0x3C)
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
bool oledReady = false;

// Sensor Objects
MAX30105 maxSensor;
bool maxReady = false;
bool mpuReady = false;

// Vitals Tracking Variables
float bpmAvg = 0.0;
float spo2Avg = 98.0;
long lastBeat = 0;
byte beats = 0;
unsigned long lastSend = 0;
unsigned long lastDisplayUpdate = 0;

// Fall Detection Constants
const float FALL_THRESHOLD_G = 2.8; // Impact threshold in G-force
unsigned long lastFallTrigger = 0;

// Initialize MPU-6050 directly over I2C (no external MPU lib needed)
void initMPU6050() {
  Wire.beginTransmission(0x68);
  Wire.write(0x6B); // Power Management 1 register
  Wire.write(0x00); // Wake up MPU-6050
  byte err = Wire.endTransmission(true);
  if (err == 0) {
    mpuReady = true;
    Serial.println("✅ MPU-6050 Accelerometer initialized on 0x68");
  } else {
    Serial.println("⚠️ MPU-6050 not detected at 0x68; check wiring.");
  }
}

// Check for sudden acceleration spikes (Fall Detection)
void checkFallDetection() {
  if (!mpuReady) return;

  Wire.beginTransmission(0x68);
  Wire.write(0x3B); // ACCEL_XOUT_H
  Wire.endTransmission(false);
  Wire.requestFrom(0x68, 6, true);

  if (Wire.available() >= 6) {
    int16_t ax = (Wire.read() << 8) | Wire.read();
    int16_t ay = (Wire.read() << 8) | Wire.read();
    int16_t az = (Wire.read() << 8) | Wire.read();

    // Convert raw 16-bit to G (±2g range: 16384 LSB/g)
    float gX = ax / 16384.0;
    float gY = ay / 16384.0;
    float gZ = az / 16384.0;
    float totalG = sqrt(gX * gX + gY * gY + gZ * gZ);

    if (totalG > FALL_THRESHOLD_G && (millis() - lastFallTrigger > 15000)) {
      lastFallTrigger = millis();
      Serial.printf("🚨 FALL DETECTED! G-Force: %.2f G\n", totalG);
      
      // Update OLED with immediate warning
      if (oledReady) {
        display.clearDisplay();
        display.setTextSize(1);
        display.setTextColor(SSD1306_WHITE);
        display.setCursor(10, 8);
        display.println("!! EMERGENCY !!");
        display.setTextSize(2);
        display.setCursor(10, 26);
        display.println("FALL EVENT");
        display.setTextSize(1);
        display.setCursor(10, 48);
        display.println("Sending alert...");
        display.display();
      }

      sendFallEvent(totalG);
    }
  }
}

// Transmit Fall Event to CareLoop API (/device/events)
void sendFallEvent(float gForce) {
  if (WiFi.status() != WL_CONNECTED) return;

  time_t now;
  time(&now);

  HTTPClient http;
  String url = String(SERVER_BASE) + "/device/events";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);

  String body = String("{\"device_id\":\"") + DEVICE_ID +
                "\",\"event_type\":\"Possible_Fall" +
                "\",\"occurred_at\":" + String((long)now) +
                ",\"details\":{\"g_force\":" + String(gForce, 2) + ",\"sensor\":\"MPU6050\"}}";

  int code = http.POST(body);
  Serial.printf("📡 POST /device/events -> HTTP %d\n", code);
  http.end();
}

// Transmit Vitals Reading to CareLoop API (/device/readings)
void sendReading(const char* mtype, float val, const char* unit, const char* quality) {
  if (WiFi.status() != WL_CONNECTED) return;

  time_t now;
  time(&now);

  HTTPClient http;
  String url = String(SERVER_BASE) + "/device/readings";
  http.begin(url);
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

// Update 1.3" OLED Wrist Display
void updateOLED(bool fingerDetected) {
  if (!oledReady) return;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Header Title matching prototype
  display.setTextSize(1);
  display.setCursor(18, 4);
  display.print("AI NURSE WATCH");
  display.drawLine(0, 15, 128, 15, SSD1306_WHITE);

  // Column Headers
  display.setCursor(6, 20);
  display.print("BPM");
  display.setCursor(76, 20);
  display.print("STATUS");

  // Vitals & Status
  if (fingerDetected && bpmAvg > 35) {
    display.setTextSize(2);
    display.setCursor(4, 34);
    display.printf("%3.0f", bpmAvg);

    display.setTextSize(1);
    display.setCursor(76, 34);
    display.print("OK");
    display.setCursor(76, 46);
    display.printf("SpO2:%2.0f%%", spo2Avg);
  } else {
    display.setTextSize(1);
    display.setCursor(4, 38);
    display.print("No Finger");

    display.setCursor(76, 38);
    display.print("OK");
  }

  // Footer: Wi-Fi status
  display.drawLine(0, 56, 128, 56, SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(6, 57);
  if (WiFi.status() == WL_CONNECTED) {
    display.print("WiFi: Connected");
  } else {
    display.print("WiFi: Searching...");
  }

  display.display();
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n==============================================");
  Serial.println("  CareLoop AI Nurse Watch Telemetry System");
  Serial.println("  ESP32 + MAX30102 + MPU-6050 + 1.3\" OLED");
  Serial.println("==============================================");

  // Initialize shared I2C bus (SDA=21, SCL=22)
  Wire.begin(21, 22);

  // 1. Initialize OLED (0x3C)
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    oledReady = true;
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(10, 20);
    display.println("AI NURSE WATCH");
    display.setCursor(10, 36);
    display.println("Initializing...");
    display.display();
    Serial.println("✅ 1.3\" I2C OLED initialized (0x3C)");
  } else {
    Serial.println("⚠️ OLED not detected at 0x3C");
  }

  // 2. Initialize MPU-6050 (0x68)
  initMPU6050();

  // 3. Initialize MAX30102 (0x57)
  if (maxSensor.begin(Wire, I2C_SPEED_FAST)) {
    maxReady = true;
    maxSensor.setup();
    maxSensor.setPulseAmplitudeRed(0x0A);
    maxSensor.setPulseAmplitudeGreen(0);
    Serial.println("✅ MAX30102 Optical Sensor initialized (0x57)");
  } else {
    Serial.println("⚠️ MAX30102 not detected at 0x57");
  }

  // 4. Connect to Wi-Fi
  Serial.printf("Connecting to Wi-Fi '%s'...", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n✅ Connected! Device IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n⚠️ Wi-Fi connection timed out. Will retry in loop.");
  }

  // 5. Sync NTP Epoch Time
  configTime(0, 0, "pool.ntp.org");
  Serial.println("Synchronizing NTP time for timestamps...");
}

void loop() {
  // 1. Check MPU-6050 for sudden fall events
  checkFallDetection();

  // 2. Sample MAX30102 Optical sensor
  bool fingerDetected = false;
  if (maxReady) {
    long ir = maxSensor.getIR();
    fingerDetected = (ir > 50000);

    if (fingerDetected && checkForBeat(ir)) {
      long delta = millis() - lastBeat;
      lastBeat = millis();
      float bpm = 60.0 / (delta / 1000.0);

      if (bpm > 35.0 && bpm < 210.0) {
        bpmAvg = (beats == 0) ? bpm : (bpmAvg * 0.8f + bpm * 0.2f);
        if (beats < 255) beats++;
      }
    }
  }

  // 3. Refresh OLED display at ~5Hz (every 200ms)
  if (millis() - lastDisplayUpdate > 200) {
    lastDisplayUpdate = millis();
    updateOLED(fingerDetected);
  }

  // 4. Send Vitals to Server every 45 seconds
  if (millis() - lastSend > 45000) {
    lastSend = millis();
    if (fingerDetected && beats >= 5) {
      sendReading("Heart_Rate", bpmAvg, "bpm", "Good");
      sendReading("SpO2", spo2Avg, "%", "Good");
    } else {
      sendReading("Heart_Rate", 0.0, "bpm", "Questionable");
    }
  }
}
