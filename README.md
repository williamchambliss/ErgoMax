# ErgoMax – B2B Smart Posture Correction System

> **Business-Engineering-Technology (BET) Capstone Project**  
> *Auburn University Study Abroad | Pamplona, Spain (Summer 2026)*  

---

## Overview
**PostureMax by ErgoMax** is an integrated hardware-software platform engineered to eliminate workplace musculoskeletal fatigue through real-time posture telemetry, haptic retraining, and automated ergonomic coaching[cite: 1]. Addressing an estimated **$353 billion** annual corporate loss from musculoskeletal disorders[cite: 1], ErgoMax delivers an affordable 3-strap retrofit array that converts standard office chairs into continuous biometric tracking hubs[cite: 1].

---

## Key System Features

### Hardware & Embedded Firmware
* **4-Node FSR Topology:** Custom 3-strap array targeting lower lumbar ($L$), mid-back ($MB$), and upper thoracic ($UB_L$, $UB_R$) zones[cite: 1].
* **Real-Time Embedded Processing:** Low-latency C/C++ firmware executing posture state classification and sitting endurance algorithms[cite: 1].
* **Dual Feedback Modes:** Active mode with localized haptic vibration alerts and passive mode for distraction-free telemetry logging[cite: 1].
* **Hardware Roadmap:** Functional Arduino UNO R4 WiFi prototype transitioning to a custom surface-mount ESP32-S3 PCB[cite: 1].

### Desktop Companion Application
* **Daily Posture Score (0–100):** Weighted scoring model based on **60%** active posture alignment and **40%** movement break compliance[cite: 1].
* **Spinal Alignment Map & Symmetry Index:** Real-time 4-node contact visualizer and 5-minute rolling left-to-right shoulder load telemetry[cite: 1].
* **Interactive Posture Coach:** Step-by-step guided 60-second desk stretches (*Sagittal Pelvic Micro-Tilts*, *Scapular Resets*) with automated timers[cite: 1].
* **Setup & Calibration Wizard:** Onboarding UI for physical strap setup, dynamic forward-lean software thresholds, and multi-user profile management[cite: 1].

### Commercial & B2B Strategy
* **Universal Retrofit Focus:** High-retention, non-intrusive form factor bypassing expensive smart chairs ($500–$1,000+) and high-friction adhesive wearables[cite: 1].
* **Target Unit Economics:** Target MSRP of **$89.00** against a scaled COGS of **$22.50** (**75%** gross margin target)[cite: 1].
* **Enterprise Deployment:** Standard 250-chair enterprise pilot bundle yielding an average deal value of **$22,250**[cite: 1].

---

## System Architecture

```text
[ 4-Node FSR Grid ] ---> [ Microcontroller / ADC ] ---> [ Embedded Firmware ] ---> [ BLE / Serial ] ---> [ Desktop Companion App ]
(Lumbar/Mid/Upper)       (Signal Conditioning)           (Posture Rules)                                 (Map & Analytics)
                                                                │
                                                                v
                                                     [ Localized Haptics ]
                                                     (Wave / Continuous)
```[cite: 1]

---
```
## Expert Validation & Team

### Clinical & Academic Advisors
* **Dr. Baweja (Director, Auburn PT Program):** Validated sensorimotor retraining concept; recommended 3rd mid-back strap to cover 95th percentile posture models[cite: 1].
* **Dr. Ballesteros (UPNA):** Approved sensor topology; recommended dynamic forward-lean thresholds, dual Active/Passive data tracking, and medical data exporting[cite: 1].
* **Holli Michaels & Dr. Ficken:** Guided app navigation hierarchy, live guided stretches, and packaging user guides[cite: 1].

### Executive Team
* **William Chambliss** – Team Lead / CEO[cite: 1]
* **George Lewis** – Chief Technology Officer (CTO)[cite: 1]
* **Aliza Ziauddin** – Chief Operating Officer / Chief Financial Officer (COO/CFO)[cite: 1]
* **Julia Downs** – Chief Product Officer (CPO)[cite: 1]
* **Tyler Wadlington** – Chief Revenue Officer (CRO)[cite: 1]
