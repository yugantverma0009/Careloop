# CareLoop Care Team Portal — Known Gaps & Boundary Conditions

This document catalogs known gaps, design compromises, synthetic prototype boundaries, and items intentionally not automated in the current CareLoop Care Team (Doctor & Nurse) Portal.

---

## 1. Intentionally Non-Automated Decisions

| Capability | Current Implementation | Rationale & Safety Boundary |
|:---|:---|:---|
| **LACE Readmission Risk Score (D-20)** | Clinician-entered parameters only | The LACE index has mixed predictive evidence in non-surgical cohorts. Automating score calculation without clinical verification risks false confidence or premature discharge. The UI enforces manual entry and prominently displays the evidence disclaimer. |
| **Pathway Rule Templates (D-13)** | Default threshold values ship completely blank (`None`) | Clinical safety protocol prohibits hardcoded "default" medical cutoffs. An attending doctor must review patient context and manually specify numeric values for each parameter (e.g., Tachycardia cutoff) before saving. |
| **AI Summary Review & Sign-Off (D-08)** | Draft summaries require human clinician approval | Generative models are restricted to drafting text strictly from deterministic fact sheets. Summaries are marked `"AI draft, not reviewed"` until an authorized doctor approves them. |
| **Nurse Alert Rule Updates** | Recorded as proposals requiring doctor review | Nurses can propose adjustments with mandatory justification text ($\ge 5$ characters); direct changes to active patient thresholds are restricted to doctor roles. |

---

## 2. Technical & Integration Gaps

| Area | Current State | Production Roadmap / Gap Description |
|:---|:---|:---|
| **ABDM Gateway Integration** | Synthesizes standard 14-digit ABHA IDs and provides FHIR R4 JSON collection bundles | True national ABDM integration requires onboarding to the National Health Authority (NHA) Sandbox with cryptographic mTLS certificates, Consent Manager hooks, and HIP/HIU bridging. |
| **Wearable Device Gateway** | Python telemetry simulator (`device/simulator.py`) and ESP32 Arduino firmware (`device/esp32_careloop/`) | Telemetry currently posts via HTTP `POST /device/readings`. In high-scale hospital production, an MQTT/CoAP broker (e.g., EMQX or AWS IoT Core) would terminate device streams with mutual TLS. |
| **SMS / Push Delivery** | Logged to database (`notifications`, `escalation_events`, `audit_log`) and displayed in UI | Production deployment requires plugging in a carrier SMS gateway (Twilio, Gupshup, or AWS SNS) with delivery status callbacks. |
| **Multi-Hospital Tenancy** | Single database schema (`careloop`) | All synthetic patients exist within the primary installation. Multi-hospital partitioning would require tenant IDs and cross-tenant row-level isolation policies. |

---

## 3. Data & Schema Compromises

1. **Patient Gender in FHIR Bundles**:
   - The local MySQL `patients` table does not contain a dedicated `gender` column (only `full_name`, `date_of_birth`, `phone_number`, `abha_id`).
   - FHIR R4 exporter safely defaults patient gender to `"unknown"`.
2. **Audit Log Ordering**:
   - The `audit_log` table uses `log_id` (auto-increment) and `created_at`. All audit endpoints order deterministically by `log_id DESC`.
3. **Synthetic Demographic Dataset**:
   - Baseline demonstration uses 5 post-discharge patients (Aarav Patel, Sunita Sharma, Vikram Malhotra, Priya Nair, Rajesh Kumar) with synthetic telemetry and medication schedules.

---

## 4. What Was Not Tested in Automated CI

- **Physical ESP32 Hardware Hardware-in-the-Loop**: Automated test suites test the ingestion API and sensor trigger logic with simulated payloads; physical I2C sensor jitter from the MAX30102 sensor was validated manually on bench hardware.
- **Concurrent 10,000+ Device Streams**: Load testing verified up to 50 concurrent simulated streams; high-volume stress testing beyond 10,000 devices will require distributed Locust/k6 workers.
