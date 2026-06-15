// App state variables
let currentTab = "dashboard";
let coachData = null;
let currentRoutine = null;
let routineTimerInterval = null;
let updateInterval = null;

// DOM ready initialization
document.addEventListener("DOMContentLoaded", () => {
  setupNavigation();
  setupEventListeners();
  setupAccordions();
  
  // Wait for pywebview to initialize, then fetch data
  if (window.pywebview && window.pywebview.api) {
    initApp();
  } else {
    window.addEventListener('pywebviewready', initApp);
  }
});

function initApp() {
  fetchInitialData();
  // Start periodic update loop (every 1 second)
  if (!updateInterval) {
    updateInterval = setInterval(pollDashboardData, 1000);
  }
}


// Setup sidebar tab navigation
function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item");
  const tabContents = document.querySelectorAll(".tab-content");

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const tab = item.getAttribute("data-tab");
      
      navItems.forEach(i => i.classList.remove("active"));
      tabContents.forEach(tc => tc.classList.remove("active"));

      item.classList.add("active");
      document.getElementById(`tab-${tab}`).classList.add("active");
      
      currentTab = tab;
      
      if (tab === "history") {
        renderHistoryChart();
      }
    });
  });
}

// Bind UI controls to python backend actions
function setupEventListeners() {
  // Calibration
  document.getElementById("btn-calibrate").addEventListener("click", () => {
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.calibrate_baseline().then(res => {
        console.log("Calibration started:", res);
        startCalibrationCountdown();
      });
    }
  });

  // Haptics intensity
  const intensitySlider = document.getElementById("haptic-intensity");
  const intensityVal = document.getElementById("intensity-val");
  
  intensitySlider.addEventListener("input", (e) => {
    const val = e.target.value;
    const pct = Math.round((val / 255) * 100);
    intensityVal.innerText = `${pct}%`;
  });

  intensitySlider.addEventListener("change", (e) => {
    const val = parseInt(e.target.value);
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.set_haptic_intensity(val);
    }
  });

  // Haptic alert mode
  document.getElementById("haptic-mode").addEventListener("change", (e) => {
    const mode = e.target.value;
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.set_haptic_mode(mode);
    }
  });

  // Windows startup checkbox
  document.getElementById("chk-startup").addEventListener("change", (e) => {
    const active = e.target.checked;
    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.toggle_startup_setting(active);
    }
  });

  // Next insight tips
  document.getElementById("btn-next-insight").addEventListener("click", rotateInsight);

  // Close active routine
  document.getElementById("btn-stop-routine").addEventListener("click", endRoutine);
}

// Accordion list collapse toggles
function setupAccordions() {
  const headers = document.querySelectorAll(".accordion-header");
  headers.forEach(header => {
    header.addEventListener("click", () => {
      const content = header.nextElementSibling;
      content.classList.toggle("open");
    });
  });
}

// Fetch content libraries and settings from DB layer
function fetchInitialData() {
  if (!window.pywebview || !window.pywebview.api) return;

  // 1. Get coach content library
  window.pywebview.api.get_coach_resources().then(data => {
    coachData = data;
    renderCoachResources();
  });

  // 2. Get saved setup state (e.g. startup registry toggle value, intensity)
  window.pywebview.api.get_settings().then(settings => {
    if (settings) {
      document.getElementById("chk-startup").checked = settings.startup_launch || false;
      document.getElementById("haptic-intensity").value = settings.haptic_intensity || 128;
      document.getElementById("intensity-val").innerText = `${Math.round(((settings.haptic_intensity || 128) / 255) * 100)}%`;
      document.getElementById("haptic-mode").value = settings.haptic_mode || "wave";
    }
  });
}

// Periodic polling to update dashboard state
function pollDashboardData() {
  if (!window.pywebview || !window.pywebview.api) return;

  window.pywebview.api.get_dashboard_data().then(data => {
    if (!data) return;

    // 1. Update Connection Pills
    updateConnectionUI(data.ble_status);

    // 2. Update Live Monitor Map (Nodes)
    updateSpineMonitor(data.active_sensors, data.current_state);

    // 3. Update Progress Rings (Dashboard)
    updateProgressRing("score-ring", data.daily_score);
    document.getElementById("score-value").innerText = data.daily_score;
    document.getElementById("encouragement-text").innerText = data.encouragement_msg;
    document.getElementById("difficulty-badge").innerText = `${data.difficulty_mode} Mode`;

    // 4. Update Standing Timer
    updateStandingTimerUI(data.sitting_seconds_elapsed, data.sitting_limit_seconds, data.is_standing_break);

    // 5. Update History metrics if user is on History page
    if (currentTab === "history") {
      updateHistoryStatsUI(data.history_stats);
    }
  });
}

