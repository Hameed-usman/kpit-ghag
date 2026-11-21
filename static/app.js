/**
 * Ghag (غږ / آواز) — Civic Tech Voice-First Assistant
 * Frontend ES Module
 */

// Application State
const state = {
  activeTab: 'ask',
  langHint: 'auto',
  demoMode: false,
  demoCache: null,
  isRecording: false,
  mediaRecorder: null,
  audioChunks: [],
  recordTimer: null,
  recordSeconds: 0,
  maxRecordSeconds: 30,
  decibelInterval: null,
  checklistItems: [],
  checklistAvailable: false
};

// DOM Elements
const elements = {
  // Tabs
  tabAskBtn: document.getElementById('tab-ask-btn'),
  tabCheckBtn: document.getElementById('tab-check-btn'),
  panelAsk: document.getElementById('panel-ask'),
  panelCheck: document.getElementById('panel-check'),

  // Header controls
  langPills: document.querySelectorAll('#lang-hint-pills .lang-pill'),
  demoModeToggle: document.getElementById('demo-mode-toggle'),
  demoModeContainer: document.getElementById('demo-mode-container'),
  demoActiveBadge: document.getElementById('demo-active-badge'),

  // Ask section
  askMicBtn: document.getElementById('ask-mic-btn'),
  askMicPing1: document.getElementById('ask-mic-ping-1'),
  askMicPing2: document.getElementById('ask-mic-ping-2'),
  askRecordingStatus: document.getElementById('ask-recording-status'),
  askCallAgentBtn: document.getElementById('ask-call-agent-btn'),
  askTimer: document.getElementById('ask-timer'),
  askTimerCircle: document.getElementById('ask-timer-circle'),
  askDecibelMeter: document.getElementById('ask-decibel-meter'),
  askTextForm: document.getElementById('ask-text-form'),
  askTextInput: document.getElementById('ask-text-input'),
  askClearBtn: document.getElementById('ask-clear-btn'),
  askSubmitBtn: document.getElementById('ask-submit-btn'),
  quickPrompts: document.querySelectorAll('.quick-prompt'),
  askLoading: document.getElementById('ask-loading'),
  askResults: document.getElementById('ask-results'),
  askDetectedLang: document.getElementById('ask-detected-lang'),
  askTranscriptInput: document.getElementById('ask-transcript-input'),
  askResendBtn: document.getElementById('ask-resend-btn'),
  askAnswerCard: document.getElementById('ask-answer-card'),
  askAnswerText: document.getElementById('ask-answer-text'),
  askLatencyBadge: document.getElementById('ask-latency-badge'),
  askAudioPlayer: document.getElementById('ask-audio-player'),
  askReplayBtn: document.getElementById('ask-replay-btn'),
  askAudioNotice: document.getElementById('ask-audio-notice'),
  askSourceLink: document.getElementById('ask-source-link'),
  askSmsCard: document.getElementById('ask-sms-card'),
  askSmsText: document.getElementById('ask-sms-text'),
  askSmsCounter: document.getElementById('ask-sms-counter'),
  askHandoffCard: document.getElementById('ask-handoff-card'),
  askHandoffReason: document.getElementById('ask-handoff-reason'),
  micError: document.getElementById('mic-error'),

  // Check section
  checklistWarningBanner: document.getElementById('checklist-warning-banner'),
  checklistItemsContainer: document.getElementById('checklist-items-container'),
  checklistLoading: document.getElementById('checklist-loading'),
  checklistFieldset: document.getElementById('checklist-fieldset'),
  checklistOptions: document.getElementById('checklist-options'),
  checkMicBtn: document.getElementById('check-mic-btn'),
  checkRecordingStatus: document.getElementById('check-recording-status'),
  checkTimer: document.getElementById('check-timer'),
  checkTextInput: document.getElementById('check-text-input'),
  checkSubmitBtn: document.getElementById('check-submit-btn'),
  checkLoading: document.getElementById('check-loading'),
  checkResults: document.getElementById('check-results'),
  checkVerdictBanner: document.getElementById('check-verdict-banner'),
  checkVerdictIcon: document.getElementById('check-verdict-icon'),
  checkVerdictTitle: document.getElementById('check-verdict-title'),
  checkVerdictMsg: document.getElementById('check-verdict-msg'),
  checkMatchedList: document.getElementById('check-matched-list'),
  checkMissingList: document.getElementById('check-missing-list'),
  checkAnswerText: document.getElementById('check-answer-text'),
  checkLatencyBadge: document.getElementById('check-latency-badge'),
  checkAudioPlayer: document.getElementById('check-audio-player'),
  checkReplayBtn: document.getElementById('check-replay-btn'),
  checkAudioNotice: document.getElementById('check-audio-notice'),
  checkSmsText: document.getElementById('check-sms-text'),
  checkSmsCounter: document.getElementById('check-sms-counter'),

  // Glass-box panels (FR-17)
  askGlassboxToggle: document.getElementById('ask-glassbox-toggle'),
  askGlassboxContent: document.getElementById('ask-glassbox-content'),
  askGlassboxChevron: document.getElementById('ask-glassbox-chevron'),
  askGbHeard: document.getElementById('ask-gb-heard'),
  askGbLang: document.getElementById('ask-gb-lang'),
  askGbSourceId: document.getElementById('ask-gb-source-id'),
  askGbSourceUrl: document.getElementById('ask-gb-source-url'),
  askGbLastVerified: document.getElementById('ask-gb-last-verified'),
  askGbConfident: document.getElementById('ask-gb-confident'),
  askGbHandoff: document.getElementById('ask-gb-handoff'),
  askGbLatency: document.getElementById('ask-gb-latency'),

  checkGlassboxToggle: document.getElementById('check-glassbox-toggle'),
  checkGlassboxContent: document.getElementById('check-glassbox-content'),
  checkGlassboxChevron: document.getElementById('check-glassbox-chevron'),
  checkGbHeard: document.getElementById('check-gb-heard'),
  checkGbLang: document.getElementById('check-gb-lang'),
  checkGbSourceId: document.getElementById('check-gb-source-id'),
  checkGbSourceUrl: document.getElementById('check-gb-source-url'),
  checkGbLastVerified: document.getElementById('check-gb-last-verified'),
  checkGbConfident: document.getElementById('check-gb-confident'),
  checkGbHandoff: document.getElementById('check-gb-handoff'),
  checkGbLatency: document.getElementById('check-gb-latency')
};

