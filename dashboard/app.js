/*
app.js — Dashboard UI Logic and Firebase Listeners
*/

// TODO: Initialize Firebase database reference
// const db = firebase.database();

// DOM Elements
const connStatus = document.getElementById('connection-status');
const currentCountEl = document.getElementById('current-count');
const tableBody = document.getElementById('attendance-body');

// TODO: 1. Listen for connection state changes (.info/connected)
// - Update connStatus text and class (status-online / status-offline)

// TODO: 2. Listen for lab_status/current_count updates (value event)
// - Update currentCountEl.innerText

// TODO: 3. Listen for new attendance logs (child_added on attendance_logs)
// - We might need to listen to all students' logs, or flatten the DB structure 
//   for easier querying (e.g. /logs/ instead of /logs/<student_id>/)
// - On child_added: Create a <tr>, populate cells (time, id, name, event),
//   prepend to tableBody.
// - Limit the table to N rows (e.g., last 50 events).

// TODO: 4. Listen for safety sensor updates (value event on safety_events/latest)
// - Update sensor widgets (temperature, gas) based on incoming mock data.

console.log("Dashboard initialized. Waiting for Firebase connection...");
