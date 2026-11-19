/*
  SINA Fresh 0.2 -- optional REFERENCE Arduino Uno sensor emitter.
  Requires an actual pulse-output flow meter and independent calibration.
  This sketch does not drive pumps, valves or other actuators.

  Set PULSES_PER_LITER to YOUR verified sensor's calibration before use.
  Pressure is not measured here and is intentionally omitted from CSV.
  Output per sample: ,LINE-1,<flow_lpm>,
  SINA serial gateway assigns UTC receive timestamp to each sample.
*/

const byte FLOW_PULSE_PIN = 2;  // UNO hardware interrupt pin
const float PULSES_PER_LITER = 0.0f;  // REQUIRED: set using calibration test
const unsigned long SAMPLE_INTERVAL_MS = 1000UL;
volatile unsigned long pulseCount = 0;
unsigned long lastSampleMs = 0;

void onFlowPulse() { pulseCount++; }

void setup() {
  Serial.begin(115200);
  pinMode(FLOW_PULSE_PIN, INPUT_PULLUP);  // Confirm with YOUR sensor data sheet
  attachInterrupt(digitalPinToInterrupt(FLOW_PULSE_PIN), onFlowPulse, FALLING);
  lastSampleMs = millis();
}

void loop() {
  unsigned long now = millis();
  unsigned long elapsed = now - lastSampleMs;
  if (elapsed < SAMPLE_INTERVAL_MS) return;
  if (PULSES_PER_LITER <= 0.0f) return; // Never send fictitious readings.
  noInterrupts();
  unsigned long count = pulseCount;
  pulseCount = 0;
  interrupts();
  float flowLpm = (count / PULSES_PER_LITER) * (60000.0f / elapsed);
  Serial.print(",LINE-1,");
  Serial.print(flowLpm, 3);
  Serial.println(","); // pressure intentionally blank
  lastSampleMs = now;
}