/**
 * Initialize
 */
async function init() {
  bindEvents();
  await loadDemoCache();
  await loadChecklist();
}

/**
 * Event Bindings
 */
function bindEvents() {
  // Tab switching
  elements.tabAskBtn.addEventListener('click', () => switchTab('ask'));
  elements.tabCheckBtn.addEventListener('click', () => switchTab('check'));

  // Language Hint Pills
  elements.langPills.forEach(pill => {
    pill.addEventListener('click', () => {
      elements.langPills.forEach(p => {
        p.classList.remove('bg-primary', 'text-surface', 'font-semibold', 'shadow');
        p.classList.add('text-on-surface-variant', 'font-medium');
      });
      pill.classList.remove('text-on-surface-variant', 'font-medium');
      pill.classList.add('bg-primary', 'text-surface', 'font-semibold', 'shadow');
      state.langHint = pill.dataset.lang;
    });
  });

  // Demo Mode Toggle
  elements.demoModeToggle.addEventListener('change', (e) => {
    state.demoMode = e.target.checked;
    elements.demoActiveBadge.classList.toggle('hidden', !state.demoMode);
  });

  // Quick Prompts
  elements.quickPrompts.forEach(btn => {
    btn.addEventListener('click', () => {
      elements.askTextInput.value = btn.innerText.trim();
      submitAskText();
    });
  });

  // Clear text
  elements.askClearBtn.addEventListener('click', () => {
    elements.askTextInput.value = '';
    elements.askTextInput.focus();
  });

  // Ask Voice Recording
  elements.askMicBtn.addEventListener('click', () => toggleRecording('ask'));

  // Two-Way Call Agent (1700 Helpline Simulation)
  if (elements.askCallAgentBtn) {
    elements.askCallAgentBtn.addEventListener('click', () => startTwoWayCall());
  }

  // Ask Form Submit
  elements.askTextForm.addEventListener('submit', (e) => {
    e.preventDefault();
    submitAskText();
  });

  // Resend Edited Transcript
  elements.askResendBtn.addEventListener('click', () => {
    const editedText = elements.askTranscriptInput.value.trim();
    if (editedText) {
      elements.askTextInput.value = editedText;
      submitAskText();
    }
  });

  // Ask Audio Replay
  elements.askReplayBtn.addEventListener('click', () => {
    if (elements.askAudioPlayer && elements.askAudioPlayer.src && elements.askAudioPlayer.src.startsWith('data:audio')) {
      elements.askAudioPlayer.currentTime = 0;
      elements.askAudioPlayer.play().catch(() => {
        speakFallback(elements.askAnswerText.textContent, state.lastResultLang);
      });
    } else if (elements.askAnswerText && elements.askAnswerText.textContent) {
      speakFallback(elements.askAnswerText.textContent, state.lastResultLang);
    }
  });

  // Check Voice Recording
  elements.checkMicBtn.addEventListener('click', () => toggleRecording('check'));

  // Check Submit
  elements.checkSubmitBtn.addEventListener('click', () => submitCheck());

  // Check Audio Replay
  elements.checkReplayBtn.addEventListener('click', () => {
    if (elements.checkAudioPlayer && elements.checkAudioPlayer.src && elements.checkAudioPlayer.src.startsWith('data:audio')) {
      elements.checkAudioPlayer.currentTime = 0;
      elements.checkAudioPlayer.play().catch(() => {
        speakFallback(elements.checkAnswerText.textContent, state.lastCheckLang);
      });
    } else if (elements.checkAnswerText && elements.checkAnswerText.textContent) {
      speakFallback(elements.checkAnswerText.textContent, state.lastCheckLang);
    }
  });

  // Glass-box toggles (FR-17)
  if (elements.askGlassboxToggle) {
    elements.askGlassboxToggle.addEventListener('click', () => {
      const isHidden = elements.askGlassboxContent.classList.toggle('hidden');
      elements.askGlassboxChevron.textContent = isHidden ? 'expand_more' : 'expand_less';
    });
  }

  if (elements.checkGlassboxToggle) {
    elements.checkGlassboxToggle.addEventListener('click', () => {
      const isHidden = elements.checkGlassboxContent.classList.toggle('hidden');
      elements.checkGlassboxChevron.textContent = isHidden ? 'expand_more' : 'expand_less';
    });
  }
}

