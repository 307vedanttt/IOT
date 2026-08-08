# Firebase Realtime Database Schema

This defines the structure of the JSON tree in the Firebase Realtime Database. 
It mirrors the local SQLite events but is structured for fast querying by the web dashboard.

```json
{
  "students": {
    "{student_id}": {
      "name": "Jane Doe",
      "department": "Computer Science",
      "id_card_code": "STU2024001"
      // Note: Raw face embeddings (the 128D numpy arrays) are omitted from the cloud DB 
      // intentionally. They remain strictly in local storage (data/embeddings/) to preserve 
      // student biometric privacy and to save cloud bandwidth.
    }
  },
  
  "attendance_events": {
    "{event_id}": {
      "student_id": "STU2024001",
      "name": "Jane Doe",
      "event_type": "entry",
      "timestamp": "2024-03-20T08:30:15"
    }
  },
  
  "mismatch_logs": {
    "{log_id}": {
      "scanned_card_id": "STU2024001",
      "reason": "face_mismatch",
      "timestamp": "2024-03-20T08:31:00"
    }
  },
  
  "safety_readings": {
    "lab_1": {
      "gas_level": 45.2,
      "temperature": 24.5,
      "humidity": 40.0,
      "timestamp": "2024-03-20T08:35:00",
      "alert_status": "NORMAL"
    }
  }
}
```
