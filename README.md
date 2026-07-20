# ErgoMax – B2B Smart Posture Correction System

> **Business-Engineering-Technology (BET) Capstone Project**  
> *Auburn University Study Abroad | Pamplona, Spain (Summer 2026)*  

---

## Overview
**ErgoMax** is an integrated hardware-software solution designed to reduce workplace musculoskeletal fatigue through real-time posture telemetry and continuous ergonomic feedback. 

Developed as a B2B product concept and functional prototype, ErgoMax pairs chair-mounted multi-sensor arrays with embedded classification firmware to evaluate real-time spine alignment and provide instant feedback to prevent strain.

---

## Key System Features

### Hardware & Firmware Engineering
* **Multi-Sensor Telemetry:** Custom sensor placement array designed to evaluate lumbar and upper-back alignment during active sitting.
* **Real-Time Embedded Processing:** C/C++ firmware executing posture-classification algorithms directly on incoming sensor data with low latency.
* **Low-Power Telemetry:** Optimized sampling rates and hardware logic for efficient continuous operation.

### Commercial & B2B Strategy
* **Enterprise Go-To-Market:** Tailored for B2B integration into corporate wellness programs and ergonomic furniture manufacturers.
* **Unit Economics Model:** Complete Bill of Materials (BOM) cost structure, hardware margin analysis, and enterprise licensing projections.
* **Investor Pitch Package:** Financial modeling, executive pitch deck, and market analysis presented in Pamplona, Spain.

---

## System Architecture

```text
[ Sensor Array ] ---> [ ADC / Microcontroller ] ---> [ Firmware Algorithm ] ---> [ Desktop App / User Interface ]
 (Lumbar / Spine)         (Signal Prep)              (Posture State Rules)         (Visual / Haptic)