/**
 * Tab Navigation
 */
function switchTab(tab) {
  state.activeTab = tab;
  if (tab === 'ask') {
    elements.tabAskBtn.className = "flex-1 py-3 px-4 rounded-xl text-sm font-bold text-white bg-surface-container-high shadow-md transition-all flex items-center justify-center gap-2 border border-surface-variant";
    elements.tabAskBtn.setAttribute('aria-selected', 'true');
    elements.tabCheckBtn.className = "flex-1 py-3 px-4 rounded-xl text-sm font-medium text-on-surface-variant hover:text-white transition-all flex items-center justify-center gap-2";
    elements.tabCheckBtn.setAttribute('aria-selected', 'false');
    elements.panelAsk.classList.remove('hidden');
    elements.panelCheck.classList.add('hidden');
  } else {
    elements.tabCheckBtn.className = "flex-1 py-3 px-4 rounded-xl text-sm font-bold text-white bg-surface-container-high shadow-md transition-all flex items-center justify-center gap-2 border border-surface-variant";
    elements.tabCheckBtn.setAttribute('aria-selected', 'true');
    elements.tabAskBtn.className = "flex-1 py-3 px-4 rounded-xl text-sm font-medium text-on-surface-variant hover:text-white transition-all flex items-center justify-center gap-2";
    elements.tabAskBtn.setAttribute('aria-selected', 'false');
    elements.panelCheck.classList.remove('hidden');
    elements.panelAsk.classList.add('hidden');
  }
}

/**
 * Demo Cache Loader
 */
async function loadDemoCache() {
  try {
    const res = await fetch('/cache.json');
    if (res.ok) {
      const data = await res.json();
      if (data && (data.ask_cases || data.check_case)) {
        state.demoCache = data;
        elements.demoModeToggle.disabled = false;
        elements.demoModeContainer.title = "Offline demo mode available (loaded from static/cache.json)";
        return;
      }
    }
  } catch (err) {
    // Cache unavailable
  }
  elements.demoModeToggle.disabled = true;
  elements.demoModeContainer.title = "Run scripts/capture_demo_cache.py to enable offline demo mode.";
}

/**
 * Load Checklist Metadata
 */
async function loadChecklist() {
  try {
    elements.checklistLoading.classList.remove('hidden');
    const res = await fetch('/api/v1/checklist');
    if (!res.ok) throw new Error('Checklist endpoint error');
    const data = await res.json();

    state.checklistAvailable = data.available;
    state.checklistItems = data.items || [];
    elements.checklistLoading.classList.add('hidden');

    if (!data.available || state.checklistItems.length === 0) {
      elements.checklistWarningBanner.classList.remove('hidden');
      elements.checklistFieldset.classList.add('hidden');
      elements.checkSubmitBtn.disabled = true;
      elements.checkMicBtn.disabled = true;
      elements.checkSubmitBtn.classList.add('opacity-50', 'cursor-not-allowed');
      elements.checkMicBtn.classList.add('opacity-50', 'cursor-not-allowed');
    } else {
      elements.checklistWarningBanner.classList.add('hidden');
      elements.checklistFieldset.classList.remove('hidden');
      elements.checkSubmitBtn.disabled = false;
      elements.checkMicBtn.disabled = false;
      elements.checkSubmitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
      elements.checkMicBtn.classList.remove('opacity-50', 'cursor-not-allowed');
      renderChecklistOptions(state.checklistItems);
    }
  } catch (err) {
    elements.checklistLoading.classList.add('hidden');
    elements.checklistWarningBanner.classList.remove('hidden');
  }
}

