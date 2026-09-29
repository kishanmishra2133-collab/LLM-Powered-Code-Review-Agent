// ReviewLens Client Logic: Unified input bar, file/folder upload dropdown, meteor shower night sky, SSE streaming, and findings

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('reviewForm');
  const inputBar = document.querySelector('.unified-input-bar');
  const uploadMenuBtn = document.getElementById('uploadMenuBtn');
  const uploadDropdown = document.getElementById('uploadDropdown');
  const optUploadFile = document.getElementById('optUploadFile');
  const optUploadFolder = document.getElementById('optUploadFolder');
  const filePicker = document.getElementById('filePicker');
  const folderPicker = document.getElementById('folderPicker');

  const selectedBadge = document.getElementById('selectedBadge');
  const badgeIcon = document.getElementById('badgeIcon');
  const badgeText = document.getElementById('badgeText');
  const clearUploadBtn = document.getElementById('clearUploadBtn');

  const targetInput = document.getElementById('targetInput');
  const submitBtn = document.getElementById('submitBtn');

  const errorCard = document.getElementById('errorCard');
  const stepperContainer = document.getElementById('stepperContainer');
  const summaryStrip = document.getElementById('summaryStrip');
  const diffContainer = document.getElementById('diffContainer');

  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const themeIcon = document.getElementById('themeIcon');

  const steps = ['fetch', 'filter', 'annotate', 'review', 'validate', 'verify', 'finalize'];
  let uploadedFilesState = []; // [{ path: string, content: string, size: number }]
  let activeEventSource = null;
  let activeAbortController = null;

  // --- Night Sky Meteor Shower Animation ---
  initMeteorShower();

  function initMeteorShower() {
    const canvas = document.getElementById('meteorCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    window.addEventListener('resize', () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
      initStars();
    });

    // Generate static twinkling stars
    let stars = [];
    function initStars() {
      stars = [];
      const count = Math.floor((width * height) / 7500); // ~130 stars on 1080p
      for (let i = 0; i < count; i++) {
        stars.push({
          x: Math.random() * width,
          y: Math.random() * height,
          radius: Math.random() * 1.3 + 0.3,
          alpha: Math.random() * 0.7 + 0.2,
          twinkleSpeed: (Math.random() * 0.02 + 0.006) * (Math.random() < 0.5 ? 1 : -1),
        });
      }
    }
    initStars();

    // Meteors array
    const meteors = [];

    function spawnMeteor() {
      // Angle: ~215 degrees (travels top-right to bottom-left)
      const angle = (Math.PI / 180) * (215 + (Math.random() * 20 - 10));
      const speed = Math.random() * 8 + 9; // 9 to 17 px per frame
      const length = Math.random() * 90 + 90; // trail length 90-180px

      // Spawn from top or right edge
      let x, y;
      if (Math.random() < 0.65) {
        x = Math.random() * (width + 100) + 100;
        y = -40;
      } else {
        x = width + 40;
        y = Math.random() * (height * 0.6);
      }

      meteors.push({
        x,
        y,
        dx: Math.cos(angle) * speed,
        dy: -Math.sin(angle) * speed,
        length,
        opacity: 1,
        fadeRate: Math.random() * 0.009 + 0.007,
        size: Math.random() * 1.4 + 1.2,
      });
    }

    let lastSpawn = 0;
    let nextSpawnInterval = 1200 + Math.random() * 1500;

    function renderFrame(timestamp) {
      // If user toggled to light theme, pause drawing
      if (document.body.classList.contains('theme-light')) {
        requestAnimationFrame(renderFrame);
        return;
      }

      ctx.clearRect(0, 0, width, height);

      // 1. Draw Twinkling Stars
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        s.alpha += s.twinkleSpeed;
        if (s.alpha > 0.95) {
          s.alpha = 0.95;
          s.twinkleSpeed = -Math.abs(s.twinkleSpeed);
        } else if (s.alpha < 0.15) {
          s.alpha = 0.15;
          s.twinkleSpeed = Math.abs(s.twinkleSpeed);
        }

        ctx.beginPath();
        ctx.arc(s.x, s.y, s.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(224, 231, 255, ${s.alpha})`;
        ctx.fill();
      }

      // 2. Spawn Meteors
      if (timestamp - lastSpawn > nextSpawnInterval) {
        spawnMeteor();
        // Occasional double meteor
        if (Math.random() < 0.3) {
          setTimeout(spawnMeteor, 220);
        }
        lastSpawn = timestamp;
        nextSpawnInterval = 1000 + Math.random() * 2000;
      }

      // 3. Update & Draw Meteors
      for (let i = meteors.length - 1; i >= 0; i--) {
        const m = meteors[i];
        m.x += m.dx;
        m.y += m.dy;
        m.opacity -= m.fadeRate;

        if (m.opacity <= 0 || m.x < -200 || m.y > height + 200) {
          meteors.splice(i, 1);
          continue;
        }

        const dirDist = Math.hypot(m.dx, m.dy);
        const tailX = m.x - (m.dx / dirDist) * m.length;
        const tailY = m.y - (m.dy / dirDist) * m.length;

        // Glowing streak gradient
        const grad = ctx.createLinearGradient(tailX, tailY, m.x, m.y);
        grad.addColorStop(0, `rgba(99, 102, 241, 0)`);
        grad.addColorStop(0.4, `rgba(168, 85, 247, ${m.opacity * 0.4})`);
        grad.addColorStop(0.85, `rgba(224, 231, 255, ${m.opacity * 0.85})`);
        grad.addColorStop(1, `rgba(255, 255, 255, ${m.opacity})`);

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(tailX, tailY);
        ctx.lineTo(m.x, m.y);
        ctx.strokeStyle = grad;
        ctx.lineWidth = m.size;
        ctx.lineCap = 'round';
        ctx.stroke();

        // Glowing head
        ctx.beginPath();
        ctx.arc(m.x, m.y, m.size * 1.3, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${m.opacity})`;
        ctx.shadowColor = '#a5b4fc';
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.restore();
      }

      requestAnimationFrame(renderFrame);
    }

    requestAnimationFrame(renderFrame);
  }

  // --- Theme Toggle ---
  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      const isLight = document.body.classList.toggle('theme-light');
      if (themeIcon) {
        themeIcon.textContent = isLight ? '☀️' : '🌙';
      }
    });
  }

  // --- Upload Menu Dropdown Toggle ---
  if (uploadMenuBtn && uploadDropdown) {
    uploadMenuBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = uploadDropdown.classList.toggle('open');
      uploadMenuBtn.classList.toggle('active', isOpen);
    });

    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
      if (!uploadDropdown.contains(e.target) && e.target !== uploadMenuBtn) {
        closeUploadMenu();
      }
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeUploadMenu();
      }
    });
  }

  function closeUploadMenu() {
    if (uploadDropdown) uploadDropdown.classList.remove('open');
    if (uploadMenuBtn) uploadMenuBtn.classList.remove('active');
  }

  // --- File & Folder Picker Triggers ---
  if (optUploadFile && filePicker) {
    optUploadFile.addEventListener('click', () => {
      closeUploadMenu();
      filePicker.click();
    });
  }

  if (optUploadFolder && folderPicker) {
    optUploadFolder.addEventListener('click', () => {
      closeUploadMenu();
      folderPicker.click();
    });
  }

  if (filePicker) {
    filePicker.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleSelectedFiles(Array.from(e.target.files));
      }
    });
  }

  if (folderPicker) {
    folderPicker.addEventListener('change', (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleSelectedFiles(Array.from(e.target.files));
      }
    });
  }

  // --- Drag & Drop on Input Bar ---
  if (inputBar) {
    ['dragenter', 'dragover'].forEach((eventName) => {
      inputBar.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        inputBar.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      inputBar.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        inputBar.classList.remove('dragover');
      });
    });

    inputBar.addEventListener('drop', (e) => {
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleSelectedFiles(Array.from(e.dataTransfer.files));
      }
    });
  }

  // --- Handle Selected Files/Folder ---
  function handleSelectedFiles(files) {
    const codeExts = [
      '.py', '.java', '.js', '.ts', '.jsx', '.tsx', '.c', '.cpp', '.h', '.hpp',
      '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala', '.sh',
      '.sql', '.html', '.css', '.json', '.yaml', '.yml', '.md', '.toml', '.txt'
    ];
    const ignoredDirs = ['node_modules', '.git', '.venv', 'venv', '__pycache__', 'dist', 'build', '.next', '.idea', '.vscode'];

    const validFiles = files.filter((f) => {
      const relPath = f.webkitRelativePath || f.name;
      const parts = relPath.split(/[/\\]/);
      if (parts.some((p) => ignoredDirs.includes(p))) return false;
      const ext = relPath.includes('.') ? '.' + relPath.split('.').pop().toLowerCase() : '';
      return codeExts.includes(ext);
    });

    if (validFiles.length === 0) {
      showError('No supported source code files found in selected item.');
      clearUploadedFiles();
      return;
    }

    errorCard.style.display = 'none';
    uploadedFilesState = [];
    let filesLoaded = 0;

    validFiles.forEach((file) => {
      const reader = new FileReader();
      const relPath = file.webkitRelativePath || file.name;

      reader.onload = (e) => {
        uploadedFilesState.push({
          path: relPath,
          content: e.target.result,
          size: file.size,
        });

        filesLoaded++;
        if (filesLoaded === validFiles.length) {
          // All files loaded into memory
          if (validFiles.length === 1) {
            badgeIcon.textContent = '📄';
            badgeText.textContent = validFiles[0].name;
          } else {
            const firstRel = validFiles[0].webkitRelativePath || '';
            const folderName = firstRel.split(/[/\\]/)[0] || 'Folder';
            badgeIcon.textContent = '📁';
            badgeText.textContent = `${folderName} (${validFiles.length} files)`;
          }

          selectedBadge.style.display = 'inline-flex';
          targetInput.value = '';
          targetInput.placeholder = 'Uploaded files ready. Click Start Review to begin...';
          targetInput.focus();
        }
      };
      reader.readAsText(file);
    });
  }

  // --- Clear Uploaded Files ---
  if (clearUploadBtn) {
    clearUploadBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      clearUploadedFiles();
    });
  }

  function clearUploadedFiles() {
    uploadedFilesState = [];
    if (filePicker) filePicker.value = '';
    if (folderPicker) folderPicker.value = '';
    if (selectedBadge) selectedBadge.style.display = 'none';
    if (targetInput) {
      targetInput.placeholder = 'Paste GitHub URL (PR, repo, file), local path, or code...';
    }
  }

  // --- Form Submission ---
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    startReview();
  });

  function resetUI() {
    errorCard.style.display = 'none';
    errorCard.textContent = '';
    diffContainer.innerHTML = '';
    diffContainer.style.display = 'none';
    summaryStrip.style.display = 'none';

    // Reset steps
    stepperContainer.style.display = 'block';
    steps.forEach((step) => {
      const el = document.getElementById(`step-${step}`);
      if (el) el.className = 'step-item';
    });
  }

  function setStepStatus(stepName, status) {
    const el = document.getElementById(`step-${stepName}`);
    if (!el) return;

    if (status === 'running') {
      el.className = 'step-item running';
    } else if (status === 'completed') {
      el.className = 'step-item completed';
    }
  }

  function setButtonsLoading(isLoading) {
    if (submitBtn) {
      submitBtn.disabled = isLoading;
      submitBtn.innerHTML = isLoading
        ? '<span>Analyzing...</span>'
        : '<span>Start Review</span>';
    }
  }

  function cleanup() {
    if (activeEventSource) {
      activeEventSource.close();
      activeEventSource = null;
    }
    if (activeAbortController) {
      activeAbortController.abort();
      activeAbortController = null;
    }
    setButtonsLoading(false);
  }

  function showError(message) {
    errorCard.textContent = message;
    errorCard.style.display = 'block';
  }

  function startReview() {
    cleanup();
    resetUI();
    setButtonsLoading(true);
    setStepStatus('fetch', 'running');

    // 1. If files or folder are uploaded
    if (uploadedFilesState.length > 0) {
      streamPostReview({
        target: '',
        files: uploadedFilesState.map((f) => ({ path: f.path, content: f.content })),
        verify: true,
      });
      return;
    }

    // 2. Otherwise read the text input
    const target = targetInput.value.trim();
    if (!target) {
      showError('Please paste a GitHub URL, enter a local path, or click the upload icon to choose files.');
      cleanup();
      return;
    }

    // Check if raw multi-line code was pasted directly into the input
    if (target.includes('\n') || (target.length > 100 && !target.startsWith('http') && !target.includes('/') && !target.includes('\\'))) {
      streamPostReview({
        target: '',
        code: target,
        filename: 'snippet.code',
        verify: true,
      });
      return;
    }

    // Standard URL or file/folder path
    streamGetReview(target);
  }

  function streamGetReview(target) {
    const streamUrl = `/api/review?target=${encodeURIComponent(target)}&verify=true`;
    activeEventSource = new EventSource(streamUrl);

    activeEventSource.addEventListener('stage', handleStageEvent);
    activeEventSource.addEventListener('finding', handleFindingEvent);
    activeEventSource.addEventListener('summary', handleSummaryEvent);
    activeEventSource.addEventListener('error', handleErrorEvent);
    activeEventSource.addEventListener('done', () => {
      steps.forEach((s) => setStepStatus(s, 'completed'));
      cleanup();
    });

    activeEventSource.onerror = () => {
      cleanup();
    };
  }

  async function streamPostReview(payload) {
    activeAbortController = new AbortController();
    try {
      const response = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: activeAbortController.signal,
      });

      if (!response.ok) {
        showError(`Server error: ${response.status} ${response.statusText}`);
        cleanup();
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep partial line in buffer

        for (const rawMessage of lines) {
          if (!rawMessage.trim()) continue;
          parseAndDispatchSSE(rawMessage);
        }
      }
      steps.forEach((s) => setStepStatus(s, 'completed'));
    } catch (err) {
      if (err.name !== 'AbortError') {
        showError(`Review streaming error: ${err.message}`);
      }
    } finally {
      cleanup();
    }
  }

  function parseAndDispatchSSE(rawMessage) {
    let eventType = 'message';
    let dataStr = '';

    const lines = rawMessage.split('\n');
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        dataStr = line.slice(6).trim();
      }
    }

    const mockEvent = { data: dataStr };
    if (eventType === 'stage') handleStageEvent(mockEvent);
    else if (eventType === 'finding') handleFindingEvent(mockEvent);
    else if (eventType === 'summary') handleSummaryEvent(mockEvent);
    else if (eventType === 'error') handleErrorEvent(mockEvent);
    else if (eventType === 'done') steps.forEach((s) => setStepStatus(s, 'completed'));
  }

  function handleStageEvent(e) {
    try {
      const data = JSON.parse(e.data);
      const stageName = data.name;
      const idx = steps.indexOf(stageName);
      if (idx !== -1) {
        for (let i = 0; i < idx; i++) {
          setStepStatus(steps[i], 'completed');
        }
        setStepStatus(stageName, 'running');
      }
    } catch (err) {
      console.error('Failed to parse stage event', err);
    }
  }

  function handleFindingEvent(e) {
    try {
      const finding = JSON.parse(e.data);
      renderFinding(finding);
    } catch (err) {
      console.error('Failed to parse finding event', err);
    }
  }

  function handleSummaryEvent(e) {
    try {
      const data = JSON.parse(e.data);
      renderSummary(data);
    } catch (err) {
      console.error('Failed to parse summary event', err);
    }
  }

  function handleErrorEvent(e) {
    try {
      if (e.data) {
        const data = JSON.parse(e.data);
        showError(data.message || 'Review failed.');
      } else {
        showError('An error occurred during review.');
      }
    } catch (err) {
      showError('Review failed.');
    }
    cleanup();
  }

  function renderFinding(f) {
    diffContainer.style.display = 'flex';

    const card = document.createElement('div');
    card.className = `finding-card severity-${f.severity || 'medium'}`;

    const header = document.createElement('div');
    header.className = 'finding-header';

    const tag = document.createElement('span');
    tag.className = 'finding-tag';
    tag.textContent = `${f.severity || 'INFO'} • ${f.category || 'DEFECT'}`;

    const loc = document.createElement('span');
    loc.style.fontSize = '0.8rem';
    loc.style.color = 'var(--text-muted)';
    loc.textContent = `${f.file}:${f.line}${f.end_line ? `-${f.end_line}` : ''}`;

    header.appendChild(tag);
    header.appendChild(loc);

    const title = document.createElement('div');
    title.className = 'finding-title';
    title.textContent = f.title;

    const body = document.createElement('div');
    body.className = 'finding-body';
    body.textContent = f.body;

    card.appendChild(header);
    card.appendChild(title);
    card.appendChild(body);

    if (f.suggestion) {
      const sug = document.createElement('pre');
      sug.className = 'finding-suggestion';
      sug.textContent = f.suggestion;
      card.appendChild(sug);
    }

    diffContainer.appendChild(card);
  }

  function renderSummary(data) {
    summaryStrip.style.display = 'grid';

    const findingsCount = data.findings ? data.findings.length : 0;
    const usage = data.usage || {};
    const skippedCount = data.skipped ? data.skipped.length : 0;

    document.getElementById('metricFindings').textContent = findingsCount;
    document.getElementById('metricTokens').textContent = (usage.total_tokens || 0).toLocaleString();
    document.getElementById('metricLatency').textContent = `${usage.latency_ms || 0}ms`;
    document.getElementById('metricSkipped').textContent = skippedCount;

    if (findingsCount === 0 && diffContainer.children.length === 0) {
      diffContainer.style.display = 'flex';
      const cleanCard = document.createElement('div');
      cleanCard.className = 'metric-card';
      cleanCard.style.textAlign = 'center';
      cleanCard.style.padding = '2rem';
      cleanCard.innerHTML = '<div style="font-size: 1.25rem; font-weight: 600; color: #22c55e;">No issues found</div><p style="color: var(--text-secondary); margin-top: 0.5rem;">The code looks clean, safe, and well-structured.</p>';
      diffContainer.appendChild(cleanCard);
    }
  }
});