// Handle connection states
function updateConnectionUI(status) {
  const pill = document.getElementById("connection-pill");
  const txt = document.getElementById("pill-status-text");
  const setupTxt = document.getElementById("status-ble-text");

  pill.className = "connection-pill";
  setupTxt.className = "";

  if (status === "Connected") {
    pill.classList.add("connected");
    txt.innerText = "Connected";
    setupTxt.innerText = "Connected";
    setupTxt.classList.add("text-connected");
  } else if (status.includes("Scanning") || status.includes("Connecting")) {
    pill.classList.add("scanning");
    txt.innerText = status;
    setupTxt.innerText = status;
    setupTxt.classList.add("text-disconnected");
  } else {
    pill.classList.add("disconnected");
    txt.innerText = "Disconnected";
    setupTxt.innerText = "Disconnected";
    setupTxt.classList.add("text-disconnected");
  }
}

// Color the spine map circles
function updateSpineMonitor(sensors, state) {
  const nodes = {
    "node-ub-l": sensors.UB_L,
    "node-ub-r": sensors.UB_R,
    "node-mb": sensors.MB,
    "node-l": sensors.L
  };

  const diags = {
    "diag-ub-l": sensors.UB_L,
    "diag-ub-r": sensors.UB_R,
    "diag-mb": sensors.MB,
    "diag-l": sensors.L
  };

  // Live dashboard monitor nodes
  for (let id in nodes) {
    const el = document.getElementById(id);
    if (nodes[id]) {
      el.classList.add("active-pressure");
    } else {
      el.classList.remove("active-pressure");
    }
  }

  // Setup diagram SVG dots
  for (let id in diags) {
    const el = document.getElementById(id);
    el.setAttribute("fill", diags[id] ? "#00A896" : "#FF4D4D"); // Teal = pressed, Red = empty
  }

  // State text label
  const stateLabel = document.getElementById("live-state-label");
  stateLabel.innerText = state;
  stateLabel.className = ""; // clear
  
  if (state === "Good Alignment" || state === "Active Rest (Forward Lean)") {
    stateLabel.classList.add("state-good");
  } else if (state === "Away") {
    stateLabel.classList.add("state-away");
  } else {
    stateLabel.classList.add("state-bad");
  }
}

// Update the circular progress indicators
function updateProgressRing(ringId, percent) {
  const ring = document.getElementById(ringId);
  const r = ring.r.baseVal.value;
  const circumference = 2 * Math.PI * r;
  
  // Calculate offset
  const offset = circumference - (percent / 100) * circumference;
  ring.style.strokeDashoffset = offset;
}

// Update Sitting/Break countdown
function updateStandingTimerUI(sittingSecs, limitSecs, isBreak) {
  const breakModal = document.getElementById("break-modal");
  
  if (isBreak) {
    // Show Fullscreen Standing break screen overlay
    breakModal.style.display = "flex";
    
    // Sitting timer is currently displaying the stand break countdown (3 mins)
    const standRemaining = Math.max(0, 180 - sittingSecs);
    const m = Math.floor(standRemaining / 60).toString().padStart(2, '0');
    const s = (standRemaining % 60).toString().padStart(2, '0');
    
    document.getElementById("modal-time").innerText = `${m}:${s}`;
    
    const breakPct = Math.round((standRemaining / 180) * 100);
    updateProgressRing("modal-ring", breakPct);
  } else {
    breakModal.style.display = "none";
    
    // Normal countdown timer
    const timeRemaining = Math.max(0, limitSecs - sittingSecs);
    const m = Math.floor(timeRemaining / 60).toString().padStart(2, '0');
    const s = (timeRemaining % 60).toString().padStart(2, '0');
    
    document.getElementById("timer-value").innerText = `${m}:${s}`;
    
    const timerPct = Math.round((timeRemaining / limitSecs) * 100);
    updateProgressRing("timer-ring", timerPct);
  }
}