/**
 * Render Checkboxes
 */
function renderChecklistOptions(items) {
  elements.checklistOptions.innerHTML = '';
  items.forEach(item => {
    const label = document.createElement('label');
    label.className = 'flex items-center gap-3 p-3 rounded-xl bg-surface-container-low border border-surface-variant hover:border-secondary/50 cursor-pointer transition-all';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = item.id;
    checkbox.name = 'declared_documents';
    checkbox.className = 'w-4 h-4 rounded text-secondary focus:ring-0 bg-surface-container';

    const span = document.createElement('span');
    span.className = 'text-xs text-white font-medium';
    span.textContent = item.label_en || item.id;

    label.appendChild(checkbox);
    label.appendChild(span);
    elements.checklistOptions.appendChild(label);
  });
}

/**
 * Voice Recording
 */
async function toggleRecording(mode) {
  if (state.isRecording) {
    stopRecording();
  } else {
    await startRecording(mode);
  }
}

/**
 * Two-Way Automated Call Agent (1700 Simulation)
 */
async function startTwoWayCall() {
  hideMicError();
  const lang = (state.langHint === 'auto' ? 'ur' : state.langHint) || 'ur';
  state.isCallMode = true;

  elements.askRecordingStatus.classList.remove('hidden');
  const statusSpan = elements.askRecordingStatus.querySelector('span:last-child');
  if (statusSpan) {
    statusSpan.textContent = '📞 Call Connected (1700 Helpline): Agent Greeting...';
  }

  try {
    const greetingAudio = new Audio(`/api/v1/call/greeting?lang=${lang}`);
    greetingAudio.onended = async () => {
      if (statusSpan) {
        statusSpan.textContent = '🎙️ Agent is listening... Speak your question now!';
      }
      if (!state.isRecording) {
        await startRecording('ask');
      }
    };
    await greetingAudio.play();
  } catch (err) {
    const greetings = {
      ur: "السلام علیکم! خیبر پختونخوا سٹیزن ہیلپ لائن میں خوش آمدید۔ ڈومیسائل کے بارے میں آپ کو کیا معلومات چاہیے؟",
      ps: "سلام علیکم! د خیبر پختونخوا ولسي خدمت مرکز ته ښه راغلاست. د ډومیسائل سند په اړه تاسو ته څه معلومات پکار دي؟",
      en: "Hello and welcome to Khyber Pakhtunkhwa Citizen Facilitation. How may I assist you with your Domicile Certificate today?"
    };
    speakFallback(greetings[lang] || greetings.ur, lang);
    setTimeout(async () => {
      if (!state.isRecording) await startRecording('ask');
    }, 4200);
  }
}

function announceProcessing() {
  const lang = (state.langHint === 'auto' ? 'ur' : state.langHint) || 'ur';
  try {
    const waitAudio = new Audio(`/api/v1/call/wait?lang=${lang}`);
    waitAudio.play().catch(() => {});
  } catch (e) {
    const waitTexts = {
      ur: "جی، میں آپ کے لیے سرکاری ریکارڈ دیکھ رہا ہوں، ذرا انتظار کیجیے۔",
      ps: "ستاسو لپاره رسمي ریکارډ کتل کیږي، لږ انتظار وکړئ.",
      en: "Checking verified government records for you, one moment please."
    };
    speakFallback(waitTexts[lang] || waitTexts.ur, lang);
  }
}

