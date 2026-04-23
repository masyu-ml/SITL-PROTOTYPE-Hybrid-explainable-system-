#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "LittleFS.h"

// --- NETWORK CREDENTIALS ---
const char* ssid = "***";             
const char* password = "***"; 

// --- TARGET LAPTOP IP ---
const char* laptopIP = "192.168.1.6";     
const int udpPort = 8080;                   

WiFiUDP udp;
File dataFile;
bool isPlaying = false; 

void jumpToFault(String faultStr) {
  if (!dataFile) {
      dataFile = LittleFS.open("/BACHA_PRESENT_STATE.csv", "r");
      if(!dataFile) dataFile = LittleFS.open("BACHA_PRESENT_STATE.csv", "r");
  }
  
  if (!dataFile) { 
    Serial.println("\n[!] ERROR: Cannot inject fault. CSV File is missing!"); 
    return; 
  }

  Serial.println("\n[>] FAULT INJECTION TRIGGERED: " + faultStr);
  dataFile.seek(0); 
  if (dataFile.available()) dataFile.readStringUntil('\n'); 

  bool found = false;
  while (dataFile.available()) {
      size_t startPos = dataFile.position();
      String line = dataFile.readStringUntil('\n');
      if (line.indexOf(faultStr) != -1) {
          dataFile.seek(startPos); 
          isPlaying = true;
          found = true;
          Serial.println("[+] SUCCESS: Synced to real '" + faultStr + "' telemetry.");
          break;
      }
  }
  if (!found) Serial.println("[!] WARNING: Label '" + faultStr + "' not found in dataset.");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n\n========================================");
  Serial.println("   AUTONOMOUS NODE: HARDWARE BOOTUP     ");
  Serial.println("========================================");

  // 1. Storage Check
  Serial.print("[1/3] Initializing LittleFS... ");
  if(!LittleFS.begin(true)){ 
    Serial.println("FAILED!"); 
    return; 
  }
  Serial.println("OK.");

  // 2. File Check
  Serial.print("[2/3] Locating BACHA_PRESENT_STATE.csv... ");
  if (LittleFS.exists("/BACHA_PRESENT_STATE.csv") || LittleFS.exists("BACHA_PRESENT_STATE.csv")) {
    File temp = LittleFS.open("/BACHA_PRESENT_STATE.csv", "r");
    if(!temp) temp = LittleFS.open("BACHA_PRESENT_STATE.csv", "r");
    Serial.println("FOUND.");
    Serial.printf("      Dataset Size: %d bytes\n", temp.size());
    temp.close();
  } else {
    Serial.println("NOT FOUND!");
    Serial.println("      Please upload the CSV via Sketch Data Upload.");
  }

  // 3. Connection Check
  Serial.print("[3/3] Connecting to WiFi [" + String(ssid) + "] ");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n\n--- NETWORK ESTABLISHED ---");
  Serial.print(">> ESP32 IP ADDRESS: ");
  Serial.println(WiFi.localIP());  // <--- Copy this IP to your Python Software
  Serial.println("----------------------------\n");
  
  udp.begin(udpPort);
  Serial.println("[READY] Awaiting UDP commands from Python dashboard...");
}

void loop() {
  int packetSize = udp.parsePacket();
  if (packetSize) {
    char incomingPacket[255];
    int len = udp.read(incomingPacket, 255);
    if (len > 0) { incomingPacket[len] = 0; }
    String command = String(incomingPacket);
    command.trim();
    
    Serial.println("[RECV] Command: " + command);
    
    if (command == "RESUME") {
      if (!dataFile) {
          dataFile = LittleFS.open("/BACHA_PRESENT_STATE.csv", "r");
          if(!dataFile) dataFile = LittleFS.open("BACHA_PRESENT_STATE.csv", "r");
          if (dataFile && dataFile.available()) dataFile.readStringUntil('\n'); 
      }
      isPlaying = true;
      Serial.println("[STATE] Mission Resumed.");
    }
    else if (command == "PAUSE") { 
      isPlaying = false; 
      Serial.println("[STATE] Mission Paused.");
    }
    else if (command == "RESET") {
      isPlaying = false;
      if (dataFile) {
          dataFile.seek(0); 
          if(dataFile.available()) dataFile.readStringUntil('\n'); 
          Serial.println("[STATE] Vehicle Reset to Start.");
      }
    }
    else if (command == "INJECT_SHORT") { jumpToFault("short_circuit"); }
    else if (command == "INJECT_OPEN")  { jumpToFault("open_circuit"); }
    else if (command == "INJECT_HEAT")  { jumpToFault("overheating"); }
    else if (command == "CLEAR_FAULTS") { 
      if(dataFile) dataFile.seek(0); 
      Serial.println("[STATE] Faults Cleared.");
    }
  }

  if (isPlaying && dataFile && dataFile.available()) {
    String telemetryLine = dataFile.readStringUntil('\n');
    telemetryLine.trim();

    if (telemetryLine.length() > 5) {
        udp.beginPacket(laptopIP, udpPort);
        udp.print(telemetryLine);
        udp.endPacket();
    }
    delay(50); 
  } 
}