// Dynamic Calibration Countdown
function startCalibrationCountdown() {
  const btn = document.getElementById("btn-calibrate");
  const display = document.getElementById("cal-countdown");
  
  btn.disabled = true;
  let remaining = 5;
  display.innerText = `${remaining}s`;
  
  const timer = setInterval(() => {
    remaining--;
    if (remaining > 0) {
      display.innerText = `${remaining}s`;
    } else {
      clearInterval(timer);
      display.innerText = "Complete";
      btn.disabled = false;
      setTimeout(() => { display.innerText = "Ready"; }, 2000);
    }
  }, 1000);
}

// Injects DB lists into the Posture Coach panel
function renderCoachResources() {
  if (!coachData) return;

  // Stretches Accordion
  const stretchesList = document.getElementById("coach-stretches-list");
  stretchesList.innerHTML = coachData.desk_stretches.map(item => `
    <div class="coach-item">
      <h5>${item.title} (${item.duration_secs}s)</h5>
      <p class="benefit"><em>Benefit: ${item.benefit}</em></p>
      <ol style="margin-left: 14px; margin-top: 6px; font-size: 11px; color: var(--text-secondary);">
        ${item.steps.map(step => `<li>${step}</li>`).join('')}
      </ol>
    </div>
  `).join('');

  // Core Activation Accordion
  const coreList = document.getElementById("coach-core-list");
  coreList.innerHTML = coachData.core_activation.map(item => `
    <div class="coach-item">
      <h5>${item.title} (${item.duration_secs}s)</h5>
      <p class="benefit"><em>Benefit: ${item.benefit}</em></p>
      <ol style="margin-left: 14px; margin-top: 6px; font-size: 11px; color: var(--text-secondary);">
        ${item.steps.map(step => `<li>${step}</li>`).join('')}
      </ol>
    </div>
  `).join('');

  // Ergonomics Setup
  const ergoList = document.getElementById("coach-ergo-list");
  ergoList.innerHTML = coachData.ergonomic_setup.map(cat => `
    <div class="coach-item" style="border-bottom: 1px solid var(--border-color);">
      <h5 style="color: var(--accent-color);">${cat.category}</h5>
      <ul style="margin-left: 14px; margin-top: 6px; font-size: 11px; color: var(--text-secondary);">
        ${cat.tips.map(tip => `<li>${tip}</li>`).join('')}
      </ul>
    </div>
  `).join('');

  // Routines Cards (60-second instructional)
  const routinesList = document.getElementById("routines-list");
  routinesList.innerHTML = coachData.micro_routines.map(routine => `
    <div class="routine-card">
      <div class="routine-info">
        <h4>${routine.title}</h4>
        <p>${routine.description}</p>
      </div>
      <button class="btn btn-primary" onclick="startRoutine('${routine.id}')">Start</button>
    </div>
  `).join('');
}

// 60-Second Guided Routine Player
function startRoutine(id) {
  if (!coachData) return;
  const routine = coachData.micro_routines.find(r => r.id === id);
  if (!routine) return;

  currentRoutine = routine;
  const modal = document.getElementById("routine-modal");
  document.getElementById("routine-modal-title").innerText = routine.title;
  document.getElementById("routine-modal-desc").innerText = routine.description;
  
  modal.style.display = "flex";
  
  let elapsed = 0;
  const total = routine.duration_secs;
  
  // Set initial step
  updateRoutineStepDisplay(elapsed);

  routineTimerInterval = setInterval(() => {
    elapsed++;
    document.getElementById("routine-timer-text").innerText = `${total - elapsed}s`;
    updateRoutineStepDisplay(elapsed);

    if (elapsed >= total) {
      endRoutine();
    }
  }, 1000);
}

function updateRoutineStepDisplay(elapsed) {
  if (!currentRoutine) return;
  
  // Find current active step
  const steps = currentRoutine.steps;
  let activeStep = steps[0];
  let activeIndex = 0;
  
  for (let i = 0; i < steps.length; i++) {
    if (elapsed >= steps[i].time) {
      activeStep = steps[i];
      activeIndex = i;
    }
  }

  document.getElementById("routine-step-counter").innerText = `Step ${activeIndex + 1} of ${steps.length}`;
  document.getElementById("routine-step-text").innerText = activeStep.instruction;
}

function endRoutine() {
  clearInterval(routineTimerInterval);
  document.getElementById("routine-modal").style.display = "none";
  currentRoutine = null;
}

