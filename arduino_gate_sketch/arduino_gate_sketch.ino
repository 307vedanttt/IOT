/*
 * ==============================================================================
 * Project: PPE Compliance Gate System — Arduino Uno Firmware v3.0
 * File:    arduino_gate_sketch.ino
 * Board:   Arduino Uno (ATmega328P)
 * Author:  Embedded Systems & Python Integration Engineering
 * ==============================================================================
 *
 * HARDWARE CONNECTIONS:
 * ------------------------------------------------------------------------------
 *  Component                  Arduino Pin       Notes
 * ------------------------------------------------------------------------------
 *  Servo Motor (Signal)       Digital Pin 6     PWM capable pin (Orange/Yellow wire)
 *  Green LED (Access Granted) Digital Pin 8     Via 220-ohm current limiting resistor
 *  Red LED (Access Denied)    Digital Pin 9     Via 220-ohm current limiting resistor
 *  Active Buzzer (Alarm)      Digital Pin 10    5V Active Buzzer (pure digitalWrite)
 *  HC-SR04 Trigger            Digital Pin 4     10 microsecond trigger pulse
 *  HC-SR04 Echo               Digital Pin 5     Measures ultrasonic return pulse
 *  I2C 16x2 LCD (SDA)         Analog Pin A4     Standard Uno I2C Data line
 *  I2C 16x2 LCD (SCL)         Analog Pin A5     Standard Uno I2C Clock line
 * ------------------------------------------------------------------------------
 *
 * SPECIFICATION & BEHAVIOR:
 *  1. BUZZER (5V Active Buzzer):
 *     - Completely SILENT on boot/startup and USB connection.
 *     - Completely SILENT on Access Granted, Idle, and Checking states.
 *     - Buzzes ONLY on ACCESS DENIED:
 *         * Helmet Missing ('H')   : Exactly 3 distinct audible beeps.
 *         * Vest Missing ('V')     : Exactly 3 distinct audible beeps.
 *         * Both Missing ('R')     : Exactly 4 distinct audible beeps.
 *     - Pure non-blocking digitalWrite() implementation (zero tone() interference).
 *     - Deduplicated: Repeated identical denial commands do NOT restart alarm.
 *     - Transitions to Idle ('I'), Checking ('C'), or Granted ('G') silence buzzer immediately.
 *
 *  2. GATE BARRIER (Servo Motor on Pin 6):
 *     - Default at start / Idle / Checking / Denied: 0 degrees (Closed).
 *     - Access Granted ('G'):
 *         * Takes exactly 1.10 seconds to smoothly glide from 0 to 90 degrees.
 *         * Rests stationary at 90 degrees for exactly 15.0 seconds for worker entry.
 *         * Takes exactly 1.10 seconds to smoothly glide back from 90 to 0 degrees.
 *     - Math for Viva:
 *         * Angular range = 90 degrees (strictly 0 to 90, never 180).
 *         * Sweep time = 1.10s = 1,100,000 microseconds.
 *         * Step rate = 1,100,000 us / 90 deg = 12,222 us per 1-degree increment.
 *     - Repeated 'G' while gate is open or moving does NOT restart or extend timer.
 *     - Repeated 'G' after closure cannot reopen without a new Checking ('C') cycle.
 *
 *  3. STATUS LEDS:
 *     - Initial state: Both LEDs OFF.
 *     - Mutually exclusive at all times:
 *         * Access Granted: Green LED ON, Red LED OFF.
 *         * Access Denied: Red LED ON, Green LED OFF.
 *         * Idle / Checking: Both LEDs OFF.
 *
 *  4. I2C 16x2 LCD DISPLAY:
 *     - Auto-detects address 0x27 or 0x3F with I2C bus recovery and timeout protection.
 *     - Operates gracefully in headless mode if LCD is disconnected.
 *     - Flicker-free differential line updates (pads to 16 chars, no full-screen clears).
 *     - Messages:
 *         * Idle:            "PPE Entry Gate  " / "Standby / Ready "
 *         * Checking:        "Checking PPE    " / "Please Standby.."
 *         * Access Granted:  "ACCESS GRANTED  " / "PPE COMPLIANT   "
 *         * Helmet Missing:  "ACCESS DENIED!  " / "Helmet Missing  "
 *         * Vest Missing:    "ACCESS DENIED!  " / "Vest Missing    "
 *         * Both Missing:    "ACCESS DENIED!  " / "No Helmet & Vest"
 *
 *  5. HC-SR04 ULTRASONIC SENSOR:
 *     - Bounded 18ms pulseIn timeout (~300cm range) to avoid blocking main loop.
 *     - Telemetry format: "D:<distance_cm>\n" every 150ms.
 * ==============================================================================
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Servo.h>

// ==============================================================================
// CONFIGURATION CONSTANTS & PIN DEFINITIONS
// ==============================================================================
const int PIN_SERVO_SIGNAL    = 6;
const int PIN_LED_GREEN       = 8;
const int PIN_LED_RED         = 9;
const int PIN_BUZZER          = 10;
const int PIN_ULTRASONIC_TRIG = 4;
const int PIN_ULTRASONIC_ECHO = 5;
const int PIN_I2C_SDA         = A4;
const int PIN_I2C_SCL         = A5;

// Configurable Servo Angles (Strictly 0 to 90 degrees)
const int SERVO_CLOSED_ANGLE = 0;   // Gate barrier closed (0 degrees)
const int SERVO_OPEN_ANGLE   = 90;  // Gate barrier open (90 degrees)

// Precise Timing Constants (Non-blocking via micros() & millis())
// Sweep: 90 degrees in 1.10 seconds = 1,100,000 us / 90 deg = 12,222 microseconds per degree
const unsigned long SERVO_STEP_INTERVAL_US = 12222UL; // Exactly 1.10s total sweep time
const unsigned long GATE_OPEN_DURATION_MS  = 15000UL; // Exactly 15.0 seconds rest at 90 degrees
const unsigned long ULTRASONIC_INTERVAL_MS = 150;     // Telemetry every 150ms
const unsigned long BUZZER_BEEP_ON_MS      = 120;     // Active buzzer ON duration (ms)
const unsigned long BUZZER_BEEP_OFF_MS     = 100;     // Active buzzer OFF duration (ms)

// System State Enum
enum SystemState {
  STATE_IDLE,
  STATE_CHECKING,
  STATE_GRANTED,
  STATE_DENIED_HELMET,
  STATE_DENIED_VEST,
  STATE_DENIED_BOTH
};

// Global Runtime Variables
SystemState currentState    = STATE_IDLE;
SystemState lastDenialState = STATE_IDLE; // Deduplication for denial buzzer
bool isGateOpen             = false;
unsigned long gateOpenTimestamp = 0;
bool grantArmed             = true;       // Set on 'C' or 'I'; cleared on 'G' or denial
unsigned long lastDistanceReadingTime = 0;

// Smooth Servo Runtime Variables (1.10s sweep, 15s rest at 90 deg)
int currentServoAngle = SERVO_CLOSED_ANGLE;
int targetServoAngle  = SERVO_CLOSED_ANGLE;
unsigned long lastServoStepTimeUs = 0;
bool gateIsRestingAt90 = false;
bool gateIsClosing     = false;

// LCD Management
LiquidCrystal_I2C* lcdPtr = nullptr;
bool lcdAvailable = false;
byte lcdAddress   = 0x27;
char cachedLcdLine1[17] = "";
char cachedLcdLine2[17] = "";

Servo gateServo;

// Non-blocking Active Buzzer Generator (pure digitalWrite)
bool buzzerRunning        = false;
bool buzzerIsSounding     = false;
int  buzzerTotalBeeps     = 0;
int  buzzerCurrentBeep    = 0;
unsigned long buzzerPhaseStartTime = 0;

// ==============================================================================
// FORWARD DECLARATIONS
// ==============================================================================
void initLcdSafe();
void updateLcd(const char* line1, const char* line2);
void setGate(bool open);
void startBuzzerPattern(int beeps);
void silenceBuzzer();
void updateBuzzerService();
int  readUltrasonicDistanceCm();
void processSerialCommand(char cmd);
void applyState(SystemState newState);

// ==============================================================================
// SETUP ROUTINE (Silent Startup, Clean Initialization)
// ==============================================================================
void setup() {
  Serial.begin(9600);

  // 1. Configure Pin Modes
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_ULTRASONIC_TRIG, OUTPUT);
  pinMode(PIN_ULTRASONIC_ECHO, INPUT);

  // 2. Initial State: Both LEDs OFF, Buzzer strictly SILENT
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  silenceBuzzer();
  digitalWrite(PIN_ULTRASONIC_TRIG, LOW);

  // 3. Servo starts strictly at 0 degrees (Closed)
  gateServo.attach(PIN_SERVO_SIGNAL);
  currentServoAngle = SERVO_CLOSED_ANGLE;
  targetServoAngle  = SERVO_CLOSED_ANGLE;
  gateServo.write(SERVO_CLOSED_ANGLE);
  isGateOpen        = false;
  gateIsRestingAt90 = false;
  gateIsClosing     = false;
  lastServoStepTimeUs = micros();

  // 4. Initialize LCD safely without CPU lockup
  initLcdSafe();

  // 5. Default to IDLE Standby
  applyState(STATE_IDLE);

  Serial.println(F("[SYSTEM READY] PPE Gate Controller v3.0 operational at 9600 baud."));
}

// ==============================================================================
// FAILSAFE I2C LCD INITIALIZATION & BUS RECOVERY
// ==============================================================================
void initLcdSafe() {
  // 1. Standard 9-clock I2C Bus Recovery:
  // Frees any slave device that may have hung mid-transaction holding SDA low.
  pinMode(PIN_I2C_SCL, OUTPUT);
  pinMode(PIN_I2C_SDA, INPUT_PULLUP);
  for (int i = 0; i < 9; i++) {
    digitalWrite(PIN_I2C_SCL, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_I2C_SCL, LOW);
    delayMicroseconds(10);
  }
  digitalWrite(PIN_I2C_SCL, HIGH);
  delayMicroseconds(10);

  // 2. Start I2C bus with hardware timeout protection if supported by AVR core
  Wire.begin();
  #if defined(WIRE_HAS_TIMEOUT)
  Wire.setWireTimeout(25000UL, true); // 25ms timeout, resets bus if blocked
  #endif

  // 3. Probe addresses 0x27 and 0x3F
  byte targetAddresses[] = {0x27, 0x3F};
  lcdAvailable = false;

  for (byte i = 0; i < 2; i++) {
    byte addr = targetAddresses[i];
    Wire.beginTransmission(addr);
    byte error = Wire.endTransmission();
    if (error == 0) {
      lcdAddress = addr;
      lcdAvailable = true;
      break;
    }
  }

  // 4. Instantiate and initialize LCD if present
  if (lcdAvailable) {
    if (lcdPtr != nullptr) {
      delete lcdPtr;
      lcdPtr = nullptr;
    }
    lcdPtr = new LiquidCrystal_I2C(lcdAddress, 16, 2);
    if (lcdPtr != nullptr) {
      lcdPtr->init();
      lcdPtr->backlight();
      lcdPtr->clear();
      memset(cachedLcdLine1, 0, sizeof(cachedLcdLine1));
      memset(cachedLcdLine2, 0, sizeof(cachedLcdLine2));
      updateLcd("PPE Entry Gate", "Standby / Ready");
    } else {
      lcdAvailable = false;
    }
  } else {
    Serial.println(F("[LCD INFO] LCD backpack not responding at 0x27 or 0x3F. Continuing without LCD."));
  }
}

// ==============================================================================
// MAIN SUPER-LOOP (Fully Non-Blocking Architecture)
// ==============================================================================
void loop() {
  unsigned long now = millis();
  unsigned long nowUs = micros();

  // Task 0: Smooth Non-Blocking Servo Stepping (Takes exactly 1.10s to open, 1.10s to close)
  if (nowUs - lastServoStepTimeUs >= SERVO_STEP_INTERVAL_US) {
    lastServoStepTimeUs = nowUs;
    if (currentServoAngle < targetServoAngle) {
      currentServoAngle++;
      gateServo.write(currentServoAngle);

      // Reached 90 degrees: Begin the 15-second rest duration
      if (currentServoAngle >= SERVO_OPEN_ANGLE) {
        currentServoAngle = SERVO_OPEN_ANGLE;
        gateIsRestingAt90 = true;
        gateOpenTimestamp = millis(); // 15 seconds rest starts NOW!
      }
    } else if (currentServoAngle > targetServoAngle) {
      currentServoAngle--;
      gateServo.write(currentServoAngle);

      // Reached 0 degrees: Gate closure completed
      if (currentServoAngle <= SERVO_CLOSED_ANGLE) {
        currentServoAngle = SERVO_CLOSED_ANGLE;
        if (gateIsClosing) {
          gateIsClosing = false;
          isGateOpen    = false;
          digitalWrite(PIN_LED_GREEN, LOW);
          applyState(STATE_IDLE);
          grantArmed = false;
        }
      }
    }
  }

  // Task 1: Check Serial Input from Python
  while (Serial.available() > 0) {
    char incomingChar = (char)Serial.read();
    if (incomingChar != '\r' && incomingChar != '\n' && incomingChar != ' ') {
      processSerialCommand(incomingChar);
    }
  }

  // Task 2: 15-Second Rest Timer at 90 Degrees
  // Once the barrier has rested at 90 degrees for exactly 15 seconds, initiate smooth 1.10s close
  if (isGateOpen && gateIsRestingAt90 && (now - gateOpenTimestamp >= GATE_OPEN_DURATION_MS)) {
    gateIsRestingAt90 = false;
    gateIsClosing     = true;
    targetServoAngle  = SERVO_CLOSED_ANGLE; // Smoothly glide back to 0 degrees over 1.10s
  }

  // Task 3: Periodic Ultrasonic Distance Telemetry (Every 150ms)
  if (now - lastDistanceReadingTime >= ULTRASONIC_INTERVAL_MS) {
    lastDistanceReadingTime = now;
    int distance = readUltrasonicDistanceCm();
    if (distance >= 2 && distance <= 400) {
      Serial.print(F("D:"));
      Serial.println(distance);
    }
  }

  // Task 4: Service Non-blocking Buzzer Pattern
  updateBuzzerService();
}

// ==============================================================================
// SERIAL COMMAND PROCESSOR
// ==============================================================================
void processSerialCommand(char cmd) {
  // CRITICAL INTERLOCK:
  // When the barrier is open or cycling (isGateOpen == true or currentServoAngle > 0),
  // access has been granted for worker entry.
  // DO NOT allow camera checking ('C'), background idle pulses ('I'), repeated grants ('G'),
  // or vision denials ('H','V','R') to cut short the 15-second passage window!
  if (isGateOpen || currentServoAngle > SERVO_CLOSED_ANGLE) {
    return; // 15-second worker entry window is strictly protected!
  }

  switch (cmd) {
    case 'I': // Idle / Standby
      applyState(STATE_IDLE);
      break;

    case 'C': // Checking PPE
      applyState(STATE_CHECKING);
      break;

    case 'G': // Access Granted
      applyState(STATE_GRANTED);
      break;

    case 'H': // Access Denied: Helmet Missing
      applyState(STATE_DENIED_HELMET);
      break;

    case 'V': // Access Denied: Safety Vest Missing
      applyState(STATE_DENIED_VEST);
      break;

    case 'R': // Access Denied: Both Missing / Uncertain
      applyState(STATE_DENIED_BOTH);
      break;

    default:
      break;
  }
}

// ==============================================================================
// STATE MACHINE LOGIC & PERIPHERAL ACTUATION
// ==============================================================================
void applyState(SystemState newState) {
  switch (newState) {
    // --------------------------------------------------------------------------
    // 1. IDLE STANDBY ('I')
    // Both LEDs OFF, Buzzer SILENT, Motor returns to 0 degrees, LCD Standby
    // --------------------------------------------------------------------------
    case STATE_IDLE:
      currentState    = STATE_IDLE;
      lastDenialState = STATE_IDLE;
      grantArmed      = true;            // Arm grant for upcoming verification cycle
      setGate(false);                    // Smoothly close motor to 0 degrees
      digitalWrite(PIN_LED_GREEN, LOW);  // Both LEDs OFF
      digitalWrite(PIN_LED_RED, LOW);
      silenceBuzzer();                   // Buzzer completely SILENT
      updateLcd("PPE Entry Gate", "Standby / Ready");
      break;

    // --------------------------------------------------------------------------
    // 2. CHECKING PPE ('C')
    // Both LEDs OFF, Buzzer SILENT, Motor locked at 0 degrees, LCD Checking
    // --------------------------------------------------------------------------
    case STATE_CHECKING:
      currentState    = STATE_CHECKING;
      lastDenialState = STATE_IDLE;
      grantArmed      = true;            // Arm grant for upcoming decision
      setGate(false);                    // Motor remains at 0 degrees
      digitalWrite(PIN_LED_GREEN, LOW);  // Both LEDs OFF
      digitalWrite(PIN_LED_RED, LOW);
      silenceBuzzer();                   // Buzzer completely SILENT
      updateLcd("Checking PPE", "Please Standby..");
      break;

    // --------------------------------------------------------------------------
    // 3. ACCESS GRANTED ('G')
    // Green LED ON, Red LED OFF, Motor smoothly glides to 90 degrees in 1.10s,
    // rests for 15.0 seconds, then glides back to 0 degrees in 1.10s. Buzzer SILENT.
    // LCD displays "ACCESS GRANTED" on Line 1, "PPE COMPLIANT" on Line 2
    // --------------------------------------------------------------------------
    case STATE_GRANTED:
      // Requirement: Repeated 'G' commands while open or moving must NOT reset or extend timer!
      if (isGateOpen || currentServoAngle > SERVO_CLOSED_ANGLE) {
        return;
      }

      currentState      = STATE_GRANTED;
      lastDenialState   = STATE_IDLE;
      setGate(true);                      // Initiate smooth 1.10s glide to 90 degrees
      digitalWrite(PIN_LED_GREEN, HIGH);  // ONLY Green LED ON
      digitalWrite(PIN_LED_RED, LOW);     // Red LED OFF
      silenceBuzzer();                    // NO BUZZER on Access Granted
      updateLcd("ACCESS GRANTED", "PPE COMPLIANT");
      break;

    // --------------------------------------------------------------------------
    // 4. ACCESS DENIED: HELMET MISSING ('H')
    // Red LED ON, Green LED OFF, Motor locked at 0 degrees, 3 audible beeps
    // --------------------------------------------------------------------------
    case STATE_DENIED_HELMET:
      grantArmed = false;                 // Denial disarms pending grant
      setGate(false);                     // Motor remains at 0 degrees
      digitalWrite(PIN_LED_GREEN, LOW);   // Green LED OFF
      digitalWrite(PIN_LED_RED, HIGH);    // ONLY Red LED ON
      updateLcd("ACCESS DENIED!", "Helmet Missing");

      // Deduplicate: start alarm only on fresh event
      if (currentState != STATE_DENIED_HELMET || lastDenialState != STATE_DENIED_HELMET) {
        startBuzzerPattern(3);
      }
      currentState    = STATE_DENIED_HELMET;
      lastDenialState = STATE_DENIED_HELMET;
      break;

    // --------------------------------------------------------------------------
    // 5. ACCESS DENIED: VEST MISSING ('V')
    // Red LED ON, Green LED OFF, Motor locked at 0 degrees, 3 audible beeps
    // --------------------------------------------------------------------------
    case STATE_DENIED_VEST:
      grantArmed = false;
      setGate(false);
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_RED, HIGH);
      updateLcd("ACCESS DENIED!", "Vest Missing");

      // Deduplicate: start alarm only on fresh event
      if (currentState != STATE_DENIED_VEST || lastDenialState != STATE_DENIED_VEST) {
        startBuzzerPattern(3);
      }
      currentState    = STATE_DENIED_VEST;
      lastDenialState = STATE_DENIED_VEST;
      break;

    // --------------------------------------------------------------------------
    // 6. ACCESS DENIED: BOTH MISSING ('R')
    // Red LED ON, Green LED OFF, Motor locked at 0 degrees, 4 audible beeps
    // --------------------------------------------------------------------------
    case STATE_DENIED_BOTH:
      grantArmed = false;
      setGate(false);
      digitalWrite(PIN_LED_GREEN, LOW);
      digitalWrite(PIN_LED_RED, HIGH);
      updateLcd("ACCESS DENIED!", "No Helmet & Vest");

      // Deduplicate: start alarm only on fresh event
      if (currentState != STATE_DENIED_BOTH || lastDenialState != STATE_DENIED_BOTH) {
        startBuzzerPattern(4);
      }
      currentState    = STATE_DENIED_BOTH;
      lastDenialState = STATE_DENIED_BOTH;
      break;
  }
}

// ==============================================================================
// SERVO BARRIER CONTROL (0 deg = Closed, 90 deg = Open)
// ==============================================================================
void setGate(bool open) {
  if (open) {
    targetServoAngle  = SERVO_OPEN_ANGLE;   // Glide slowly to 90 degrees (strictly 90 max)
    isGateOpen        = true;
    gateIsRestingAt90 = false;
    gateIsClosing     = false;
  } else {
    targetServoAngle  = SERVO_CLOSED_ANGLE; // Glide slowly to 0 degrees
    gateIsRestingAt90 = false;
    if (currentServoAngle > SERVO_CLOSED_ANGLE) {
      gateIsClosing = true;
    } else {
      isGateOpen    = false;
      gateIsClosing = false;
    }
  }
}

// ==============================================================================
// ACTIVE BUZZER CONTROL (Pure Non-Blocking digitalWrite)
// ==============================================================================
void startBuzzerPattern(int beeps) {
  buzzerTotalBeeps      = beeps;
  buzzerCurrentBeep     = 0;
  buzzerIsSounding      = true;
  buzzerRunning         = true;
  buzzerPhaseStartTime  = millis();
  digitalWrite(PIN_BUZZER, HIGH); // Sound first beep immediately
}

void silenceBuzzer() {
  digitalWrite(PIN_BUZZER, LOW);
  buzzerRunning         = false;
  buzzerIsSounding      = false;
  buzzerTotalBeeps      = 0;
  buzzerCurrentBeep     = 0;
}

void updateBuzzerService() {
  if (!buzzerRunning) {
    return;
  }

  unsigned long now = millis();

  if (buzzerIsSounding) {
    // Current beep sounding phase
    if (now - buzzerPhaseStartTime >= BUZZER_BEEP_ON_MS) {
      digitalWrite(PIN_BUZZER, LOW); // End active pulse
      buzzerIsSounding = false;
      buzzerPhaseStartTime = now;
      buzzerCurrentBeep++;

      if (buzzerCurrentBeep >= buzzerTotalBeeps) {
        buzzerRunning = false; // All beeps completed
      }
    }
  } else {
    // Silent interval between beeps
    if (now - buzzerPhaseStartTime >= BUZZER_BEEP_OFF_MS) {
      digitalWrite(PIN_BUZZER, HIGH); // Begin next beep
      buzzerIsSounding = true;
      buzzerPhaseStartTime = now;
    }
  }
}

// ==============================================================================
// HC-SR04 ULTRASONIC SENSOR DRIVER (Bounded 18ms pulseIn)
// ==============================================================================
int readUltrasonicDistanceCm() {
  digitalWrite(PIN_ULTRASONIC_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_ULTRASONIC_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_ULTRASONIC_TRIG, LOW);

  // Bounded timeout: 18000us corresponds to ~309cm maximum range.
  // Bounding prevents worst-case execution delays on missed echo.
  unsigned long durationUs = pulseIn(PIN_ULTRASONIC_ECHO, HIGH, 18000UL);

  if (durationUs == 0) {
    return -1; // Out of range or no echo return
  }

  int distanceCm = (int)(durationUs / 58.2);
  return distanceCm;
}

// ==============================================================================
// FLICKER-FREE I2C LCD HELPER (Differential Line Update)
// ==============================================================================
void updateLcd(const char* line1, const char* line2) {
  if (!lcdAvailable || lcdPtr == nullptr) {
    return;
  }

  char buf1[17];
  char buf2[17];
  snprintf(buf1, sizeof(buf1), "%-16.16s", line1 ? line1 : "");
  snprintf(buf2, sizeof(buf2), "%-16.16s", line2 ? line2 : "");

  // Update Line 1 only if content has changed
  if (strncmp(cachedLcdLine1, buf1, 16) != 0) {
    lcdPtr->setCursor(0, 0);
    lcdPtr->print(buf1);
    strncpy(cachedLcdLine1, buf1, sizeof(cachedLcdLine1));
  }

  // Update Line 2 only if content has changed
  if (strncmp(cachedLcdLine2, buf2, 16) != 0) {
    lcdPtr->setCursor(0, 1);
    lcdPtr->print(buf2);
    strncpy(cachedLcdLine2, buf2, sizeof(cachedLcdLine2));
  }
}
