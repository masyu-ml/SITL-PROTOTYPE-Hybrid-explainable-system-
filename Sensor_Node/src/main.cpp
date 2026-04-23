#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "LittleFS.h"

// --- NETWORK CREDENTIALS ---
const char* ssid = "RMB 2.4G";             
const char* password = "@Basilio115529"; 

// --- TARGET LAPTOP IP ---
const char* laptopIP = "192.168.1.6";     
const int udpPort = 8080;                   

WiFiUDP udp;
File dataFile;
bool isPlaying = false; 

// --- FAULT INJECTION STATES ---
bool injectShortCircuit = false;
bool injectOpenCircuit = false;
bool injectOverheating = false;
float artificialHeat = 0.0; 

void setup() {
  Serial.begin(115200);
  delay(1000);

  if(!LittleFS.begin(true)){ 
    Serial.println("CRITICAL: LittleFS Mount Failed!"); 
    return; 
  }
  Serial.println("LittleFS Mounted.");

  // --- DIAGNOSTIC: LIST ALL FILES ---
  Serial.println("Scanning Filesystem...");
  File root = LittleFS.open("/");
  File file = root.openNextFile();
  while(file){
      Serial.print("Found File: ");
      Serial.println(file.name());
      file = root.openNextFile();
  }

  Serial.print("Connecting to Wi-Fi: ");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  
  Serial.println("\n--- WI-FI CONNECTED ---");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
  
  udp.begin(udpPort);
  Serial.println("SYSTEM READY: Awaiting UDP Command...");
}

void loop() {
  // --- LISTEN FOR WIRELESS COMMANDS ---
  int packetSize = udp.parsePacket();
  if (packetSize) {
    char incomingPacket[255];
    int len = udp.read(incomingPacket, 255);
    if (len > 0) { incomingPacket[len] = 0; }
    
    String command = String(incomingPacket);
    command.trim();
    Serial.println("Received: " + command);
    
    if (command == "RESUME") {
      if (!dataFile) {
          dataFile = LittleFS.open("/BACHA_PRESENT_STATE.csv", "r");
          // Fallback for different LittleFS naming conventions
          if(!dataFile) dataFile = LittleFS.open("BACHA_PRESENT_STATE.csv", "r");
      }

      if (dataFile) {
          isPlaying = true; 
          Serial.println("STATUS: DATA FOUND - STARTING STREAM");
      } else {
          Serial.println("ERROR: File not found on Flash.");
      }
    }
    else if (command == "PAUSE") { 
      isPlaying = false; 
      Serial.println("STATUS: PAUSED");
    }
    else if (command == "RESET") {
      isPlaying = false; // Stop streaming while resetting
      if (dataFile) {
          dataFile.seek(0); // Move "needle" to start of file
          // Optional: If your CSV has headers, skip the first line
          if(dataFile.available()) dataFile.readStringUntil('\n'); 
          Serial.println("SYSTEM RESET: Data set to beginning.");
      } else {
          Serial.println("RESET ERROR: File not open.");
      }
    }
    else if (command == "INJECT_SHORT") { injectShortCircuit = true; Serial.println("FAULT: Short Circuit Injected"); }
    else if (command == "INJECT_OPEN")  { injectOpenCircuit = true; Serial.println("FAULT: Open Circuit Injected"); }
    else if (command == "INJECT_HEAT")  { injectOverheating = true; Serial.println("FAULT: Overheating Injected"); }
    else if (command == "CLEAR_FAULTS") {
        injectShortCircuit = false;
        injectOpenCircuit = false;
        injectOverheating = false;
        artificialHeat = 0.0;
        Serial.println("STATUS: ALL FAULTS CLEARED");
    }
  }

  // --- CSV TELEMETRY STREAMING ---
  if (isPlaying && dataFile && dataFile.available()) {
    String telemetryLine = dataFile.readStringUntil('\n');
    
    // --- FAULT INJECTION OVERRIDE ---
    if (injectShortCircuit) { 
        telemetryLine = "99999,500.0,1.2,60.0,0,0,0,0,0,0,0,0,0,0,0,fault,F1"; 
    } 
    else if (injectOpenCircuit) { 
        telemetryLine = "99999,0.0,0.0,25.0,0,0,0,0,0,0,0,0,0,0,0,fault,F2"; 
    } 
    else if (injectOverheating) {
        artificialHeat += 2.5; 
        telemetryLine = "99999,10.5,12.0," + String(40.0 + artificialHeat) + ",0,0,0,0,0,0,0,0,0,0,0,fault,F3";
    }

    // Wireless Broadcast to Laptop
    udp.beginPacket(laptopIP, udpPort);
    udp.print(telemetryLine);
    udp.endPacket();
    
    delay(50); // 20Hz Sampling Rate
  } 
  
  // End of File reached
  if (isPlaying && dataFile && !dataFile.available()) {
    isPlaying = false;
    Serial.println("STATUS: END OF DATASET");
  }
}