// Render History Stats values
function updateHistoryStatsUI(stats) {
  if (!stats) return;
  
  document.getElementById("metric-stretch").innerText = `${stats.sedentary_stretch_mins} mins`;
  document.getElementById("metric-symmetry").innerText = `${stats.symmetry_index}%`;
  document.getElementById("metric-rate").innerText = `${stats.average_correction_speed_secs}s`;
}

// Canvas-based historical progress chart
function renderHistoryChart() {
  if (!window.pywebview || !window.pywebview.api) return;

  window.pywebview.api.get_historical_chart_data().then(chartData => {
    if (!chartData || chartData.length === 0) return;

    const canvas = document.getElementById("history-chart");
    const ctx = canvas.getContext("2d");
    
    // Handle retina display crisp lines
    const width = canvas.clientWidth || 500;
    const height = canvas.clientHeight || 220;
    canvas.width = width * window.devicePixelRatio;
    canvas.height = height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);


    // Filter to last 28 days (4 weeks) - chartData is already 28 items
    const barsCount = chartData.length;
    
    // Layout variables
    const paddingLeft = 40;
    const paddingRight = 10;
    const paddingTop = 20;
    const paddingBottom = 30;
    
    const chartWidth = width - paddingLeft - paddingRight;
    const chartHeight = height - paddingTop - paddingBottom;
    
    // Draw background grid lines (horizontal Y lines)
    ctx.strokeStyle = "#E2E8F0";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#A0AEC0";
    ctx.font = "10px Inter, sans-serif";
    ctx.textAlign = "right";
    
    const gridLevels = [0, 25, 50, 75, 100];
    gridLevels.forEach(level => {
      const y = paddingTop + chartHeight - (level / 100) * chartHeight;
      
      // Draw grid line
      ctx.beginPath();
      ctx.moveTo(paddingLeft, y);
      ctx.lineTo(width - paddingRight, y);
      ctx.stroke();
      
      // Draw label
      ctx.fillText(level, paddingLeft - 8, y + 3);
    });

    // Draw Bar Elements
    const barSpacing = 4;
    const totalSpacing = barSpacing * (barsCount - 1);
    const barWidth = (chartWidth - totalSpacing) / barsCount;

    chartData.forEach((item, index) => {
      const score = item.score;
      const barHeight = (score / 100) * chartHeight;
      const x = paddingLeft + index * (barWidth + barSpacing);
      const y = paddingTop + chartHeight - barHeight;

      // Color selection (accent colors for high scores, muted for low)
      if (score >= 85) {
        ctx.fillStyle = "#00A896"; // Teal
      } else if (score >= 70) {
        ctx.fillStyle = "#34D399"; // Light Emerald
      } else if (score >= 50) {
        ctx.fillStyle = "#FBBF24"; // Amber
      } else {
        ctx.fillStyle = "#F87171"; // Coral Red
      }

      // Draw rounded bar
      ctx.beginPath();
      ctx.rect(x, y, barWidth, barHeight);
      ctx.fill();

      // Show X axis labels periodically (e.g. once every 7 days/weeks, or first/last)
      if (index % 7 === 0 || index === barsCount - 1) {
        ctx.fillStyle = "#718096";
        ctx.textAlign = "center";
        ctx.font = "9px Inter, sans-serif";
        ctx.fillText(item.label, x + barWidth / 2, paddingTop + chartHeight + 16);
      }
    });
  });
}

// Spinal health motivation insights slider rotation
const insights = [
  "Prolonged sitting restricts blood flow and adds load to the lumbar spine. Interspersing standing breaks every 50-60 minutes decreases static fatigue and improves energy levels.",
  "Left-leaning or right-leaning side imbalances place asymmetrical stress on the pelvis and intervertebral discs. Check your armrest levels and maintain balanced weight on your sit-bones.",
  "A rounded neck and head-forward posture places up to 30 lbs of extra weight on your cervical spine. Keep the top of your monitor at eye level to support alignment.",
  "Deep core stability is built by active muscle engagement. Periodically perform the Transverse Abdominis (TVA) bracing routine to support your spine naturally."
];
let insightIndex = 0;

function rotateInsight() {
  insightIndex = (insightIndex + 1) % insights.length;
  document.getElementById("motivation-text").innerText = insights[insightIndex];
}