async function startRecording(mode) {
  hideMicError();
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showMicError("Audio recording not supported on this browser context. Please use text input or open over http://localhost:8000.");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    let mimeType = '';
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      mimeType = 'audio/webm;codecs=opus';
    } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
      mimeType = 'audio/mp4';
    }

    state.mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    state.audioChunks = [];
    state.recordingMode = mode;

    state.mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        state.audioChunks.push(e.data);
      }
    };

    state.mediaRecorder.onstop = () => {
      stream.getTracks().forEach(track => track.stop());
      const mime = state.mediaRecorder.mimeType || 'audio/webm';
      const audioBlob = new Blob(state.audioChunks, { type: mime });
      if (state.recordingMode === 'ask') {
        if (state.isCallMode) {
          announceProcessing();
          state.isCallMode = false;
        }
        submitAskAudio(audioBlob);
      } else {
        submitCheckAudio(audioBlob);
      }
    };

    state.mediaRecorder.start();
    state.isRecording = true;
    state.recordSeconds = 0;

    // UI Updates
    const langNames = {
      'auto': 'Auto-detect',
      'ur': 'Urdu (اردو)',
      'ps': 'Pashto (پښتو)',
      'en': 'English'
    };
    const activeLangLabel = langNames[state.langHint] || 'Auto-detect';

    if (mode === 'ask') {
      elements.askMicPing1.classList.remove('hidden');
      elements.askMicPing2.classList.remove('hidden');
      elements.askRecordingStatus.classList.remove('hidden');
      elements.askRecordingStatus.querySelector('span:last-child').textContent = `Listening in ${activeLangLabel}... (Max 30s)`;
      elements.askTimer.textContent = '00:00';
      startWaveformSimulation();
    } else {
      elements.checkRecordingStatus.classList.remove('hidden');
      elements.checkTimer.textContent = '00:00';
    }

    state.recordTimer = setInterval(() => {
      state.recordSeconds++;
      const mm = String(Math.floor(state.recordSeconds / 60)).padStart(2, '0');
      const ss = String(state.recordSeconds % 60).padStart(2, '0');
      const timeStr = `${mm}:${ss}`;

      if (mode === 'ask') {
        elements.askTimer.textContent = timeStr;
        // Progress circle
        const offset = 276 - (276 * (state.recordSeconds / state.maxRecordSeconds));
        elements.askTimerCircle.style.strokeDashoffset = offset;
      } else {
        elements.checkTimer.textContent = timeStr;
      }

      if (state.recordSeconds >= state.maxRecordSeconds) {
        stopRecording();
      }
    }, 1000);

  } catch (err) {
    console.error('Microphone access denied:', err);
    showMicError('Microphone access denied or unavailable. Please grant microphone permissions or type your question.');
  }
}

function stopRecording() {
  if (!state.isRecording || !state.mediaRecorder) return;
  state.isRecording = false;
  clearInterval(state.recordTimer);
  stopWaveformSimulation();

  elements.askMicPing1.classList.add('hidden');
  elements.askMicPing2.classList.add('hidden');
  elements.askRecordingStatus.classList.add('hidden');
  elements.checkRecordingStatus.classList.add('hidden');
  elements.askTimerCircle.style.strokeDashoffset = 276;

  if (state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.stop();
  }
}

function startWaveformSimulation() {
  const bars = elements.askDecibelMeter.querySelectorAll('.waveform-bar');
  state.decibelInterval = setInterval(() => {
    bars.forEach(b => {
      const h = Math.floor(Math.random() * 28) + 6;
      b.style.height = `${h}px`;
    });
  }, 120);
}

function stopWaveformSimulation() {
  if (state.decibelInterval) clearInterval(state.decibelInterval);
  const bars = elements.askDecibelMeter.querySelectorAll('.waveform-bar');
  bars.forEach((b, i) => {
    b.style.height = `${(i % 5) * 3 + 4}px`;
  });
}

function showMicError(msg) {
  elements.micError.textContent = msg;
  elements.micError.classList.remove('hidden');
}

function hideMicError() {
  elements.micError.classList.add('hidden');
  elements.micError.textContent = '';
}

/**
 * Submit Ask Text
 */
