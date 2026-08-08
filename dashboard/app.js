/*
app.js — Dashboard UI Logic and Firebase Listeners
*/

// ==========================================
// 1. DOM Elements
// ==========================================
const loginScreen = document.getElementById('login-screen');
const dashboardScreen = document.getElementById('dashboard-screen');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const logoutBtn = document.getElementById('logout-btn');

const safetyBanner = document.getElementById('safety-banner');
const safetyText = document.getElementById('safety-text');
const safetyTemp = document.getElementById('safety-temp');
const safetyGas = document.getElementById('safety-gas');
const safetyHum = document.getElementById('safety-hum');

const insideCount = document.getElementById('inside-count');
const insideList = document.getElementById('inside-list');
const mismatchList = document.getElementById('mismatch-list');
const eventsBody = document.getElementById('events-body');

const searchInput = document.getElementById('search-input');
const exportCsvBtn = document.getElementById('export-csv-btn');

// State for filtering and export
let allEventsArray = []; // Store the raw events for filtering

// ==========================================
// 2. Authentication Logic
// ==========================================
auth.onAuthStateChanged((user) => {
    if (user) {
        // Logged in
        loginScreen.classList.add('hidden');
        dashboardScreen.classList.remove('hidden');
        document.getElementById('admin-status').innerText = `Logged in as ${user.email}`;
        
        // Start listening to data now that we are authenticated
        initDatabaseListeners();
    } else {
        // Logged out
        loginScreen.classList.remove('hidden');
        dashboardScreen.classList.add('hidden');
    }
});

loginForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    auth.signInWithEmailAndPassword(email, password)
        .catch((error) => {
            loginError.innerText = error.message;
            loginError.classList.remove('hidden');
        });
});

logoutBtn.addEventListener('click', () => {
    auth.signOut();
});

// ==========================================
// 3. Database Listeners (Real-time updates)
// ==========================================
function initDatabaseListeners() {
    
    // --- Safety Readings Listener ---
    const safetyRef = db.ref('safety_readings/lab_1');
    safetyRef.on('value', (snapshot) => {
        const data = snapshot.val();
        if (data) {
            safetyTemp.innerText = data.temperature;
            safetyGas.innerText = data.gas_level;
            safetyHum.innerText = data.humidity;
            
            if (data.alert_status === "ALERT" || data.alert_status === "DANGER") {
                safetyBanner.className = "banner banner-alert";
                safetyText.innerText = `ALERT TRIGGERED! (${data.alert_status})`;
            } else {
                safetyBanner.className = "banner banner-normal";
                safetyText.innerText = "Normal";
            }
        }
    });

    // --- Mismatch Logs Listener ---
    const mismatchRef = db.ref('mismatch_logs').orderByChild('timestamp').limitToLast(50);
    mismatchRef.on('value', (snapshot) => {
        const logs = [];
        snapshot.forEach((child) => { logs.push(child.val()); });
        logs.reverse(); // Newest first
        
        mismatchList.innerHTML = '';
        if (logs.length === 0) {
            mismatchList.innerHTML = '<tr><td class="empty-state">No mismatches logged.</td></tr>';
            return;
        }
        
        logs.forEach(log => {
            const tr = document.createElement('tr');
            const timeStr = new Date(log.timestamp).toLocaleTimeString();
            tr.innerHTML = `
                <td>
                    <strong>${log.scanned_card_id}</strong><br>
                    <span class="text-danger">${log.reason}</span><br>
                    <span class="text-muted">${timeStr}</span>
                </td>
            `;
            mismatchList.appendChild(tr);
        });
    });

    // --- Attendance Events Listener ---
    const eventsRef = db.ref('attendance_events').orderByChild('timestamp');
    eventsRef.on('value', (snapshot) => {
        allEventsArray = [];
        const studentState = {}; // To track who is inside
        
        snapshot.forEach((child) => {
            const event = child.val();
            allEventsArray.push(event);
            
            // Track state: 'entry' puts them in, 'exit' takes them out
            if (event.event_type === 'entry') {
                studentState[event.student_id] = event; // store the whole event for details
            } else if (event.event_type === 'exit') {
                delete studentState[event.student_id];
            }
        });
        
        // Reverse so newest is first in the feed
        allEventsArray.reverse();
        
        // 1. Update "Currently Inside" panel
        updateCurrentlyInside(studentState);
        
        // 2. Render Feed
        renderEventsFeed(allEventsArray);
    });
}

// ==========================================
// 4. UI Rendering & Interactions
// ==========================================
function updateCurrentlyInside(studentState) {
    insideList.innerHTML = '';
    const studentsInside = Object.values(studentState);
    insideCount.innerText = studentsInside.length;
    
    if (studentsInside.length === 0) {
        insideList.innerHTML = '<tr><td class="empty-state">No students currently in lab.</td></tr>';
        return;
    }
    
    studentsInside.forEach(student => {
        const timeStr = new Date(student.timestamp).toLocaleTimeString();
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <strong>${student.name}</strong> (${student.student_id})<br>
                <span class="text-muted">Entered at ${timeStr}</span>
            </td>
        `;
        insideList.appendChild(tr);
    });
}

function renderEventsFeed(eventsToRender) {
    eventsBody.innerHTML = '';
    if (eventsToRender.length === 0) {
        eventsBody.innerHTML = '<tr><td colspan="4" class="empty-state">No events found.</td></tr>';
        return;
    }
    
    eventsToRender.forEach(event => {
        const tr = document.createElement('tr');
        const timeStr = new Date(event.timestamp).toLocaleString();
        const eventClass = event.event_type === 'entry' ? 'event-entry' : 'event-exit';
        
        tr.innerHTML = `
            <td>${timeStr}</td>
            <td>${event.student_id}</td>
            <td>${event.name}</td>
            <td class="${eventClass}">${event.event_type.toUpperCase()}</td>
        `;
        eventsBody.appendChild(tr);
    });
}

// Search Filter
searchInput.addEventListener('input', (e) => {
    const term = e.target.value.toLowerCase();
    const filtered = allEventsArray.filter(event => {
        return event.name.toLowerCase().includes(term) || 
               event.student_id.toLowerCase().includes(term);
    });
    renderEventsFeed(filtered);
});

// ==========================================
// 5. CSV Export Logic
// ==========================================
exportCsvBtn.addEventListener('click', () => {
    // Determine which events are currently being displayed
    const term = searchInput.value.toLowerCase();
    const eventsToExport = allEventsArray.filter(event => {
        return event.name.toLowerCase().includes(term) || 
               event.student_id.toLowerCase().includes(term);
    });
    
    if (eventsToExport.length === 0) {
        alert("No data to export.");
        return;
    }

    // Build CSV string
    const headers = ["Timestamp", "Student ID", "Name", "Event Type"];
    const rows = eventsToExport.map(e => [
        `"${e.timestamp}"`, 
        `"${e.student_id}"`, 
        `"${e.name}"`, 
        `"${e.event_type}"`
    ]);
    
    const csvContent = [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
    
    // Create Blob and Download Link
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `attendance_export_${new Date().getTime()}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
});