async function submitAskText() {
  const text = elements.askTextInput.value.trim();
  if (!text) return;

  // Demo cache match
  if (state.demoMode && state.demoCache && state.demoCache.ask_cases) {
    const replay = matchDemoAsk(text);
    if (replay) {
      renderAskResult(replay);
      return;
    }
  }

  showAskLoading(true);
  const startTime = performance.now();

  try {
    const formData = new FormData();
    formData.append('text', text);
    if (state.langHint && state.langHint !== 'auto') {
      formData.append('lang_hint', state.langHint);
      formData.append('lang', state.langHint);
    }

    const res = await fetch('/api/v1/ask', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    const data = await res.json();
    const elapsed = Math.round(performance.now() - startTime);
    renderAskResult(data, elapsed);

  } catch (err) {
    showMicError(`Error processing request: ${err.message}`);
  } finally {
    showAskLoading(false);
  }
}

/**
 * Submit Ask Audio
 */
async function submitAskAudio(blob) {
  showAskLoading(true);
  const startTime = performance.now();

  try {
    const formData = new FormData();
    const filename = blob.type.includes('mp4') ? 'voice.mp4' : 'voice.webm';
    formData.append('audio', blob, filename);
    if (state.langHint && state.langHint !== 'auto') {
      formData.append('lang_hint', state.langHint);
    }

    const res = await fetch('/api/v1/ask', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    const data = await res.json();
    const elapsed = Math.round(performance.now() - startTime);
    renderAskResult(data, elapsed);

  } catch (err) {
    showMicError(`Error processing audio: ${err.message}`);
  } finally {
    showAskLoading(false);
  }
}

/**
 * Render Ask Result
 */
function renderAskResult(data, latencyMs = null) {
  elements.askResults.classList.remove('hidden');

  // Transcript
  elements.askTranscriptInput.value = data.transcript || data.question || '';
  const lang = (data.lang || 'ur').toLowerCase();
  elements.askDetectedLang.textContent = lang === 'ur' ? 'URDU (اردو)' : (lang === 'ps' ? 'PASHTO (پښتو)' : 'ENGLISH');
  
  const isRtl = (lang === 'ur' || lang === 'ps');
  elements.askTranscriptInput.dir = isRtl ? 'rtl' : 'ltr';

  // Answer Text
  elements.askAnswerText.textContent = data.answer || '';
  elements.askAnswerText.dir = isRtl ? 'rtl' : 'ltr';

  // Latency
  if (latencyMs) {
    elements.askLatencyBadge.textContent = `${latencyMs} ms`;
    elements.askLatencyBadge.classList.remove('hidden');
  } else {
    elements.askLatencyBadge.classList.add('hidden');
  }

  // Source Citation
  if (data.source_url) {
    elements.askSourceLink.href = data.source_url;
    elements.askSourceLink.textContent = data.source_id ? `[${data.source_id}] ${data.source_url}` : data.source_url;
    elements.askSourceLink.classList.remove('hidden');
  } else if (data.source_id) {
    elements.askSourceLink.textContent = data.source_id;
    elements.askSourceLink.removeAttribute('href');
    elements.askSourceLink.classList.remove('hidden');
  } else {
    elements.askSourceLink.classList.add('hidden');
  }

  state.lastResultLang = lang;

  // Audio Playback
  const audioData = data.audio_b64 || data.audio_base64;
  if (audioData) {
    elements.askAudioPlayer.classList.remove('hidden');
    elements.askAudioPlayer.src = `data:audio/mp3;base64,${audioData}`;
    elements.askAudioPlayer.load();
    elements.askAudioNotice.classList.add('hidden');
    elements.askAudioPlayer.play().then(() => {
      elements.askAudioNotice.classList.add('hidden');
    }).catch(() => {
      elements.askAudioNotice.classList.remove('hidden');
    });
  } else {
    elements.askAudioPlayer.removeAttribute('src');
    elements.askAudioNotice.classList.remove('hidden');
    elements.askAudioNotice.innerHTML = '🔊 <em>Tap green speaker icon to listen</em>';
    speakFallback(data.answer, lang);
  }

  // SMS Bubble
  const smsText = data.sms_text || data.sms || '';
  elements.askSmsText.textContent = smsText;
  elements.askSmsText.dir = isRtl ? 'rtl' : 'ltr';
  elements.askSmsCounter.textContent = `${smsText.length}/160 chars`;

  // Handoff Card
  if (data.outcome === 'handoff' || data.confident === false) {
    elements.askHandoffCard.classList.remove('hidden');
    elements.askHandoffReason.textContent = "This inquiry requires verified official guidance from designated citizen facilitation officers.";
  } else {
    elements.askHandoffCard.classList.add('hidden');
  }

  // Glass-Box Explainability Panel (FR-17)
  if (elements.askGbHeard) {
    elements.askGbHeard.textContent = data.transcript || data.heard || 'N/A';
    elements.askGbLang.textContent = (data.lang || 'N/A').toUpperCase();
    elements.askGbSourceId.textContent = data.source_id || 'None (Refused / Unmatched)';

    if (data.source_url) {
      elements.askGbSourceUrl.textContent = data.source_url;
      elements.askGbSourceUrl.href = data.source_url;
      elements.askGbSourceUrl.classList.remove('hidden');
    } else {
      elements.askGbSourceUrl.textContent = 'None';
      elements.askGbSourceUrl.removeAttribute('href');
    }

    elements.askGbLastVerified.textContent = data.last_verified || '2026-11-17 (Official Gazette)';
    const isConfident = data.confident !== undefined ? data.confident : (data.outcome !== 'handoff');
    elements.askGbConfident.textContent = isConfident ? 'YES (Grounded in Verified KB)' : 'NO (Refused / Out of Scope)';
    elements.askGbConfident.className = isConfident ? 'text-emerald-400 font-bold font-mono' : 'text-amber-400 font-bold font-mono';
    elements.askGbHandoff.textContent = data.handoff_reason || (isConfident ? 'None' : 'Out of verified government knowledge base scope');
    elements.askGbLatency.textContent = `${data.latency_ms || latencyMs || '—'} ms`;
  }

  elements.askResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/**
 * Submit Check
 */
async function submitCheck() {
  const textInput = elements.checkTextInput.value.trim();
  const checkboxes = document.querySelectorAll('input[name="declared_documents"]:checked');
  const declaredList = Array.from(checkboxes).map(cb => cb.value);

  if (state.demoMode && state.demoCache && state.demoCache.check_case) {
    renderCheckResult(state.demoCache.check_case);
    return;
  }

  showCheckLoading(true);
  const startTime = performance.now();

  try {
    const payload = {
      text: textInput || (declaredList.join(', ')),
      service: 'domicile'
    };
    if (state.langHint && state.langHint !== 'auto') {
      payload.lang = state.langHint;
    }

    const res = await fetch('/api/v1/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    const data = await res.json();
    const elapsed = Math.round(performance.now() - startTime);
    renderCheckResult(data, elapsed);

  } catch (err) {
    alert(`Pre-check failed: ${err.message}`);
  } finally {
    showCheckLoading(false);
  }
}

/**
 * Submit Check Audio
 */
async function submitCheckAudio(blob) {
  showCheckLoading(true);
  const startTime = performance.now();

  try {
    const formData = new FormData();
    const filename = blob.type.includes('mp4') ? 'docs.mp4' : 'docs.webm';
    formData.append('audio', blob, filename);
    if (state.langHint && state.langHint !== 'auto') {
      formData.append('lang_hint', state.langHint);
    }

    const res = await fetch('/api/v1/check', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    const data = await res.json();
    const elapsed = Math.round(performance.now() - startTime);
    renderCheckResult(data, elapsed);

  } catch (err) {
    alert(`Voice pre-check failed: ${err.message}`);
  } finally {
    showCheckLoading(false);
  }
}

/**
 * Render Check Result
 */
function renderCheckResult(data, latencyMs = null) {
  elements.checkResults.classList.remove('hidden');

  // Verdict Banner
  elements.checkVerdictBanner.className = 'p-4 rounded-2xl flex items-center gap-3 shadow-md';
  if (data.verdict === 'ready') {
    elements.checkVerdictBanner.classList.add('bg-emerald-950/40', 'border', 'border-emerald-500/40', 'text-emerald-200');
    elements.checkVerdictIcon.textContent = '✅';
    elements.checkVerdictTitle.textContent = 'All Required Documents Present';
    elements.checkVerdictMsg.textContent = 'You have all gazetted documents ready. Proceed to submit your application.';
  } else if (data.verdict === 'missing') {
    elements.checkVerdictBanner.classList.add('bg-red-950/40', 'border', 'border-red-500/40', 'text-red-200');
    elements.checkVerdictIcon.textContent = '❌';
    elements.checkVerdictTitle.textContent = 'Missing Required Documents Detected';
    elements.checkVerdictMsg.textContent = 'One or more required documents are missing. Complete your set before visiting.';
  } else if (data.verdict === 'unavailable') {
    elements.checkVerdictBanner.classList.add('bg-amber-950/40', 'border', 'border-amber-500/40', 'text-amber-200');
    elements.checkVerdictIcon.textContent = '⚠️';
    elements.checkVerdictTitle.textContent = 'Checklist Currently Unverified';
    elements.checkVerdictMsg.textContent = 'Official checklist verification is pending in the KB (Constitution P-1).';
  } else {
    elements.checkVerdictBanner.classList.add('bg-surface-variant', 'text-white');
    elements.checkVerdictIcon.textContent = '❓';
    elements.checkVerdictTitle.textContent = 'Unclear Document Utterance';
    elements.checkVerdictMsg.textContent = 'Could not reliably identify your documents. Please review the checklist.';
  }

  // Matched Documents
  elements.checkMatchedList.innerHTML = '';
  const matched = data.matched || data.matched_documents || [];
  if (matched.length > 0) {
    matched.forEach(doc => {
      const li = document.createElement('li');
      li.textContent = doc;
      elements.checkMatchedList.appendChild(li);
    });
  } else {
    const li = document.createElement('li');
    li.textContent = 'None identified';
    elements.checkMatchedList.appendChild(li);
  }

  // Missing Documents
  elements.checkMissingList.innerHTML = '';
  const missing = data.missing || data.missing_documents || [];
  if (missing.length > 0) {
    missing.forEach(doc => {
      const li = document.createElement('li');
      li.textContent = typeof doc === 'object' ? `${doc.id}: ${doc.label}` : doc;
      elements.checkMissingList.appendChild(li);
    });
  } else {
    const li = document.createElement('li');
    li.textContent = 'No missing documents!';
    elements.checkMissingList.appendChild(li);
  }

  // Spoken Guidance
  elements.checkAnswerText.textContent = data.spoken || data.explanation || '';
  const isRtl = (data.lang === 'ur' || data.lang === 'ps');
  elements.checkAnswerText.dir = isRtl ? 'rtl' : 'ltr';
  state.lastCheckLang = data.lang || 'ur';

  // Audio Playback
  const audioData = data.audio_b64 || data.audio_base64;
  if (audioData) {
    elements.checkAudioPlayer.classList.remove('hidden');
    elements.checkAudioPlayer.src = `data:audio/mp3;base64,${audioData}`;
    elements.checkAudioPlayer.load();
    elements.checkAudioNotice.classList.add('hidden');
    elements.checkAudioPlayer.play().catch(() => {
      elements.checkAudioNotice.classList.remove('hidden');
    });
  } else {
    elements.checkAudioPlayer.removeAttribute('src');
    elements.checkAudioPlayer.classList.add('hidden');
    elements.checkAudioNotice.classList.remove('hidden');
    elements.checkAudioNotice.innerHTML = '🔊 <em>Tap speaker icon to listen</em>';
    speakFallback(data.spoken || data.explanation, data.lang);
  }

  // SMS
  const smsText = data.sms_text || data.sms || '';
  elements.checkSmsText.textContent = smsText;
  elements.checkSmsCounter.textContent = `${smsText.length}/160 chars`;

  // Glass-Box Explainability Panel for Document Check (FR-17)
  if (elements.checkGbHeard) {
    elements.checkGbHeard.textContent = data.heard || 'Declared items';
    elements.checkGbLang.textContent = (data.lang || 'EN').toUpperCase();
    elements.checkGbSourceId.textContent = data.source_id || 'dom-checklist';

    if (data.source_url) {
      elements.checkGbSourceUrl.textContent = data.source_url;
      elements.checkGbSourceUrl.href = data.source_url;
    } else {
      elements.checkGbSourceUrl.textContent = 'https://cfc.kp.gov.pk/';
      elements.checkGbSourceUrl.href = 'https://cfc.kp.gov.pk/';
    }

    elements.checkGbLastVerified.textContent = data.last_verified || '2026-11-17 (Gazette)';
    const isConfident = (data.verdict === 'ready' || data.verdict === 'missing');
    elements.checkGbConfident.textContent = isConfident ? 'YES (Strict Set Difference)' : 'NO (Unverified or Ambiguous)';
    elements.checkGbConfident.className = isConfident ? 'text-emerald-400 font-bold font-mono' : 'text-amber-400 font-bold font-mono';
    elements.checkGbHandoff.textContent = data.handoff_reason || (isConfident ? 'None' : 'Checklist unverified or utterance ambiguous');
    elements.checkGbLatency.textContent = `${data.latency_ms || latencyMs || '—'} ms`;
  }

  elements.checkResults.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function speakFallback(text, lang) {
  if (!('speechSynthesis' in window) || !text) return;
  try {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    if (lang === 'ur') {
      utterance.lang = 'ur-PK';
    } else if (lang === 'ps') {
      utterance.lang = 'ps-AF';
    } else {
      utterance.lang = 'en-US';
    }
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  } catch (err) {
    console.warn('Browser speech synthesis error:', err);
  }
}

function matchDemoAsk(query) {
  if (!state.demoCache || !state.demoCache.ask_cases) return null;
  const cases = state.demoCache.ask_cases;
  const match = cases.find(c => c.question && c.question.toLowerCase().includes(query.toLowerCase()));
  return match || cases[0];
}

function showAskLoading(show) {
  elements.askLoading.classList.toggle('hidden', !show);
  elements.askSubmitBtn.disabled = show;
  elements.askMicBtn.disabled = show;
}

function showCheckLoading(show) {
  elements.checkLoading.classList.toggle('hidden', !show);
  elements.checkSubmitBtn.disabled = show;
  elements.checkMicBtn.disabled = show;
}

// Boot
init();
