// Omi narrator integration
const OMI_BASE = '/omi/';
function matchScoreAccentColor(score01) {
    if (score01 == null || typeof score01 !== 'number' || Number.isNaN(score01)) return '#6b7280';
    const p = score01 * 100;
    if (p >= 85) return '#10b981';
    if (p >= 75) return '#f59e0b';
    if (p >= 50) return '#ef4444';
    return '#7c3aed';
}

function normalizeAccuracy01(value) {
    if (value == null || value === '') return null;
    const n = typeof value === 'number' ? value : parseFloat(value);
    if (Number.isNaN(n)) return null;
    return n > 1 ? n / 100 : n;
}

const OMI_STATES = {
    first: {
        webm: 'First Appearance_Original.webm',
        mp4: 'First Appearance_Lite.mp4',
        loop: false,
        message: 'Hi, I am Omi. I will guide your journey.',
    },
    idle: {
        webm: 'Idle State Motion_Original.webm',
        mp4: 'Idle State Motion_Lite.mp4',
        loop: true,
        message: 'I am here whenever you need help.',
    },
    greet: {
        webm: 'Omi Greeting_Original.webm',
        mp4: 'Omi Greeting_Lite.mp4',
        loop: false,
        message: 'Nice! Let us explore this section together.',
    },
    task: {
        webm: 'Omi Task execution motion_Original.webm',
        mp4: 'Omi Task execution motion_Lite.mp4',
        loop: true,
        message: 'Working on it. Hold tight.',
    },
    input: {
        webm: 'Omi Inputs recording motion_Original.webm',
        mp4: 'Omi Inputs recording motion_Lite.mp4',
        loop: true,
        message: 'Great input. Capturing details now.',
    },
    celebrate: {
        webm: 'Omi Micro-Celebration_Original.webm',
        mp4: 'Omi Micro-Celebration_Lite.mp4',
        loop: false,
        message: 'Awesome! That worked perfectly.',
    },
    caution: {
        webm: 'Omi Caution State_Original.webm',
        mp4: 'Omi Caution State_Lite.mp4',
        loop: false,
        message: 'Hmm, let us fix this together.',
    },
};

let omiCurrentState = 'idle';
let omiHideTimer = null;

function omiAsset(fileName) {
    return OMI_BASE + encodeURIComponent(fileName);
}

function omiSetVideoSource(video, cfg) {
    const webmSrc = cfg.webm ? omiAsset(cfg.webm) : null;
    const mp4Src = cfg.mp4 ? omiAsset(cfg.mp4) : null;
    const desired = webmSrc || mp4Src;
    if (!desired) return;
    if (video.dataset.currentSrc === desired) return;

    let fallbackTried = false;
    video.onerror = function () {
        if (!fallbackTried && mp4Src && video.getAttribute('src') !== mp4Src) {
            fallbackTried = true;
            video.setAttribute('src', mp4Src);
            video.load();
            const playPromise = video.play();
            if (playPromise && typeof playPromise.catch === 'function') playPromise.catch(() => {});
            return;
        }
        const narrator = document.getElementById('omi-narrator');
        if (narrator) narrator.style.display = 'none';
    };

    video.setAttribute('src', desired);
    video.dataset.currentSrc = desired;
    video.load();
}

function omiSpeak(text, duration = 2600) {
    const bubble = document.getElementById('omi-bubble');
    if (!bubble || !text) return;
    bubble.textContent = text;
    bubble.classList.add('show');
    if (omiHideTimer) clearTimeout(omiHideTimer);
    omiHideTimer = setTimeout(() => bubble.classList.remove('show'), duration);
}

function omiPlay(state, customMessage = null) {
    const video = document.getElementById('omi-video');
    const narrator = document.getElementById('omi-narrator');
    if (!video || !narrator) return;
    const cfg = OMI_STATES[state] || OMI_STATES.idle;
    omiCurrentState = state in OMI_STATES ? state : 'idle';
    video.loop = !!cfg.loop;
    omiSetVideoSource(video, cfg);
    const playPromise = video.play();
    if (playPromise && typeof playPromise.catch === 'function') {
        playPromise.catch(() => {});
    }
    omiSpeak(customMessage || cfg.message);
}

function omiStateForSection(id) {
    const map = {
        home: ['greet', 'Welcome! Start with Validation Runs or Industry Surveys.'],
        reports: ['idle', 'Your dashboard gives a quick health check of validations.'],
        surveys: ['input', 'Create and manage survey experiments from here.'],
        validation: ['task', 'Upload synthetic and real files to run comparisons.'],
        results: ['idle', 'Review scores and recommendations here.'],
        'industry-surveys': ['greet', 'Browse industry references and S3 files quickly.'],
        'market-research': ['task', 'Paste or upload a report and I will help reconstruct the questionnaire.'],
        dashboard: ['idle', 'Track metrics and trends in one place.'],
    };
    return map[id] || ['idle', null];
}

function initOmiNarrator() {
    const narrator = document.getElementById('omi-narrator');
    const video = document.getElementById('omi-video');
    const muteBtn = document.getElementById('omi-mute');
    const toggleBtn = document.getElementById('omi-toggle');
    if (!narrator || !video || !muteBtn || !toggleBtn) return;

    video.muted = true;
    muteBtn.addEventListener('click', () => {
        video.muted = !video.muted;
        muteBtn.textContent = video.muted ? '🔇' : '🔊';
    });

    toggleBtn.addEventListener('click', () => {
        narrator.classList.toggle('collapsed');
        toggleBtn.textContent = narrator.classList.contains('collapsed') ? '+' : '–';
        toggleBtn.title = narrator.classList.contains('collapsed') ? 'Show Omi' : 'Hide Omi';
    });

    video.addEventListener('ended', () => {
        if (omiCurrentState !== 'idle' && !video.loop) {
            omiPlay('idle');
        }
    });
    omiPlay('first');
}

function showSection(id) {
    closeMobileMenu();
    // Check if user is authenticated before showing protected sections
    // Without login: allow Dashboard & Reports and Results (View Details from dashboard)
    if (currentUserRole === null && id !== 'reports' && id !== 'results') {
        showNotification('Please log in to access this page', 'warning');
        id = 'reports';
    }
    
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const targetSection = document.getElementById(id);
    if (targetSection) {
        targetSection.classList.add('active');
    }

    // highlight nav - handle combined dashboard-reports
    const sections = ['home','dashboard','surveys','validation','results','industry-surveys','market-research','reports'];
    sections.forEach(key => {
        const btn = document.getElementById(`nav-${key}`);
        if (btn) btn.classList.toggle('active', key === id);
    });
    
    // Handle combined dashboard-reports nav
    const combinedNav = document.getElementById('nav-dashboard-reports');
    if (combinedNav) {
        combinedNav.classList.toggle('active', id === 'reports' || id === 'dashboard');
    }

    const titleMap = {
        home: 'Home',
        dashboard: 'Dashboard & Reports',
        surveys: 'Surveys',
        validation: 'Validation Runs',
        results: 'Test Results',
        'industry-surveys': 'Industry Surveys',
        'market-research': 'Market Research Reverse Engineering',
        reports: 'Dashboard & Reports',
    };
    
    const subtitleMap = {
        home: 'Welcome to SynTera Test Suite - Statistical Validation Framework',
        dashboard: 'Metrics, statistics, and validation reports',
        surveys: 'Manage your survey comparisons',
        validation: 'Compare two questionnaires via file upload or manual data entry',
        results: 'Compare synthetic vs real survey responses question-by-question',
        'industry-surveys': 'Explore standard industry surveys with validation data',
        'market-research': 'Reverse-engineer the original research design from a market research report',
        reports: 'Metrics, statistics, and validation reports for all completed surveys',
    };
    
    const titleEl = document.getElementById('section-title');
    const subtitleEl = document.getElementById('section-subtitle');
    if (titleEl) titleEl.textContent = titleMap[id] || 'Home';
    if (subtitleEl) subtitleEl.textContent = subtitleMap[id] || '';

    const [omiState, omiMessage] = omiStateForSection(id);
    omiPlay(omiState, omiMessage);

    if(id==='surveys') loadSurveys();
    else if(id==='dashboard' || id==='reports') {
        Promise.all([loadDashboard(), loadReports(currentReportsPage)]).catch((err) => console.error(err));
    }
    else if(id==='industry-surveys') {
        loadIndustrySurveys();
    }
    else if(id==='results') {
        loadResultsPage();
    }
    else if (id === 'market-research') {
        loadLatestMarketResearchExtraction();
    }
    // Home section doesn't need any loading function
}

async function loadSurveys() {
    try {
        const surveys = await fetchSurveysList();
        document.getElementById('surveys-list').innerHTML = surveys.map(s =>
            `<div class="survey-card">
                <h3>${formatSurveyTitle(s.title)}</h3>
                <p>Accuracy: ${s.accuracy_score ?? 'N/A'}</p>
                <small>ID: ${s.id}</small>
            </div>`
        ).join('');
    } catch(e) { console.error(e); }
}

async function loadDashboard() {
    try {
        const [surveys, testLabResp] = await Promise.all([
            fetchSurveysList(),
            fetch('/api/validation/test-lab/metrics')
        ]);
        const totalSurveys = Array.isArray(surveys) ? surveys.length : 0;
        document.getElementById('total-surveys').textContent = totalSurveys;

        if (testLabResp.ok) {
            const metrics = await testLabResp.json();
            document.getElementById('validated-surveys').textContent = metrics?.scenarios_covered?.count ?? 0;
            document.getElementById('avg-accuracy').textContent = `${((metrics?.avg_similarity ?? 0) * 100).toFixed(1)}%`;
            document.getElementById('avg-variance-range').textContent = `${((metrics?.avg_directional_alignment ?? 0) * 100).toFixed(1)}%`;
            document.getElementById('avg-stability-indicator').textContent = metrics?.industries_covered?.count ?? 0;
            lastScenarioMix = metrics?.scenarios_covered?.mix || {};
            lastIndustryMix = metrics?.industries_covered?.mix || {};
            const scenarioBtn = document.getElementById('scenario-mix-btn');
            const industryBtn = document.getElementById('industry-mix-btn');
            if (scenarioBtn) scenarioBtn.style.display = Object.keys(lastScenarioMix).length ? 'inline-flex' : 'none';
            if (industryBtn) industryBtn.style.display = Object.keys(lastIndustryMix).length ? 'inline-flex' : 'none';
            return;
        }

        // Fallback to survey-only metrics if test-lab endpoint is unavailable
        const validatedSurveys = surveys.filter(s => s.accuracy_score !== null && s.accuracy_score !== undefined);
        document.getElementById('validated-surveys').textContent = validatedSurveys.length;
        const avgAccuracy = validatedSurveys.length > 0
            ? ((validatedSurveys.reduce((sum, s) => sum + (parseFloat(s.accuracy_score) || 0), 0) / validatedSurveys.length) * 100)
            : 0;
        document.getElementById('avg-accuracy').textContent = avgAccuracy.toFixed(1) + '%';
        document.getElementById('avg-variance-range').textContent = '—';
        document.getElementById('avg-stability-indicator').textContent = '—';
        const scenarioBtn = document.getElementById('scenario-mix-btn');
        const industryBtn = document.getElementById('industry-mix-btn');
        if (scenarioBtn) scenarioBtn.style.display = 'none';
        if (industryBtn) industryBtn.style.display = 'none';
    } catch(e) { 
        console.error('Error loading dashboard:', e);
        document.getElementById('total-surveys').textContent = '0';
        document.getElementById('validated-surveys').textContent = '0';
        document.getElementById('avg-accuracy').textContent = '0%';
        const avgVarianceEl = document.getElementById('avg-variance-range');
        const avgStabilityEl = document.getElementById('avg-stability-indicator');
        if (avgVarianceEl) avgVarianceEl.textContent = '—';
        if (avgStabilityEl) avgStabilityEl.textContent = '—';
        const scenarioBtn = document.getElementById('scenario-mix-btn');
        const industryBtn = document.getElementById('industry-mix-btn');
        if (scenarioBtn) scenarioBtn.style.display = 'none';
        if (industryBtn) industryBtn.style.display = 'none';
    }
}

function createNewSurvey() {
    const title = prompt('Survey title:');
    if(!title) return;
    fetch('/api/surveys/', {method:'POST', body: JSON.stringify({title}),
           headers:{'Content-Type':'application/json'}}).then(async () => {
        invalidateSurveysCache();
        await loadSurveys();
    });
}

async function runValidation() {
    const surveyId = document.getElementById('validation-survey-id').value.trim();
    const syntheticText = document.getElementById('synthetic-input').value;
    const realText = document.getElementById('real-input').value;

    if (!surveyId) {
        showNotification('Please enter a survey ID to continue.', 'warning');
        return;
    }

    let synthetic, real;
    try {
        synthetic = syntheticText ? JSON.parse(syntheticText) : [];
        real = realText ? JSON.parse(realText) : [];
    } catch (e) {
        showNotification('Synthetic/real responses must be valid JSON arrays, e.g. [1,2,3]', 'error');
        return;
    }

    try {
        omiPlay('task', 'Running statistical validation now.');
        const res = await fetch(`/api/validation/attach-and-compare/${surveyId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                synthetic_responses: synthetic,
                real_responses: real
            })
        });
        const data = await res.json();
        
        // Store results and navigate to results page
        storeResultsAndNavigate(data, surveyId);
        omiPlay('celebrate', 'Validation complete! Let us review the results.');
        
        invalidateSurveysCache();
        await Promise.all([loadDashboard(), loadSurveys()]);
    } catch (e) {
        console.error(e);
        omiPlay('caution', 'Validation hit an issue. I can help you retry.');
        showErrorDisplay(
            'Validation Failed',
            'Unable to complete validation. Please check your inputs and try again.',
            e.message,
            '<button onclick="showSection(\'validation\')" class="btn-primary">Go to Validation</button>'
        );
    }
}


function downloadReport(surveyId, format) {
    window.open(`/api/reports/${surveyId}/download?format=${format}`, '_blank');
}

async function loadIndustrySurveys() {
    const surveysList = document.getElementById('industry-surveys-list');
    const s3List = document.getElementById('industry-surveys-s3-list');
    const s3Help = document.getElementById('industry-s3-help');
    if (!surveysList) {
        console.error('Industry surveys list element not found');
        return;
    }

    // Load S3 bucket contents (model-training1 / Dat_for_model_Training/)
    if (s3List && s3Help) {
        try {
            const r = await fetch('/api/industry-surveys/s3');
            if (r.ok) {
                const data = await r.json();
                const items = (data.items || []).slice();
                if (items.length > 0) {
                    s3Help.textContent = 'Industry data';

                    // Group by group_display (short name); keep original group for keying
                    const groups = {};
                    items.forEach(item => {
                        const g = (item.group_display || item.group || 'Other').trim() || 'Other';
                        if (!groups[g]) groups[g] = [];
                        groups[g].push(item);
                    });

                    const groupNames = Object.keys(groups).sort((a, b) => a.localeCompare(b));
                    const PAGE_SIZE = 3;
                    window._industryS3GroupItems = window._industryS3GroupItems || {};
                    groupNames.forEach((_, idx) => {
                        const id = 's3-group-' + idx;
                        window._industryS3GroupItems[id] = groups[groupNames[idx]];
                    });

                    // Populate industry type dropdown and show filter row
                    const filterRow = document.getElementById('industry-s3-filter-row');
                    const filterSelect = document.getElementById('industry-s3-filter');
                    if (filterRow && filterSelect) {
                        filterSelect.innerHTML = '<option value="">All industries</option>' +
                            groupNames.map(function (g) { return '<option value="' + escapeHtml(g) + '">' + escapeHtml(g) + '</option>'; }).join('');
                        filterRow.style.display = 'flex';
                    }
                    const renderCard = (item) => {
                        const sizeStr = item.size != null ? (item.size < 1024 ? item.size + ' B' : (item.size < 1024 * 1024 ? (item.size / 1024).toFixed(1) + ' KB' : (item.size / (1024 * 1024)).toFixed(1) + ' MB')) : '';
                        const dateStr = item.last_modified ? new Date(item.last_modified).toLocaleDateString() : '';
                        const title = item.name_display || item.name || '';
                        return `
                            <div class="industry-s3-card">
                                <div class="industry-survey-header">
                                    <div class="industry-survey-icon" style="background: rgba(59, 130, 246, 0.2); border-color: #3b82f6;">📁</div>
                                    <div class="industry-survey-title-section">
                                        <h3 class="industry-survey-title">${escapeHtml(title)}</h3>
                                    </div>
                                </div>
                                <p class="industry-survey-description">${sizeStr ? sizeStr + (dateStr ? ' · ' + dateStr : '') : '—'}</p>
                                <div class="industry-survey-links">
                                    <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="industry-link-button industry-s3-dl">⬇ Download</a>
                                </div>
                            </div>`;
                    };

                    let html = '';
                    groupNames.forEach((groupName, groupIdx) => {
                        const groupItems = groups[groupName];
                        const totalPages = Math.max(1, Math.ceil(groupItems.length / PAGE_SIZE));
                        const groupId = 's3-group-' + groupIdx;
                        const bodyId = groupId + '-body';
                        const paginationId = groupId + '-pagination';
                        html += `<div class="industry-s3-group" id="${groupId}" data-expanded="true" data-group-name="${escapeHtml(groupName)}">`;
                        html += `<div class="industry-s3-group-header" role="button" tabindex="0" aria-expanded="true" data-toggle="${groupId}">`;
                        html += `<span class="industry-s3-group-chevron">▼</span>`;
                        html += `<h3>${escapeHtml(groupName)}</h3>`;
                        html += `<span class="industry-s3-group-count">${groupItems.length} file${groupItems.length !== 1 ? 's' : ''}</span>`;
                        html += `</div>`;
                        html += `<div class="industry-s3-group-body" id="${bodyId}">`;
                        html += `<div class="industry-s3-group-items" data-page="1" data-total-pages="${totalPages}">`;
                        const page1 = groupItems.slice(0, PAGE_SIZE);
                        page1.forEach(it => { html += renderCard(it); });
                        html += `</div>`;
                        if (totalPages > 1) {
                            html += `<div class="industry-s3-pagination" id="${paginationId}">`;
                            html += `<button type="button" class="industry-s3-page-btn" data-group="${groupId}" data-dir="prev" disabled>Previous</button>`;
                            html += `<span class="industry-s3-page-info">Page 1 of ${totalPages}</span>`;
                            html += `<button type="button" class="industry-s3-page-btn" data-group="${groupId}" data-dir="next">Next</button>`;
                            html += `</div>`;
                        }
                        html += `</div></div>`;
                    });

                    s3List.innerHTML = html;

                    // Collapse/expand group header
                    s3List.querySelectorAll('.industry-s3-group-header[data-toggle]').forEach(header => {
                        header.addEventListener('click', function () {
                            const id = this.getAttribute('data-toggle');
                            const groupEl = document.getElementById(id);
                            if (!groupEl) return;
                            const expanded = groupEl.getAttribute('data-expanded') !== 'false';
                            groupEl.setAttribute('data-expanded', expanded ? 'false' : 'true');
                            const body = groupEl.querySelector('.industry-s3-group-body');
                            const chevron = this.querySelector('.industry-s3-group-chevron');
                            if (body) body.classList.toggle('collapsed', expanded);
                            if (chevron) chevron.textContent = expanded ? '▶' : '▼';
                            this.setAttribute('aria-expanded', expanded ? 'false' : 'true');
                        });
                    });

                    // Industry filter dropdown: show only selected industry or all
                    if (filterSelect) {
                        filterSelect.addEventListener('change', function () {
                            const value = (this.value || '').trim();
                            s3List.querySelectorAll('.industry-s3-group').forEach(function (el) {
                                const name = el.getAttribute('data-group-name') || '';
                                el.style.display = value === '' || name === value ? '' : 'none';
                            });
                        });
                    }

                    // Pagination: re-render current page for that group
                    s3List.querySelectorAll('.industry-s3-page-btn').forEach(btn => {
                        btn.addEventListener('click', function () {
                            const groupId = this.getAttribute('data-group');
                            const dir = this.getAttribute('data-dir');
                            const groupEl = document.getElementById(groupId);
                            if (!groupEl) return;
                            const itemsEl = groupEl.querySelector('.industry-s3-group-items');
                            if (!itemsEl) return;
                            let page = parseInt(itemsEl.getAttribute('data-page'), 10) || 1;
                            const totalPages = parseInt(itemsEl.getAttribute('data-total-pages'), 10) || 1;
                            const items = (window._industryS3GroupItems && window._industryS3GroupItems[groupId]) || [];
                            if (dir === 'next' && page < totalPages) page += 1;
                            else if (dir === 'prev' && page > 1) page -= 1;
                            itemsEl.setAttribute('data-page', String(page));
                            const start = (page - 1) * PAGE_SIZE;
                            const pageItems = items.slice(start, start + PAGE_SIZE);
                            itemsEl.innerHTML = pageItems.map(it => renderCard(it)).join('');
                            const paginationDiv = groupEl.querySelector('.industry-s3-pagination');
                            if (paginationDiv) {
                                const prevBtn = paginationDiv.querySelector('[data-dir="prev"]');
                                const nextBtn = paginationDiv.querySelector('[data-dir="next"]');
                                const infoSpan = paginationDiv.querySelector('.industry-s3-page-info');
                                if (prevBtn) prevBtn.disabled = page <= 1;
                                if (nextBtn) nextBtn.disabled = page >= totalPages;
                                if (infoSpan) infoSpan.textContent = 'Page ' + page + ' of ' + totalPages;
                            }
                        });
                    });
                } else {
                    s3Help.textContent = 'No files in bucket. Configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env if the bucket is private.';
                    s3List.innerHTML = '';
                }
            } else {
                const err = await r.json().catch(() => ({ detail: r.statusText }));
                s3Help.textContent = err.detail || 'Could not load S3 list. Add AWS credentials in .env for private bucket.';
                s3List.innerHTML = '';
            }
        } catch (e) {
            console.error('S3 industry surveys load failed', e);
            s3Help.textContent = 'S3 unavailable. Configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env to list the bucket.';
            s3List.innerHTML = '';
        }
    }

    // Industry survey reference data (6 domains)
    const industrySurveys = [
        {
            id: 'banking-fintech',
            domain: 'Banking & FinTech',
            title: 'Banking & FinTech Adoption Survey',
            description: 'Customer satisfaction and technology adoption survey in the banking sector',
            icon: '🏦',
            color: '#10b981',
            surveyLink: 'https://example.com/surveys/banking-fintech',
            pdfLink: 'https://example.com/pdfs/banking-fintech-report.pdf',
            accuracy: 92.5,
            validatedDate: '2024-01-15',
            testCount: 12,
            pdfReferences: [
                { title: 'RBI - Financial Inclusion Survey Report', url: 'https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=21019' },
                { title: 'NABARD - All India Rural Financial Inclusion Survey', url: 'https://www.nabard.org/content1.aspx?id=1060&catid=8&mid=536' },
                { title: 'RBI - Digital Payment Index Report', url: 'https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=21020' },
                { title: 'CRISIL - Banking Sector Report India', url: 'https://www.crisil.com/en/home/our-analysis/reports/banking-sector.html' },
                { title: 'BCG - Digital Banking in India Report', url: 'https://www.bcg.com/publications/2023/digital-banking-india' }
            ],
            surveyReferences: [
                { title: 'RBI Consumer Confidence Survey', url: 'https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=21018' },
                { title: 'NPCI - Digital Payment Usage Survey', url: 'https://www.npci.org.in/' },
                { title: 'IBEF - Banking Sector Survey India', url: 'https://www.ibef.org/industry/banking-india' },
                { title: 'PwC India - Banking & FinTech Survey', url: 'https://www.pwc.in/industries/financial-services.html' },
                { title: 'EY - Digital Banking Transformation India', url: 'https://www.ey.com/en_in/banking-capital-markets' }
            ]
        },
        {
            id: 'healthcare-patient',
            domain: 'Healthcare',
            title: 'Patient Experience & Care Quality Survey',
            description: 'Patient satisfaction and healthcare quality assessment survey',
            icon: '🏥',
            color: '#00D4EC',
            surveyLink: 'https://example.com/surveys/healthcare-patient',
            pdfLink: 'https://example.com/pdfs/healthcare-patient-report.pdf',
            accuracy: 88.3,
            validatedDate: '2024-01-18',
            testCount: 12,
            pdfReferences: [
                { title: 'NITI Aayog - Health System for New India Report', url: 'https://www.niti.gov.in/health-system-new-india' },
                { title: 'Ministry of Health - National Health Profile', url: 'https://www.cbhidghs.nic.in/showfile.php?lid=1147' },
                { title: 'ICMR - National Family Health Survey', url: 'https://www.nfhsindia.org/' },
                { title: 'WHO India - Health Survey Reports', url: 'https://www.who.int/india/publications' },
                { title: 'PHFI - India Health Report', url: 'https://phfi.org/the-work/research/' }
            ],
            surveyReferences: [
                { title: 'NFHS-5 National Family Health Survey', url: 'https://www.nfhsindia.org/nfhs-5' },
                { title: 'Ministry of Health - Ayushman Bharat Survey', url: 'https://www.pmjay.gov.in/' },
                { title: 'ICMR Health Research Surveys', url: 'https://www.icmr.gov.in/' },
                { title: 'NSSO - Health Expenditure Survey', url: 'https://www.mospi.gov.in/national-sample-survey-office-nsso' },
                { title: 'PwC India - Healthcare Sector Survey', url: 'https://www.pwc.in/industries/healthcare.html' }
            ]
        },
        {
            id: 'retail-consumer',
            domain: 'Retail & E-commerce',
            title: 'Consumer Shopping Behavior Survey',
            description: 'E-commerce preferences and shopping behavior analysis',
            icon: '🛍️',
            color: '#f59e0b',
            surveyLink: 'https://example.com/surveys/retail-consumer',
            pdfLink: 'https://example.com/pdfs/retail-consumer-report.pdf',
            accuracy: 85.7,
            validatedDate: '2024-01-20',
            testCount: 12,
            pdfReferences: [
                { title: 'IBEF - Retail Industry in India Report', url: 'https://www.ibef.org/industry/retail-india' },
                { title: 'CRISIL - E-commerce Market Report India', url: 'https://www.crisil.com/en/home/our-analysis/reports/retail-ecommerce.html' },
                { title: 'Deloitte India - Retail Sector Survey', url: 'https://www2.deloitte.com/in/en/pages/consumer-business/articles/retail-sector.html' },
                { title: 'BCG - Future of Retail in India', url: 'https://www.bcg.com/publications/2023/future-of-retail-india' },
                { title: 'RedSeer - E-commerce Market India Report', url: 'https://redseer.com/reports/india-ecommerce-market/' }
            ],
            surveyReferences: [
                { title: 'IBEF E-commerce Industry Survey', url: 'https://www.ibef.org/industry/ecommerce-india' },
                { title: 'NASSCOM - E-commerce Trends India', url: 'https://nasscom.in/knowledge-center/publications/ecommerce-trends' },
                { title: 'PwC India - Retail & Consumer Survey', url: 'https://www.pwc.in/industries/retail-and-consumer.html' },
                { title: 'EY India - Consumer Products & Retail', url: 'https://www.ey.com/en_in/consumer-products-retail' },
                { title: 'KPMG India - Retail Sector Survey', url: 'https://home.kpmg/in/en/home/industries/consumer-markets.html' }
            ]
        },
        {
            id: 'education-student',
            domain: 'Education',
            title: 'Student Learning Experience Survey',
            description: 'Online learning platforms and educational technology effectiveness',
            icon: '📚',
            color: '#8b5cf6',
            surveyLink: 'https://example.com/surveys/education-student',
            pdfLink: 'https://example.com/pdfs/education-student-report.pdf',
            accuracy: 90.2,
            validatedDate: '2024-01-22',
            testCount: 12,
            pdfReferences: [
                { title: 'Ministry of Education - National Education Policy Report', url: 'https://www.education.gov.in/sites/upload_files/mhrd/files/NEP_Final_English_0.pdf' },
                { title: 'NCERT - National Achievement Survey Report', url: 'https://ncert.nic.in/nas.php' },
                { title: 'UGC - Higher Education Survey India', url: 'https://www.ugc.gov.in/page/Higher-Education-Survey.aspx' },
                { title: 'NITI Aayog - School Education Quality Index', url: 'https://www.niti.gov.in/school-education-quality-index' },
                { title: 'ASER - Annual Status of Education Report', url: 'https://www.asercentre.org/' }
            ],
            surveyReferences: [
                { title: 'NCERT National Achievement Survey', url: 'https://ncert.nic.in/nas.php' },
                { title: 'ASER Annual Education Survey', url: 'https://www.asercentre.org/annual-status-education-report' },
                { title: 'UGC All India Survey on Higher Education', url: 'https://www.ugc.gov.in/page/AISHE.aspx' },
                { title: 'Ministry of Education - Digital Learning Survey', url: 'https://www.education.gov.in/en' },
                { title: 'NASSCOM - EdTech Sector India Report', url: 'https://nasscom.in/knowledge-center/publications/edtech-sector-india' }
            ]
        },
        {
            id: 'technology-ai',
            domain: 'Technology & AI',
            title: 'AI Tools Usage & Adoption Survey',
            description: 'Workplace AI tool adoption and user satisfaction analysis',
            icon: '🤖',
            color: '#6366f1',
            surveyLink: 'https://example.com/surveys/technology-ai',
            pdfLink: 'https://example.com/pdfs/technology-ai-report.pdf',
            accuracy: 87.9,
            validatedDate: '2024-01-25',
            testCount: 12,
            pdfReferences: [
                { title: 'NASSCOM - AI Adoption in India Report', url: 'https://nasscom.in/knowledge-center/publications/ai-adoption-india' },
                { title: 'MeitY - National Strategy for AI', url: 'https://www.meity.gov.in/content/national-strategy-artificial-intelligence' },
                { title: 'NITI Aayog - AI for All Report', url: 'https://www.niti.gov.in/ai-for-all' },
                { title: 'BCG - AI in India Report', url: 'https://www.bcg.com/publications/2023/ai-adoption-india' },
                { title: 'EY India - AI & Automation Survey', url: 'https://www.ey.com/en_in/technology/artificial-intelligence' }
            ],
            surveyReferences: [
                { title: 'NASSCOM Technology Survey India', url: 'https://nasscom.in/knowledge-center/publications/technology-survey' },
                { title: 'IBEF - IT & ITeS Sector India', url: 'https://www.ibef.org/industry/information-technology-india' },
                { title: 'PwC India - AI & Analytics Survey', url: 'https://www.pwc.in/consulting/analytics.html' },
                { title: 'Deloitte India - Technology Survey', url: 'https://www2.deloitte.com/in/en/pages/technology/articles/technology-survey.html' },
                { title: 'KPMG India - Digital Transformation Survey', url: 'https://home.kpmg/in/en/home/insights/2023/digital-transformation.html' }
            ]
        },
        {
            id: 'transportation-mobility',
            domain: 'Transportation & Mobility',
            title: 'Urban Mobility & Transportation Survey',
            description: 'Public transportation usage and urban mobility preferences',
            icon: '🚗',
            color: '#ec4899',
            surveyLink: 'https://example.com/surveys/transportation-mobility',
            pdfLink: 'https://example.com/pdfs/transportation-mobility-report.pdf',
            accuracy: 83.4,
            validatedDate: '2024-01-28',
            testCount: 12,
            pdfReferences: [
                { title: 'Ministry of Road Transport - National Transport Survey', url: 'https://morth.nic.in/' },
                { title: 'Indian Railways - Passenger Satisfaction Survey', url: 'https://indianrailways.gov.in/' },
                { title: 'NITI Aayog - India\'s Electric Mobility Report', url: 'https://www.niti.gov.in/electric-mobility' },
                { title: 'BCG - Urban Mobility India Report', url: 'https://www.bcg.com/publications/2023/urban-mobility-india' },
                { title: 'CRISIL - Transportation Sector India Report', url: 'https://www.crisil.com/en/home/our-analysis/reports/transportation.html' }
            ],
            surveyReferences: [
                { title: 'Ministry of Road Transport Statistics', url: 'https://morth.nic.in/statistics' },
                { title: 'Indian Railways Passenger Survey', url: 'https://indianrailways.gov.in/railwayboard/' },
                { title: 'IBEF - Transportation & Logistics India', url: 'https://www.ibef.org/industry/transport-and-logistics-india' },
                { title: 'PwC India - Automotive Sector Survey', url: 'https://www.pwc.in/industries/automotive.html' },
                { title: 'EY India - Mobility & Transportation', url: 'https://www.ey.com/en_in/automotive-transportation' }
            ]
        }
    ];
    
    surveysList.innerHTML = industrySurveys.map(survey => {
        return `
            <div class="industry-survey-card" style="border-left-color: ${survey.color};">
                <div class="industry-survey-header">
                    <div class="industry-survey-icon" style="background: ${survey.color}20; border-color: ${survey.color};">
                        ${survey.icon}
                    </div>
                    <div class="industry-survey-title-section">
                        <div class="industry-survey-domain" style="color: ${survey.color};">${survey.domain}</div>
                        <h3 class="industry-survey-title">${survey.title}</h3>
                    </div>
                </div>
                <p class="industry-survey-description">${survey.description}</p>
                <div class="industry-survey-stats">
                    <div class="industry-stat">
                        <div class="industry-stat-label">Accuracy</div>
                        <div class="industry-stat-value" style="color: ${survey.color};">${survey.accuracy}%</div>
                    </div>
                    <div class="industry-stat">
                        <div class="industry-stat-label">Tests Run</div>
                        <div class="industry-stat-value">${survey.testCount}</div>
                    </div>
                    <div class="industry-stat">
                        <div class="industry-stat-label">Validated</div>
                        <div class="industry-stat-value">${survey.validatedDate}</div>
                    </div>
                </div>
                <div class="industry-survey-links">
                    <a href="${survey.surveyLink}" target="_blank" class="industry-link-button" style="border-color: ${survey.color}; color: ${survey.color};">
                        <span>🔗</span> View Survey
                    </a>
                    <a href="${survey.pdfLink}" target="_blank" class="industry-link-button" style="border-color: ${survey.color}; color: ${survey.color};">
                        <span>📄</span> Download PDF
                    </a>
                </div>
                <div class="industry-survey-references">
                    <div class="reference-section">
                        <button class="reference-toggle" onclick="toggleReferences('${survey.id}-pdfs')" style="border-color: ${survey.color}; color: ${survey.color};">
                            <span>📚</span> Public Survey PDFs
                            <span class="toggle-icon" id="icon-${survey.id}-pdfs">▼</span>
                        </button>
                        <div class="reference-list" id="${survey.id}-pdfs" style="display: none;">
                            ${survey.pdfReferences.map(ref => `
                                <a href="${ref.url}" target="_blank" class="reference-link" style="border-color: ${survey.color}40;">
                                    <span class="reference-icon">📄</span>
                                    <span class="reference-text">${ref.title}</span>
                                    <span class="reference-arrow">→</span>
                                </a>
                            `).join('')}
                        </div>
                    </div>
                    <div class="reference-section">
                        <button class="reference-toggle" onclick="toggleReferences('${survey.id}-surveys')" style="border-color: ${survey.color}; color: ${survey.color};">
                            <span>🔗</span> Survey Links & Resources
                            <span class="toggle-icon" id="icon-${survey.id}-surveys">▼</span>
                        </button>
                        <div class="reference-list" id="${survey.id}-surveys" style="display: none;">
                            ${survey.surveyReferences.map(ref => `
                                <a href="${ref.url}" target="_blank" class="reference-link" style="border-color: ${survey.color}40;">
                                    <span class="reference-icon">🔗</span>
                                    <span class="reference-text">${ref.title}</span>
                                    <span class="reference-arrow">→</span>
                                </a>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Toggle function for reference sections
function toggleReferences(id) {
    const element = document.getElementById(id);
    const icon = document.getElementById(`icon-${id}`);
    if (element.style.display === 'none') {
        element.style.display = 'block';
        if (icon) icon.textContent = '▲';
    } else {
        element.style.display = 'none';
        if (icon) icon.textContent = '▼';
    }
}

// Market Research Reverse Engineering
async function loadSamplePdfText() {
    const textEl = document.getElementById('market-research-report-text');
    const statusEl = document.getElementById('market-research-status');
    if (!textEl || !statusEl) return;
    statusEl.style.display = 'block';
    statusEl.textContent = 'Loading sample PDF...';
    statusEl.className = 'market-research-status loading';
    omiPlay('input', 'Loading sample report so we can reverse-engineer it.');
    try {
        const opts = { method: 'GET' };
        const token = localStorage.getItem('authToken');
        if (token) opts.headers = { 'Authorization': 'Bearer ' + token };
        const res = await fetch('/api/market-research/sample-pdf-text', opts);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Failed to load sample PDF');
        }
        const data = await res.json();
        textEl.value = data.report_text || '';
        statusEl.textContent = 'Sample PDF loaded. You can now click Reverse-Engineer.';
        statusEl.className = 'market-research-status success';
        omiPlay('celebrate', 'Sample loaded. Ready when you are.');
    } catch (err) {
        statusEl.textContent = err.message || 'Failed to load sample PDF';
        statusEl.className = 'market-research-status error';
        omiPlay('caution', 'Could not load sample PDF. Please try again.');
        showNotification(err.message || 'Sample PDF not found. Place sample_market_research_report.pdf in project root.', 'warning');
    }
}

let lastMarketResearchData = null;

/** Load last persisted reverse-engineer result from API (same shape as POST response). */
async function loadLatestMarketResearchExtraction() {
    const outputPanel = document.getElementById('market-research-output-panel');
    const objectivesEl = document.getElementById('market-research-output-objectives');
    const questionnaireEl = document.getElementById('market-research-output-questionnaire');
    const statusEl = document.getElementById('market-research-status');
    if (!outputPanel || !objectivesEl || !questionnaireEl) return;

    const token = localStorage.getItem('authToken');
    const headers = token ? { Authorization: 'Bearer ' + token } : {};
    try {
        const res = await fetch('/api/market-research/latest-extraction', { headers });
        if (!res.ok) return;
        const body = await res.json();
        if (!body.has_extraction || !body.data) return;

        lastMarketResearchData = body.data;
        renderMarketResearchOutput(body.data, objectivesEl, questionnaireEl);
        outputPanel.style.display = 'block';
        if (statusEl) {
            statusEl.style.display = 'block';
            statusEl.className = 'market-research-status success';
            const when = body.data.persisted_at
                ? new Date(body.data.persisted_at).toLocaleString()
                : '';
            statusEl.textContent = when
                ? 'Loaded last saved extraction (' + when + '). Run Reverse-Engineer to process a new report.'
                : 'Loaded last saved extraction. Run Reverse-Engineer to process a new report.';
        }
    } catch (e) {
        console.warn('Could not load latest market research extraction', e);
    }
}

function notifyMarketResearchSaved(data) {
    if (data && data.extraction_id) {
        showNotification('Report extraction saved to the database.', 'success', 4000);
    }
}

// Chunk size for upload (stay under ~1MB to avoid 413). No limit on total file or text length.
var MAX_UPLOAD_CHARS = 300000;
var MAX_UPLOAD_FILE_BYTES = 900 * 1024;  // files larger than this are sent in chunked upload
var FILE_CHUNK_BYTES = 256 * 1024;        // 256KB per chunk (base64 stays under 1MB)

function generateSessionId() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function readFileChunkAsBase64(file, start, end) {
    return new Promise(function(resolve, reject) {
        var blob = file.slice(start, end);
        var r = new FileReader();
        r.onload = function() {
            var s = r.result;
            resolve(s.substring(s.indexOf(',') + 1));
        };
        r.onerror = reject;
        r.readAsDataURL(blob);
    });
}

async function runMarketResearchReverseEngineer() {
    const textEl = document.getElementById('market-research-report-text');
    const fileEl = document.getElementById('market-research-file');
    const statusEl = document.getElementById('market-research-status');
    const outputPanel = document.getElementById('market-research-output-panel');
    const objectivesEl = document.getElementById('market-research-output-objectives');
    const questionnaireEl = document.getElementById('market-research-output-questionnaire');

    if (!statusEl || !outputPanel || !objectivesEl || !questionnaireEl) return;

    statusEl.style.display = 'block';
    statusEl.className = 'market-research-status loading';
    outputPanel.style.display = 'none';
    omiPlay('task', 'Reverse-engineering report. This can take a moment.');

    const token = localStorage.getItem('authToken');
    const authHeader = token ? { 'Authorization': 'Bearer ' + token } : {};

    try {
        const file = fileEl?.files[0];
        let reportText = (textEl?.value || '').trim();

        if (file && file.size > 0) {
            var totalFileChunks = Math.ceil(file.size / FILE_CHUNK_BYTES);
            if (file.size <= MAX_UPLOAD_FILE_BYTES) {
                statusEl.textContent = 'Processing report...';
                var formData = new FormData();
                formData.append('file', file);
                if (reportText.length >= 50) formData.append('report_text', reportText.length > MAX_UPLOAD_CHARS ? reportText.substring(0, MAX_UPLOAD_CHARS) : reportText);
                var res = await fetch('/api/market-research/reverse-engineer', { method: 'POST', headers: authHeader, body: formData });
                if (!res.ok) {
                    var err = await res.json().catch(function() { return { detail: res.statusText }; });
                    throw new Error(err.detail || 'Reverse engineering failed');
                }
                var data = await res.json();
                lastMarketResearchData = data;
                renderMarketResearchOutput(data, objectivesEl, questionnaireEl);
                outputPanel.style.display = 'block';
                notifyMarketResearchSaved(data);
                if (data.ai_used === false && data.message) {
                    statusEl.innerHTML = '<strong>Placeholder only.</strong> ' + escapeHtml(data.message);
                    statusEl.className = 'market-research-status error';
                    omiPlay('caution', 'No AI key configured. Showing heuristic placeholder.');
                } else {
                    statusEl.textContent = 'Done.';
                    statusEl.className = 'market-research-status success';
                    omiPlay('celebrate', 'Reconstruction ready. Check objectives and questionnaire.');
                }
                return;
            }
            // Chunked file upload: no size limit (e.g. 30MB+)
            var sessionId = generateSessionId();
            for (var fc = 0; fc < totalFileChunks; fc++) {
                statusEl.textContent = 'Uploading file part ' + (fc + 1) + ' of ' + totalFileChunks + '...';
                var fStart = fc * FILE_CHUNK_BYTES;
                var fEnd = Math.min(fStart + FILE_CHUNK_BYTES, file.size);
                var b64 = await readFileChunkAsBase64(file, fStart, fEnd);
                var chunkRes = await fetch('/api/market-research/append-chunk', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', ...authHeader },
                    body: JSON.stringify({
                        session_id: sessionId,
                        chunk_index: fc,
                        total_chunks: totalFileChunks,
                        content: b64,
                        is_file_part: true,
                        filename: fc === 0 ? file.name : undefined
                    })
                });
                if (!chunkRes.ok) {
                    var err = await chunkRes.json().catch(function() { return { detail: chunkRes.statusText }; });
                    throw new Error(err.detail || 'File chunk upload failed');
                }
            }
            statusEl.textContent = 'Extracting text and processing report...';
            var runRes = await fetch('/api/market-research/reverse-engineer-session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeader },
                body: JSON.stringify({ session_id: sessionId })
            });
            if (!runRes.ok) {
                var runErr = await runRes.json().catch(function() { return { detail: runRes.statusText }; });
                throw new Error(runErr.detail || 'Processing failed');
            }
            var data = await runRes.json();
            lastMarketResearchData = data;
            renderMarketResearchOutput(data, objectivesEl, questionnaireEl);
            outputPanel.style.display = 'block';
            notifyMarketResearchSaved(data);
            if (data.ai_used === false && data.message) {
                statusEl.innerHTML = '<strong>Placeholder only.</strong> ' + escapeHtml(data.message);
                statusEl.className = 'market-research-status error';
                omiPlay('caution', 'AI unavailable. Showing heuristic reconstruction.');
            } else {
                statusEl.textContent = 'Done.';
                statusEl.className = 'market-research-status success';
                omiPlay('celebrate', 'Reconstruction complete.');
            }
            return;
        }

        if (reportText.length < 50) {
            statusEl.textContent = 'Please paste at least 50 characters of report text or upload a .txt/.pdf file.';
            statusEl.className = 'market-research-status error';
            return;
        }

        // Pasted text: no length limit. If over MAX_UPLOAD_CHARS, send in chunks then process.
        if (reportText.length <= MAX_UPLOAD_CHARS) {
            statusEl.textContent = 'Processing report...';
            const res = await fetch('/api/market-research/reverse-engineer/json', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeader },
                body: JSON.stringify({ report_text: reportText })
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: res.statusText }));
                throw new Error(err.detail || 'Reverse engineering failed');
            }
            const data = await res.json();
            lastMarketResearchData = data;
            renderMarketResearchOutput(data, objectivesEl, questionnaireEl);
            outputPanel.style.display = 'block';
            notifyMarketResearchSaved(data);
            if (data.ai_used === false && data.message) {
                statusEl.innerHTML = '<strong>Placeholder only.</strong> ' + escapeHtml(data.message);
                statusEl.className = 'market-research-status error';
                omiPlay('caution', 'AI unavailable. Showing heuristic reconstruction.');
            } else {
                statusEl.textContent = 'Done.';
                statusEl.className = 'market-research-status success';
                omiPlay('celebrate', 'Reconstruction complete.');
            }
            return;
        }

        // Chunked upload: send in parts then reverse-engineer-session (no limit on total length)
        var sessionId = generateSessionId();
        var totalChunks = Math.ceil(reportText.length / MAX_UPLOAD_CHARS);
        for (var c = 0; c < totalChunks; c++) {
            statusEl.textContent = 'Uploading part ' + (c + 1) + ' of ' + totalChunks + '...';
            var start = c * MAX_UPLOAD_CHARS;
            var content = reportText.substring(start, start + MAX_UPLOAD_CHARS);
            var chunkRes = await fetch('/api/market-research/append-chunk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...authHeader },
                body: JSON.stringify({ session_id: sessionId, chunk_index: c, total_chunks: totalChunks, content: content })
            });
            if (!chunkRes.ok) {
                var err = await chunkRes.json().catch(function() { return { detail: chunkRes.statusText }; });
                throw new Error(err.detail || 'Chunk upload failed');
            }
        }
        statusEl.textContent = 'Processing report (' + reportText.length + ' chars, ' + totalChunks + ' parts)...';
        var runRes = await fetch('/api/market-research/reverse-engineer-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...authHeader },
            body: JSON.stringify({ session_id: sessionId })
        });
        if (!runRes.ok) {
            var runErr = await runRes.json().catch(function() { return { detail: runRes.statusText }; });
            throw new Error(runErr.detail || 'Processing failed');
        }
        var data = await runRes.json();
        lastMarketResearchData = data;
        renderMarketResearchOutput(data, objectivesEl, questionnaireEl);
        outputPanel.style.display = 'block';
        notifyMarketResearchSaved(data);
        if (data.ai_used === false && data.message) {
            statusEl.innerHTML = '<strong>Placeholder only.</strong> ' + escapeHtml(data.message);
            statusEl.className = 'market-research-status error';
            omiPlay('caution', 'AI unavailable. Showing heuristic reconstruction.');
        } else {
            statusEl.textContent = 'Done.';
            statusEl.className = 'market-research-status success';
            omiPlay('celebrate', 'Reconstruction complete.');
        }
    } catch (err) {
        statusEl.textContent = err.message || 'Request failed.';
        statusEl.className = 'market-research-status error';
        console.error('Market research reverse engineer error:', err);
        omiPlay('caution', 'Reverse engineering failed. Please adjust input and retry.');
    }
}

/**
 * Split raw markdown (actual AI output) into Research Objective (A+B) and Questionnaire (C) sections.
 * Returns { researchObjective: string, questionnaire: string } so we display/download the real output.
 */
function parseRawMarkdownSections(raw) {
    if (!raw || !raw.trim()) return { researchObjective: '', questionnaire: '' };
    const r = raw.trim();
    const blockA = r.match(/A\.\s*Overall Research Objectives\s*([\s\S]*?)(?=B\.|$)/i);
    const blockB = r.match(/B\.\s*Section-wise Objectives\s*([\s\S]*?)(?=C\.|$)/i);
    const blockC = r.match(/C\.\s*Reconstructed Questionnaire\s*([\s\S]*)$/i);
    const partA = blockA ? blockA[1].trim() : '';
    const partB = blockB ? blockB[1].trim() : '';
    const partC = blockC ? blockC[1].trim() : '';
    const researchObjective = [partA, partB].filter(Boolean).join('\n\n');
    const questionnaire = partC || '';
    return { researchObjective, questionnaire, full: r };
}

/** Remove markdown ** bold from text (e.g. **word** -> word, trailing **). */
function stripMarkdownBold(s) {
    if (s == null || typeof s !== 'string') return s;
    let t = s.trim().replace(/\*\*([^*]*)\*\*/g, '$1').replace(/\*\*/g, '');
    return t.trim();
}

/**
 * Parse "C. Reconstructed Questionnaire" raw text into [{ survey_question, question_type, answer_options }].
 */
function parseQuestionnaireFromRaw(rawSectionC) {
    if (!rawSectionC || !rawSectionC.trim()) return [];
    let blocks = [];
    if (rawSectionC.match(/-\s*Survey Question:/i)) {
        blocks = rawSectionC.split(/(?=-\s*Survey Question:)/i).filter(b => b.trim().length > 0);
    }
    if (blocks.length <= 1 && rawSectionC.match(/Survey Question:\s*/i)) {
        blocks = rawSectionC.split(/(?=Survey Question:\s*)/i).filter(b => b.trim().length > 0);
    }
    if (blocks.length <= 1) {
        blocks = rawSectionC.split(/\n(?=-\s*Report Reference:|\n-\s*Research Intent:)/i).filter(b => b.trim().length > 0);
    }
    const questions = [];
    const optRe = /Answer Options:\s*([\s\S]*?)(?=Target Segment:|Expected Output|-\s*Report Reference:|-\s*Research Intent:|-\s*Survey Question:|\Z)/i;
    const surveyRe = /Survey Question:\s*([\s\S]*?)(?=Question Type:|Answer Options:|Target Segment:|$)/i;
    const typeRe = /Question Type:\s*([\s\S]*?)(?=Answer Options:|Target Segment:|$)/i;
    blocks.forEach(blk => {
        const blkStr = blk.trim();
        if (blkStr.length < 10) return;
        const surveyM = blkStr.match(surveyRe);
        const typeM = blkStr.match(typeRe);
        const optM = blkStr.match(optRe);
        let survey_question = surveyM ? surveyM[1].trim() : '';
        if (!survey_question && (blkStr.includes('Survey Question') || blkStr.includes('Question Type'))) {
            const afterLabel = blkStr.replace(/^[\s\S]*?Survey Question:\s*/i, '').trim();
            survey_question = afterLabel.replace(/\n.*?(?=Question Type:|Answer Options:|Target Segment:|$)/is, '').trim();
        }
        if (!survey_question && blkStr.includes('Question Type:')) {
            const beforeType = blkStr.replace(/\n\s*Question Type:[\s\S]*/i, '').replace(/^[\s\S]*?Survey Question:\s*/i, '').trim();
            if (beforeType.length > 2) survey_question = beforeType;
        }
        const question_type = typeM ? typeM[1].trim() : '';
        let answer_options = [];
        if (optM && optM[1]) {
            const optText = optM[1].replace(/^\s*[-•]\s*/gm, '').trim();
            answer_options = optText.split(/[\n]+/).map(line => line.replace(/^\s*[-•]\s*/, '').trim()).filter(o => o && o.length > 0 && o !== 'Option');
            if (answer_options.length === 0) {
                answer_options = optM[1].split(/[-•]/).map(o => o.trim()).filter(o => o && o.length > 0);
            }
        }
        survey_question = stripMarkdownBold(survey_question);
        answer_options = answer_options.map(o => stripMarkdownBold(o)).filter(o => o);
        if (survey_question) {
            questions.push({ survey_question, question_type: stripMarkdownBold(question_type), answer_options });
        }
    });
    return questions;
}

/**
 * Value from report must be numeric only. Return integer string (count); strip any non-numeric/garbage.
 * No percentages in output - backend sends counts only. Blank -> "0".
 */
function formatOptionValueNumericOnly(val) {
    if (val == null || val === '') return '0';
    var s = String(val).trim();
    var numMatch = s.match(/^\s*(\d+)\s*$/);
    if (numMatch) return numMatch[1];
    var anyNum = s.match(/(\d+)/);
    return anyNum ? anyNum[1] : '0';
}

/**
 * Get questionnaire list for display/export: prefer API structured data (includes option_values), else parse from raw.
 */
function getQuestionnaireList(data) {
    const structured = data.reconstructed_questionnaire || [];
    if (structured.length > 0) {
        const overallN = (data.overall_sample_size_n != null && data.overall_sample_size_n > 0) ? parseInt(data.overall_sample_size_n, 10) : null;
        return structured.map(q => {
            const opts = Array.isArray(q.answer_options) ? q.answer_options : [];
            const vals = Array.isArray(q.option_values) ? q.option_values : [];
            const qN = q.sample_size_n != null && q.sample_size_n > 0 ? parseInt(q.sample_size_n, 10) : null;
            const n = qN != null ? qN : overallN;
            return {
                survey_question: stripMarkdownBold(q.survey_question || ''),
                question_type: stripMarkdownBold(q.question_type || ''),
                answer_options: opts.map(o => stripMarkdownBold(String(o))).filter(o => o),
                option_values: vals.map(v => stripMarkdownBold(String(v))).filter(v => v !== undefined && v !== null),
                sample_size_n: n
            };
        });
    }
    const raw = data.raw_markdown || '';
    const sections = parseRawMarkdownSections(raw);
    return parseQuestionnaireFromRaw(sections.questionnaire);
}

function renderMarketResearchOutput(data, objectivesEl, questionnaireEl) {
    const raw = data.raw_markdown || '';
    const aiUsed = data.ai_used !== false;
    const message = data.message || '';

    const sections = parseRawMarkdownSections(raw);
    const hasRealOutput = sections.researchObjective.length > 0 || sections.questionnaire.length > 0;

    let objectivesHtml = '';
    const ctxGeo = data.geography;
    const ctxInd = data.industry;
    const ctxScen = data.scenario;
    if (ctxGeo || ctxInd || ctxScen) {
        objectivesHtml += '<div class="mre-block mre-extracted-context"><h4>Geography, industry & scenario</h4><dl class="mre-context-dl">';
        if (ctxGeo) objectivesHtml += '<dt>Geography</dt><dd>' + escapeHtml(String(ctxGeo)) + '</dd>';
        if (ctxInd) objectivesHtml += '<dt>Industry</dt><dd>' + escapeHtml(String(ctxInd)) + '</dd>';
        if (ctxScen) objectivesHtml += '<dt>Scenario</dt><dd>' + escapeHtml(String(ctxScen)) + '</dd>';
        objectivesHtml += '</dl></div>';
    }
    if (!aiUsed && message) {
        objectivesHtml += '<div class="mre-no-api-key-banner"><strong>No API key.</strong> ' + escapeHtml(message) + '</div>';
    }
    if (hasRealOutput && sections.researchObjective) {
        objectivesHtml += '<pre class="mre-raw-section">' + escapeHtml(sections.researchObjective) + '</pre>';
    } else {
        const overall = data.overall_objectives || [];
        const sectionObjs = data.section_objectives || [];
        objectivesHtml += '<div class="mre-block"><h4>Overall objectives</h4><ul>';
        overall.forEach(obj => { objectivesHtml += '<li>' + escapeHtml(obj) + '</li>'; });
        objectivesHtml += '</ul></div>';
        objectivesHtml += '<div class="mre-block"><h4>Section-wise objectives</h4>';
        sectionObjs.forEach(sec => {
            objectivesHtml += '<div class="mre-section"><strong>' + escapeHtml(sec.section_name || '') + '</strong><p>' + escapeHtml(sec.research_objective || '') + '</p></div>';
        });
        objectivesHtml += '</div>';
    }

    const questionnaireList = getQuestionnaireList(data);
    let questionnaireHtml = '';
    questionnaireList.forEach((q, i) => {
        questionnaireHtml += '<div class="mre-q-item mre-q-survey-only">';
        questionnaireHtml += '<div class="mre-q-survey">Question ' + (i + 1) + ': ' + escapeHtml(q.survey_question || '') + '</div>';
        const opts = Array.isArray(q.answer_options) ? q.answer_options : [];
        const vals = Array.isArray(q.option_values) ? q.option_values : [];
        const n = q.sample_size_n;
        const hasValues = vals.length > 0;
        if (opts.length) {
            questionnaireHtml += '<div class="mre-q-options-label">' + (hasValues ? 'Options & value from report' + (n ? ' (n=' + n + ')' : '') : 'Options') + ':</div>';
            questionnaireHtml += '<ul class="mre-q-options-list">';
            opts.forEach(function(opt, j) {
                const val = vals[j];
                const displayVal = hasValues ? formatOptionValueNumericOnly(val) : '';
                if (displayVal !== '') {
                    questionnaireHtml += '<li><span class="mre-q-opt-text">' + escapeHtml(opt) + '</span> <span class="mre-q-opt-value">' + escapeHtml(displayVal) + '</span></li>';
                } else {
                    questionnaireHtml += '<li>' + escapeHtml(opt) + '</li>';
                }
            });
            questionnaireHtml += '</ul>';
        }
        questionnaireHtml += '</div>';
    });

    if (objectivesEl) objectivesEl.innerHTML = objectivesHtml;
    if (questionnaireEl) questionnaireEl.innerHTML = questionnaireHtml;
}

function downloadMarketResearchPdf() {
    if (!lastMarketResearchData) {
        showNotification('Run Reverse-Engineer first to generate a result.', 'warning');
        return;
    }
    const raw = lastMarketResearchData.raw_markdown || '';
    const sections = parseRawMarkdownSections(raw);
    const useRaw = sections.full.length > 0;
    try {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
        const pageW = doc.internal.pageSize.getWidth();
        const pageH = doc.internal.pageSize.getHeight();
        let y = 22;
        const lineH = 5.5;
        const margin = 22;
        const optIndent = 8;
        const maxW = pageW - margin * 2;
        const maxWOpt = pageW - margin * 2 - optIndent;

        function newPageIfNeeded(needLines) {
            if (y + needLines * lineH > pageH - 25) {
                doc.addPage();
                y = 22;
            }
        }

        const addText = (text, opts = {}) => {
            const lines = doc.splitTextToSize(String(text || ''), opts.maxW || maxW);
            newPageIfNeeded(lines.length);
            lines.forEach(line => {
                doc.text(line, opts.x ?? margin, y);
                y += lineH;
            });
            if (opts.spaceAfter) y += lineH;
        };

        // Title
        doc.setFontSize(18);
        doc.setFont(undefined, 'bold');
        doc.text('Market Research Reverse Engineering', margin, y);
        y += 10;
        doc.setFontSize(10);
        doc.setFont(undefined, 'normal');
        doc.setTextColor(100, 100, 100);
        doc.text('Generated questionnaire from report', margin, y);
        y += 12;
        doc.setTextColor(0, 0, 0);

        // Section 1: Research Objective
        doc.setFont(undefined, 'bold');
        doc.setFontSize(12);
        addText('1. Research Objective', { spaceAfter: true });
        doc.setFont(undefined, 'normal');
        doc.setFontSize(10);
        if (useRaw && sections.researchObjective) {
            addText(sections.researchObjective);
        } else {
            const overall = lastMarketResearchData.overall_objectives || [];
            overall.forEach(obj => { addText('• ' + obj, { spaceAfter: true }); });
            (lastMarketResearchData.section_objectives || []).forEach(sec => {
                addText(sec.section_name || '', { spaceAfter: true });
                addText(sec.research_objective || '', { spaceAfter: true });
            });
        }
        y += 10;

        // Section 2: Questionnaire
        doc.setFont(undefined, 'bold');
        doc.setFontSize(12);
        addText('2. Questionnaire', { spaceAfter: true });
        doc.setFont(undefined, 'normal');
        doc.setFontSize(10);

        const questionnaireList = getQuestionnaireList(lastMarketResearchData);
        if (questionnaireList.length === 0 && useRaw && sections.questionnaire) {
            addText(sections.questionnaire);
        } else {
            questionnaireList.forEach((q, i) => {
                newPageIfNeeded(4);
                const qLabel = 'Question ' + (i + 1) + ':';
                const qText = (q.survey_question || '').trim();
                doc.setFont(undefined, 'bold');
                doc.text(qLabel, margin, y);
                y += lineH;
                doc.setFont(undefined, 'normal');
                const qLines = doc.splitTextToSize(qText, maxW);
                qLines.forEach(line => {
                    newPageIfNeeded(1);
                    doc.text(line, margin, y);
                    y += lineH;
                });
                const opts = Array.isArray(q.answer_options) ? q.answer_options : [];
                const vals = Array.isArray(q.option_values) ? q.option_values : [];
                const hasV = vals.length > 0;
                if (opts.length > 0) {
                    y += 2;
                    opts.forEach((opt, j) => {
                        const optStr = (opt || '').trim();
                        const valStr = hasV ? formatOptionValueNumericOnly(vals[j]) : '0';
                        const lineStr = '• ' + optStr + ' — ' + valStr;
                        const optLines = doc.splitTextToSize(lineStr, maxWOpt);
                        optLines.forEach(line => {
                            newPageIfNeeded(1);
                            doc.text(line, margin + optIndent, y);
                            y += lineH;
                        });
                    });
                }
                y += 8;
            });
        }

        doc.save('market-research-result.pdf');
        showNotification('PDF downloaded.', 'success');
    } catch (e) {
        console.error('PDF download failed:', e);
        showNotification('PDF download failed. Ensure jsPDF is loaded.', 'error');
    }
}

function csvEscape(s) {
    const t = String(s == null ? '' : s).replace(/^["'\s]+|["'\s]+$/g, '').replace(/"/g, '""');
    return '"' + t + '"';
}

function downloadMarketResearchCsv() {
    if (!lastMarketResearchData) {
        showNotification('Run Reverse-Engineer first to generate a result.', 'warning');
        return;
    }
    const questionnaire = getQuestionnaireList(lastMarketResearchData);
    const hasAnyValues = questionnaire.some(q => Array.isArray(q.option_values) && q.option_values.length > 0);
    const headers = hasAnyValues ? ['Q No.', 'Question Description', 'Options', 'Value from report'] : ['Q No.', 'Question Description', 'Options'];
    const rows = [];
    questionnaire.forEach((q, i) => {
        const qNo = i + 1;
        const desc = (q.survey_question || '').trim().replace(/^["']+|["']+$/g, '');
        const opts = Array.isArray(q.answer_options) ? q.answer_options : [];
        const vals = Array.isArray(q.option_values) ? q.option_values : [];
        if (opts.length === 0) {
            rows.push(hasAnyValues ? [qNo, desc, '', ''] : [qNo, desc, '']);
        } else {
            opts.forEach((opt, j) => {
                const optVal = (opt || '').trim().replace(/^["']+|["']+$/g, '');
                const reportVal = formatOptionValueNumericOnly(vals[j]).replace(/^["']+|["']+$/g, '');
                const rowQNo = j === 0 ? qNo : '';
                const rowDesc = j === 0 ? desc : '';
                rows.push(hasAnyValues ? [rowQNo, rowDesc, optVal, reportVal] : [rowQNo, rowDesc, optVal]);
            });
        }
    });
    const csvContent = [headers.map(h => csvEscape(h)).join(','),
        ...rows.map(r => r.map(c => csvEscape(c)).join(','))].join('\r\n');
    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'questionnaire.csv';
    a.click();
    URL.revokeObjectURL(a.href);
    showNotification('Questionnaire CSV downloaded.', 'success');
}

function escapeHtml(s) {
    if (s == null) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}

function formatStudyValidatedAt(d) {
    if (d == null || d === '') return '—';
    const dt = new Date(d);
    if (Number.isNaN(dt.getTime())) return '—';
    return dt.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function shortSurveyId(id) {
    if (!id) return '—';
    const s = String(id);
    if (s.length <= 14) return s;
    return s.slice(0, 8) + '…';
}

// Pagination state
let currentReportsPage = 1;
const reportsPerPage = 1; // one study per page; use pagination for the rest
const testLabProfileCache = new Map();
let surveysListCache = null;
let surveysFetchPromise = null;

function invalidateSurveysCache() {
    surveysListCache = null;
    surveysFetchPromise = null;
    testLabProfileCache.clear();
}

async function fetchSurveysList() {
    if (surveysListCache !== null) return surveysListCache;
    if (!surveysFetchPromise) {
        surveysFetchPromise = fetch('/api/surveys/?summary=1')
            .then(async (r) => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                const surveys = await r.json();
                surveysListCache = Array.isArray(surveys) ? surveys : [];
                return surveysListCache;
            })
            .finally(() => {
                surveysFetchPromise = null;
            });
    }
    return surveysFetchPromise;
}

let pendingLeadSurveyId = null;
let lastScenarioMix = {};
let lastIndustryMix = {};

async function getTestLabProfile(surveyId) {
    if (!surveyId) return null;
    if (testLabProfileCache.has(surveyId)) return testLabProfileCache.get(surveyId);
    try {
        const res = await fetch(`/api/validation/test-lab/profile/${surveyId}`);
        if (!res.ok) return null;
        const profile = await res.json();
        testLabProfileCache.set(surveyId, profile);
        return profile;
    } catch (e) {
        return null;
    }
}

async function fetchTestLabProfilesBatch(surveyIds) {
    const ids = [...new Set((surveyIds || []).filter(Boolean))];
    if (!ids.length) return new Map();
    const missing = ids.filter((id) => !testLabProfileCache.has(id));
    if (missing.length) {
        const qs = encodeURIComponent(missing.join(','));
        try {
            const res = await fetch(`/api/validation/test-lab/profiles/batch?survey_ids=${qs}`);
            if (res.ok) {
                const batch = await res.json();
                missing.forEach((id) => {
                    testLabProfileCache.set(id, batch[id] != null ? batch[id] : null);
                });
            } else {
                await Promise.all(missing.map((id) => getTestLabProfile(id)));
            }
        } catch {
            await Promise.all(missing.map((id) => getTestLabProfile(id)));
        }
    }
    return new Map(ids.map((id) => [id, testLabProfileCache.get(id) || {}]));
}

/** Fieldwork duration buckets (aligns with backend _estimate_human_time). */
function estimateHumanTime(sampleSize) {
    const n = parseInt(sampleSize, 10);
    if (!n || n <= 0) return 'Unknown';
    if (n <= 2000) return '1-2 weeks';
    if (n <= 4000) return '2-3 weeks';
    if (n <= 6000) return '3-4 weeks';
    return '4-5 weeks';
}

const HUMAN_ECON_TOOLTIPS = {
    cost: 'Estimated cost of conducting the human survey: conventional range is $5–$8 per response × sample size (e.g. 2,600 × $5 = $13,000 min and 2,600 × $8 = $20,800 max).',
    time: 'Approximate time for respondents to complete fieldwork, bucketed by sample size (e.g. 1,000–2,000 → 1–2 weeks; 2,001–4,000 → 2–3 weeks; 4,001–6,000 → 3–4 weeks; 6,000+ → 4–5 weeks).',
    effort: 'Estimated hours for data processing, analysis, and report preparation for a standard survey study (typically 80–120 hours).'
};

function formatCurrencyRange(minValue, maxValue) {
    const min = Number(minValue);
    const max = Number(maxValue);
    if (!Number.isFinite(min) && !Number.isFinite(max)) return '—';
    if (Number.isFinite(min) && Number.isFinite(max)) return `$${Math.round(min).toLocaleString()}-$${Math.round(max).toLocaleString()}`;
    const fallback = Number.isFinite(min) ? min : max;
    return `$${Math.round(fallback).toLocaleString()}`;
}

function surveyDisplayName(rawTitle) {
    const t = String(rawTitle || '').trim();
    if (t === 'File Comparison: Food_Delivery_Behavior_AI_Summary.csv vs Food_Delivery_Behavior_Human_Summary.csv') {
        return 'Food Delivery Behavior in India';
    }
    const parsed = formatSurveyName(rawTitle);
    return parsed || 'Food Delivery Behavior';
}

function targetAudienceWithAge(rawAudience) {
    const t = String(rawAudience || '').trim();
    if (!t) return 'Age group: 18-45 years';
    return /age/i.test(t) ? t : `Age group: ${t}`;
}

function derivedIndustry(studyName, profileIndustry) {
    const named = String(profileIndustry || '').trim();
    const s = String(studyName || '').toLowerCase();
    let inferred = 'General';
    if (/food/i.test(s)) inferred = 'Food';
    else if (/\bev\b|electric vehicle|e-vehicle|automotive/i.test(s)) inferred = 'Automotive';
    if (!named || named.toLowerCase() === 'general') return inferred;
    return named;
}

/** Fallback human cost range when economics not yet persisted ($5–$8 per response). */
function estimatedCostFromRespondents(sampleSize) {
    const n = Number(sampleSize || 0);
    if (!n || n <= 0) return '—';
    const min = Math.round(n * 5);
    const max = Math.round(n * 8);
    return `$${min.toLocaleString()}–$${max.toLocaleString()}`;
}

function computeDirectionalAlignment(questionComparisons) {
    if (!Array.isArray(questionComparisons) || questionComparisons.length === 0) return null;
    let aligned = 0;
    let comparable = 0;
    questionComparisons.forEach((q) => {
        const options = Array.isArray(q?.option_comparisons) ? q.option_comparisons : [];
        if (!options.length) return;
        const synTop = options.reduce((a, b) => (Number(a.synthetic_count || 0) >= Number(b.synthetic_count || 0) ? a : b));
        const realTop = options.reduce((a, b) => (Number(a.real_count || 0) >= Number(b.real_count || 0) ? a : b));
        comparable += 1;
        if (String(synTop.option) === String(realTop.option)) aligned += 1;
    });
    if (!comparable) return null;
    return (aligned / comparable) * 100;
}

function formatHumanCostDisplay(econ) {
    if (!econ || typeof econ !== 'object') return '—';
    const min = econ.estimated_cost_min;
    const max = econ.estimated_cost_max;
    if (min != null && max != null) {
        const a = Math.round(Number(min));
        const b = Math.round(Number(max));
        if (!Number.isFinite(a) || !Number.isFinite(b)) return '—';
        if (a === 0 && b === 0) return '—';
        if (a === b) return `$${a.toLocaleString()}`;
        return `$${a.toLocaleString()}–$${b.toLocaleString()}`;
    }
    return '—';
}

/** Display stored 0–1 or 0–100 similarity-style values as a percent string. */
function formatOutcomePercent(val) {
    if (val == null || val === '') return '—';
    const n = Number(val);
    if (Number.isNaN(n)) return '—';
    const pct = n <= 1 ? n * 100 : n;
    return `${pct.toFixed(1)}%`;
}

function vlabelWithTip(text, tipText) {
    return `<span class="vlabel">${escapeHtml(text)} <span class="metric-tip" title="${escapeHtml(tipText)}">i</span></span>`;
}

function renderVerdictBulletList(items) {
    const arr = Array.isArray(items) ? items.filter((t) => t != null && String(t).trim() !== '') : [];
    if (!arr.length) {
        return '<p class="verdict-empty">No verdict bullets stored yet.</p>';
    }
    return `<ul class="verdict-list">${arr.map((t) => `<li>${escapeHtml(String(t))}</li>`).join('')}</ul>`;
}

function renderMixChart(mix) {
    const entries = Object.entries(mix || {}).filter(([, v]) => Number(v) > 0);
    if (entries.length === 0) return '<p class="help-text">No data available.</p>';
    const total = entries.reduce((sum, [, v]) => sum + Number(v), 0);
    const colors = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#a855f7', '#14b8a6', '#f97316'];
    let cumulative = 0;
    const segments = entries.map(([, count], idx) => {
        const value = Number(count);
        const pct = (value / total) * 100;
        const start = cumulative;
        cumulative += pct;
        return `${colors[idx % colors.length]} ${start.toFixed(2)}% ${cumulative.toFixed(2)}%`;
    }).join(', ');
    const legend = entries.map(([name, count], idx) => {
        const pct = ((Number(count) / total) * 100).toFixed(1);
        return `<div class="mix-legend-item"><span class="mix-dot" style="background:${colors[idx % colors.length]}"></span><span>${escapeHtml(name)}: ${count} (${pct}%)</span></div>`;
    }).join('');
    return `
        <div class="mix-pie-wrap">
            <div class="mix-pie" style="background: conic-gradient(${segments});"></div>
            <div class="mix-total">Total: ${total}</div>
        </div>
        <div class="mix-legend">${legend}</div>
    `;
}

function openMixPopup(kind) {
    const modal = document.getElementById('mix-popup-modal');
    const titleEl = document.getElementById('mix-popup-title');
    const contentEl = document.getElementById('mix-popup-content');
    if (!modal || !titleEl || !contentEl) return;
    if (kind === 'scenarios') {
        titleEl.textContent = 'Scenarios Mix';
        contentEl.innerHTML = renderMixChart(lastScenarioMix);
    } else {
        titleEl.textContent = 'Industries Mix';
        contentEl.innerHTML = renderMixChart(lastIndustryMix);
    }
    modal.style.display = 'flex';
}

function closeMixPopup() {
    const modal = document.getElementById('mix-popup-modal');
    if (modal) modal.style.display = 'none';
}

function openLeadCaptureModal(surveyId) {
    pendingLeadSurveyId = surveyId;
    const modal = document.getElementById('lead-capture-modal');
    const errorEl = document.getElementById('lead-form-error');
    if (errorEl) {
        errorEl.style.display = 'none';
        errorEl.textContent = '';
    }
    if (modal) modal.style.display = 'flex';
}

function closeLeadCaptureModal() {
    pendingLeadSurveyId = null;
    const modal = document.getElementById('lead-capture-modal');
    if (modal) modal.style.display = 'none';
}

async function submitLeadCapture() {
    if (!pendingLeadSurveyId) return;
    const surveyId = pendingLeadSurveyId;
    const nameEl = document.getElementById('lead-name');
    const companyEl = document.getElementById('lead-company');
    const emailEl = document.getElementById('lead-email');
    const errorEl = document.getElementById('lead-form-error');
    const payload = {
        name: (nameEl?.value || '').trim(),
        company_name: (companyEl?.value || '').trim(),
        email: (emailEl?.value || '').trim(),
        consent: true,
        source: 'view_detailed_comparison',
        metadata: { section: 'reports' }
    };
    if (!payload.name || !payload.company_name || !payload.email) {
        if (errorEl) {
            errorEl.textContent = 'All fields are required.';
            errorEl.style.display = 'block';
        }
        return;
    }
    try {
        const res = await fetch(`/api/validation/test-lab/lead-capture/${surveyId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Could not capture details.');
        closeLeadCaptureModal();
        if (nameEl) nameEl.value = '';
        if (companyEl) companyEl.value = '';
        if (emailEl) emailEl.value = '';
        await viewReport(surveyId);
    } catch (e) {
        if (errorEl) {
            errorEl.textContent = e.message || 'Could not submit form.';
            errorEl.style.display = 'block';
        }
    }
}

function toggleReportCardChecks(btn) {
    const grid = btn.closest('.synthetic-test-results')?.querySelector('.test-results-grid');
    if (!grid) return;
    const count = btn.dataset.moreCount || '0';
    grid.classList.toggle('is-expanded');
    btn.textContent = grid.classList.contains('is-expanded') ? 'Show less' : `+ ${count} more checks`;
}

async function loadReports(page = 1) {
    currentReportsPage = page;
    const reportsList = document.getElementById('reports-list');
    const paginationContainer = document.getElementById('reports-pagination');
    
    if (!reportsList) {
        console.error('Reports list element not found');
        return;
    }
    
    // Show loading state
    reportsList.innerHTML = '<div class="empty-state"><p>Loading reports...</p></div>';
    
    try {
        const surveys = await fetchSurveysList();
        
        // Filter to only show surveys with validation results
        const validatedSurveys = surveys.filter(s => {
            const hasReport = s.test_suite_report !== null && s.test_suite_report !== undefined;
            const hasAccuracy = s.accuracy_score !== null && s.accuracy_score !== undefined;
            return hasReport && hasAccuracy;
        });
        
        // Sort by date in descending order (latest first)
        validatedSurveys.sort((a, b) => {
            // Prioritize validated_at, fallback to updated_at, then created_at
            const dateA = a.validated_at || a.updated_at || a.created_at || 0;
            const dateB = b.validated_at || b.updated_at || b.created_at || 0;
            // Convert to timestamps for comparison
            const timestampA = dateA ? new Date(dateA).getTime() : 0;
            const timestampB = dateB ? new Date(dateB).getTime() : 0;
            // Descending order (newest first)
            return timestampB - timestampA;
        });
        
        if (validatedSurveys.length === 0) {
            reportsList.innerHTML = `
                <div class="empty-state">
                    <p>No validation reports available yet.</p>
                    <p class="subtitle" style="margin-top: 8px; color: #9ca3af;">Run a validation to generate reports.</p>
                    <p class="subtitle" style="margin-top: 4px; color: #6b7280; font-size: 0.85rem;">Total surveys: ${surveys.length}</p>
                </div>
            `;
            if (paginationContainer) paginationContainer.innerHTML = '';
            return;
        }
        
        // Pagination
        const totalPages = Math.ceil(validatedSurveys.length / reportsPerPage);
        const startIndex = (page - 1) * reportsPerPage;
        const endIndex = startIndex + reportsPerPage;
        const paginatedSurveys = validatedSurveys.slice(startIndex, endIndex);
        const profileMap = await fetchTestLabProfilesBatch(paginatedSurveys.map((s) => s.id));
        
        reportsList.innerHTML = paginatedSurveys.map((s, idx) => {
            const studyIndex = startIndex + idx + 1;
            const totalStudies = validatedSurveys.length;
            const validatedLabel = formatStudyValidatedAt(s.validated_at || s.updated_at || s.created_at);
            const accuracy = s.accuracy_score ? (s.accuracy_score * 100).toFixed(1) : 'N/A';
            const profile = profileMap.get(s.id) || {};
            const humanStudy = profile.human_study || {};
            const sampleSize = humanStudy.sample_size || 0;
            const estimatedCost = estimatedCostFromRespondents(sampleSize);
            const estimatedTime = humanStudy?.economics?.estimated_time_range || estimateHumanTime(sampleSize);
            const estimatedEffort = humanStudy?.economics?.estimated_effort_hours || '80-120 hours';
            const scenario = profile.scenario || '—';
            const rawStudyName = humanStudy.survey_name || s.title || '';
            const commonSurveyName = surveyDisplayName(rawStudyName);
            const industry = derivedIndustry(commonSurveyName, profile.industry);
            const profileGeo = profile.geography || humanStudy.geography || 'India';
            
            // Extract test accuracies from test_suite_report
            const report = s.test_suite_report || {};
            const tests = report.tests || [];
            
            // Get file info if present
            const fileInfo = s.synthetic_personas || {};
            const questionComparisons = s.test_suite_report?.question_comparisons || [];
            const slimQc = Number(fileInfo._question_data_count);
            const questionCount = questionComparisons.length
                || (Number.isFinite(slimQc) && slimQc > 0 ? slimQc : 0)
                || (Array.isArray(fileInfo.question_data) ? fileInfo.question_data.length : 0)
                || 0;
            const syntheticStudy = profile.synthetic_study || {};
            const commonTargetAudience = targetAudienceWithAge(humanStudy.target_audience);
            const humanSampleSize = humanStudy.sample_size || questionCount || 0;
            const humanQuestions = humanStudy.total_questions || questionCount || 0;
            const smPersisted = s.study_metrics || {};
            const pickMetric = (a, b, c) => {
                const v = a != null ? a : (b != null ? b : c);
                return v == null || v === '' ? '—' : escapeHtml(String(v));
            };
            const actionPoints = pickMetric(s.actions_data_points, smPersisted.actions_data_points, syntheticStudy.actions_data_points);
            const neuroPoints = pickMetric(s.neuroscience_data_points, smPersisted.neuroscience_data_points, syntheticStudy.neuroscience_data_points);
            const contextualPoints = pickMetric(s.contextual_layer_data_points, smPersisted.contextual_layer_data_points, syntheticStudy.contextual_layer_data_points);
            const avgSimSource = s.avg_similarity != null ? s.avg_similarity : (smPersisted.avg_similarity != null ? smPersisted.avg_similarity : s.accuracy_score);
            const avgSimilarityDisplay = avgSimSource != null && avgSimSource !== '' ? escapeHtml((Number(avgSimSource) * 100).toFixed(1)) : escapeHtml(accuracy);
            const daStored = s.directional_alignment != null ? s.directional_alignment : smPersisted.directional_alignment;
            const directionalAlignmentPct = daStored != null && daStored !== ''
                ? (Number(daStored) <= 1 ? (Number(daStored) * 100).toFixed(1) : Number(daStored).toFixed(1))
                : null;
            const directionalDisplay = directionalAlignmentPct != null ? escapeHtml(directionalAlignmentPct) + '%' : (() => {
                const live = computeDirectionalAlignment(questionComparisons);
                return live == null ? '—' : escapeHtml(live.toFixed(1)) + '%';
            })();
            const checksSource = s.checks_passed != null ? s.checks_passed : smPersisted.checks_passed;
            const totalTests = tests.filter(t => !t.error).length;
            const checksDisplay = escapeHtml(String(checksSource != null ? checksSource : totalTests));
            const spEconomics = syntheticStudy.economics || {};
            const spCostLabel = spEconomics.cost_display != null && String(spEconomics.cost_display).trim() !== ''
                ? escapeHtml(String(spEconomics.cost_display))
                : '$999';
            const spTime = spEconomics.time_display || '3-4 hrs';
            const spEffort = spEconomics.effort_display || '1-2 hrs';

            const verdict = profile.verdict || {};
            const synStats = syntheticStudy.statistics && typeof syntheticStudy.statistics === 'object' ? syntheticStudy.statistics : {};
            const simPersonas = syntheticStudy.sample_size != null ? syntheticStudy.sample_size : humanSampleSize;
            const synThreadsDisp = syntheticStudy.contextual_conversation_threads != null
                ? escapeHtml(String(syntheticStudy.contextual_conversation_threads))
                : '—';
            const synSourcesDisp = syntheticStudy.contextual_sources_inferred != null
                ? escapeHtml(String(syntheticStudy.contextual_sources_inferred))
                : '—';
            const predAccRaw = s.avg_prediction_accuracy != null ? s.avg_prediction_accuracy : synStats.avg_prediction_accuracy;
            const relStrRaw = s.avg_relationship_strength != null ? s.avg_relationship_strength : synStats.avg_relationship_strength;
            const predDisp = escapeHtml(formatOutcomePercent(predAccRaw));
            const relDisp = escapeHtml(formatOutcomePercent(relStrRaw));
            const humanCostDisp = (() => {
                const d = formatHumanCostDisplay(humanStudy.economics);
                return d !== '—' ? d : estimatedCost;
            })();

            const verdictSource = verdict.source ? String(verdict.source) : '';
            const verdictMetaLine = verdictSource === 'llm'
                ? `<p class="verdict-meta">Source: LLM${verdict.llm_model ? ` (${escapeHtml(String(verdict.llm_model))})` : ''}${verdict.generated_at ? ` · ${escapeHtml(String(verdict.generated_at))}` : ''}</p>`
                : '';
            const verdictInsight = verdict.summary_statement
                ? String(verdict.summary_statement)
                : `Insight: Human and Synthetic People outputs show ${avgSimilarityDisplay}% overall similarity with ${directionalDisplay} directional alignment. Use "Where it differs" to review low-similarity questions and refine calibration.`;

            return `
                <article class="report-card-2x2 verdict-screen-card" aria-label="Study ${studyIndex} of ${totalStudies}: ${escapeHtml(formatSurveyName(s.title || 'Validation run'))}">
                    <div class="verdict-screen-meta">
                        <span class="study-card-pill study-card-pill--industry">${escapeHtml(industry)}</span>
                        <span class="study-card-topbar-meta">
                            <span class="study-card-meta-item"><span class="study-card-meta-key">Validated</span> ${validatedLabel}</span>
                            <span class="study-card-meta-item"><span class="study-card-meta-key">Study</span> ${studyIndex} / ${totalStudies}</span>
                            <span class="study-card-meta-item study-card-meta-id" title="${escapeHtml(s.id)}"><span class="study-card-meta-key">ID</span> ${escapeHtml(shortSurveyId(s.id))}</span>
                        </span>
                    </div>
                    <div class="verdict-split">
                        <section class="verdict-panel verdict-panel-human" aria-label="Human study">
                            <h3 class="verdict-panel-title">Human Study</h3>
                            <div class="verdict-panel-body">
                                <div class="vrow"><span class="vlabel">Survey title</span><strong class="vvalue">${escapeHtml(commonSurveyName)}</strong></div>
                                <div class="vrow"><span class="vlabel">Industry</span><strong class="vvalue">${escapeHtml(industry)}</strong></div>
                                <div class="vrow"><span class="vlabel">Scenario</span><strong class="vvalue">${escapeHtml(scenario)}</strong></div>
                                <div class="vrow"><span class="vlabel">Target audience</span><strong class="vvalue">${escapeHtml(commonTargetAudience)}</strong></div>
                                <div class="vrow"><span class="vlabel">Geography</span><strong class="vvalue">${escapeHtml(profileGeo)}</strong></div>
                                <div class="vrow"><span class="vlabel">Sample size</span><strong class="vvalue">${escapeHtml(humanSampleSize)}</strong></div>
                                <div class="vrow"><span class="vlabel">No. of questions</span><strong class="vvalue">${escapeHtml(humanQuestions)}</strong></div>
                                <div class="verdict-subhead">Economics (human)</div>
                                <div class="vrow">${vlabelWithTip('Est. cost', HUMAN_ECON_TOOLTIPS.cost)}<strong class="vvalue">${humanCostDisp}</strong></div>
                                <div class="vrow">${vlabelWithTip('Est. time', HUMAN_ECON_TOOLTIPS.time)}<strong class="vvalue">${escapeHtml(estimatedTime)}</strong></div>
                                <div class="vrow">${vlabelWithTip('Est. effort', HUMAN_ECON_TOOLTIPS.effort)}<strong class="vvalue">${escapeHtml(estimatedEffort)}</strong></div>
                            </div>
                        </section>
                        <section class="verdict-panel verdict-panel-synthetic" aria-label="Synthetic-people simulation">
                            <h3 class="verdict-panel-title">Synthetic-People simulation</h3>
                            <div class="verdict-panel-body">
                                <div class="vrow"><span class="vlabel">Simulation setup (personas)</span><strong class="vvalue">${escapeHtml(String(simPersonas))}</strong></div>
                                <div class="vrow"><span class="vlabel">Behavior calibration (actions ingested)</span><strong class="vvalue">${actionPoints}</strong></div>
                                <div class="vrow"><span class="vlabel">Neuroscience (signals)</span><strong class="vvalue">${neuroPoints}</strong></div>
                                <div class="vrow"><span class="vlabel">Contextual — conversation threads</span><strong class="vvalue">${synThreadsDisp}</strong></div>
                                <div class="vrow"><span class="vlabel">Contextual — sources inferred</span><strong class="vvalue">${synSourcesDisp}</strong></div>
                                <div class="vrow vrow--hint"><span class="vlabel">Contextual layer (aggregate)</span><strong class="vvalue">${contextualPoints}</strong></div>
                                <div class="verdict-subhead">Outcome matrix</div>
                                <div class="vrow"><span class="vlabel">Avg. similarity</span><strong class="vvalue">${avgSimilarityDisplay}%</strong></div>
                                <div class="vrow"><span class="vlabel">Avg. directional alignment</span><strong class="vvalue">${directionalDisplay}</strong></div>
                                <div class="vrow"><span class="vlabel">Avg. prediction accuracy</span><strong class="vvalue">${predDisp}</strong></div>
                                <div class="vrow"><span class="vlabel">Avg. relationship strength</span><strong class="vvalue">${relDisp}</strong></div>
                                <div class="verdict-subhead">Economics (synthetic)</div>
                                <div class="vrow"><span class="vlabel">Est. cost</span><strong class="vvalue">${spCostLabel}</strong></div>
                                <div class="vrow"><span class="vlabel">Est. time</span><strong class="vvalue">${escapeHtml(spTime)}</strong></div>
                                <div class="vrow"><span class="vlabel">Est. effort</span><strong class="vvalue">${escapeHtml(spEffort)}</strong></div>
                            </div>
                        </section>
                    </div>
                    <section class="verdict-bottom" aria-label="The verdict">
                        <h3 class="verdict-bottom-title">The Verdict</h3>
                        <p class="verdict-summary">${escapeHtml(verdictInsight)}</p>
                        ${verdictMetaLine}
                        <div class="verdict-bottom-columns">
                            <div class="verdict-bottom-block">
                                <h4 class="verdict-bottom-heading">What matches</h4>
                                ${renderVerdictBulletList(verdict.what_matches)}
                            </div>
                            <div class="verdict-bottom-block">
                                <h4 class="verdict-bottom-heading">Where it differs</h4>
                                ${renderVerdictBulletList(verdict.where_it_differs)}
                            </div>
                            <div class="verdict-bottom-block verdict-bottom-block--full">
                                <h4 class="verdict-bottom-heading">Why the difference</h4>
                                ${renderVerdictBulletList(verdict.why_the_difference)}
                            </div>
                        </div>
                    </section>
                    <div class="report-card-actions-2x2">
                        <button onclick="openLeadCaptureModal('${s.id}')" class="btn-view-details">View detailed comparison</button>
                        <button type="button" onclick="downloadReport('${s.id}', 'html')" class="btn-download-small btn-download-label" title="Download HTML report">HTML</button>
                        <button type="button" onclick="downloadReport('${s.id}', 'json')" class="btn-download-small btn-download-label" title="Download JSON">JSON</button>
                        ${authToken ? `<button type="button" onclick="deleteReport('${s.id}')" class="btn-download-small btn-delete-report">Delete</button>` : ''}
                    </div>
                </article>
            `;
        }).join('');
        
        // Render pagination
        if (paginationContainer && totalPages > 1) {
            let paginationHtml = '<div class="pagination">';
            
            // Previous button
            if (page > 1) {
                paginationHtml += `<button onclick="loadReports(${page - 1})" class="pagination-btn">← Previous</button>`;
            } else {
                paginationHtml += `<button class="pagination-btn disabled" disabled>← Previous</button>`;
            }
            
            // Page numbers
            for (let i = 1; i <= totalPages; i++) {
                if (i === page) {
                    paginationHtml += `<button class="pagination-btn active">${i}</button>`;
                } else if (i === 1 || i === totalPages || (i >= page - 1 && i <= page + 1)) {
                    paginationHtml += `<button onclick="loadReports(${i})" class="pagination-btn">${i}</button>`;
                } else if (i === page - 2 || i === page + 2) {
                    paginationHtml += `<span class="pagination-ellipsis">...</span>`;
                }
            }
            
            // Next button
            if (page < totalPages) {
                paginationHtml += `<button onclick="loadReports(${page + 1})" class="pagination-btn">Next →</button>`;
            } else {
                paginationHtml += `<button class="pagination-btn disabled" disabled>Next →</button>`;
            }
            
            paginationHtml += '</div>';
            paginationContainer.innerHTML = paginationHtml;
        } else if (paginationContainer) {
            paginationContainer.innerHTML = '';
        }
        
    } catch(e) { 
        console.error('Error loading reports:', e);
        const reportsList = document.getElementById('reports-list');
        if (reportsList) {
            reportsList.innerHTML = `
                <div class="empty-state">
                    <p>Error loading reports: ${e.message}</p>
                    <p class="subtitle" style="margin-top: 8px; color: #9ca3af;">Check console for details.</p>
                </div>
            `;
        }
    }
}

async function deleteReport(surveyId) {
    if (currentUserRole !== 'super') {
        alert('Only super users can delete reports.');
        return;
    }

    const confirmed = window.confirm('Delete this report permanently? This cannot be undone.');
    if (!confirmed) return;

    try {
        const res = await fetch(`/api/surveys/${surveyId}`, {
            method: 'DELETE'
        });
        if (!res.ok) {
            throw new Error(`Failed to delete report (status ${res.status})`);
        }
        invalidateSurveysCache();
        await Promise.all([loadDashboard(), loadReports(currentReportsPage || 1)]);
    } catch (e) {
        console.error('Error deleting report:', e);
        alert('Could not delete report. Please try again.');
    }
}

async function viewReport(surveyId) {
    try {
        // Fetch full report data
        const res = await fetch(`/api/validation/results/${surveyId}`);
        if (!res.ok) {
            throw new Error('Report not found');
        }
        const data = await res.json();
        
        // Store and navigate to results page
        storeResultsAndNavigate(data, surveyId);
        
    } catch (e) {
        console.error('Error viewing report:', e);
        alert('Could not load report. It may not have validation results yet.');
    }
}

// Store results in sessionStorage and navigate to results page
function storeResultsAndNavigate(resultsData, surveyId) {
    // Ensure surveyId is in the results data
    if (!resultsData.survey_id && surveyId) {
        resultsData.survey_id = surveyId;
    }
    
    // Store results data with consistent structure
    const dataToStore = {
        data: resultsData,
        surveyId: surveyId || resultsData.survey_id,
        survey_id: surveyId || resultsData.survey_id,
        timestamp: new Date().toISOString()
    };
    
    sessionStorage.setItem('lastValidationResults', JSON.stringify(dataToStore));
    
    // Navigate to results page
    showSection('results');
    
    // Load and display results
    loadResultsPage();
}

// Load results page content
async function loadResultsPage() {
    const resultsContent = document.getElementById('results-content');
    if (!resultsContent) return;
    
    const stored = sessionStorage.getItem('lastValidationResults');
    if (!stored) {
        // Show empty state (button: Dashboard when not logged in, Validation Runs when logged in)
        const goToSection = currentUserRole ? 'validation' : 'reports';
        const goToLabel = currentUserRole ? 'Go to Validation Runs' : 'Go to Dashboard';
        resultsContent.innerHTML = `
            <div class="empty-results-state">
                <div class="empty-icon">📊</div>
                <h3>No Results Yet</h3>
                <p>Run a validation from the Validation Runs page to see results here.</p>
                <button id="results-empty-action-btn" onclick="showSection('${goToSection}')" class="btn-primary">${goToLabel}</button>
            </div>
        `;
        return;
    }
    
    try {
        const parsed = JSON.parse(stored);
        const data = parsed.data || parsed;
        const surveyId = parsed.surveyId || parsed.survey_id || data.survey_id;
        
        if (surveyId) {
            try {
                const res = await fetch(`/api/validation/results/${surveyId}`);
                if (res.ok) {
                    const fullData = await res.json();
                    displaySemilatticeStyleResults(fullData, surveyId, resultsContent);
                    return;
                }
            } catch (e) {
                // Use stored data on fetch failure
            }
        }
        // Fallback to stored data - ensure it has the right structure
        const displayData = {
            ...data,
            survey_id: surveyId || data.survey_id,
            survey: data.survey || { 
                id: surveyId || data.survey_id, 
                title: data.title || 'Survey Comparison',
                description: data.description || 'Comparison between synthetic and real survey responses'
            },
            tests: data.tests || [],
            recommendations: data.recommendations || []
        };
        
        // Try the new Semilattice style display, fallback to old style if it fails
        try {
            displaySemilatticeStyleResults(displayData, surveyId, resultsContent);
        } catch (e) {
            displayValidationResults(displayData, surveyId, resultsContent);
        }
    } catch (e) {
        resultsContent.innerHTML = `
            <div class="empty-results-state error-state-enhanced">
                <div class="error-icon-animated">
                    <div class="error-icon-circle-large">
                        <span class="error-icon-emoji-large">⚠️</span>
                    </div>
                    <div class="error-pulse-ring-large"></div>
                    <div class="error-pulse-ring-large"></div>
                </div>
                <h3 class="error-title-enhanced">Error Loading Results</h3>
                <p class="error-message-enhanced">There was an error displaying the results. Please run a new validation.</p>
                <div class="error-details-enhanced">
                    <code>${e.message}</code>
                </div>
                <button onclick="showSection('${currentUserRole ? 'validation' : 'reports'}')" class="btn-primary error-action-button">${currentUserRole ? 'Go to Validation Runs' : 'Go to Dashboard'}</button>
            </div>
        `;
    }
}

// Helper function to format test names
function formatTestName(testName) {
    const names = {
        'chi_square': '📊 Pattern Matching',
        'ks_test': '📈 Distribution Similarity',
        'jensen_shannon': '📉 Statistical Distance',
        'mann_whitney': '🔍 Median Comparison',
        't_test': '📐 Average Comparison',
        'anderson_darling': '✅ Distribution Shape',
        'wasserstein_distance': '📏 Data Alignment',
        'correlation': '🔗 Relationship Strength',
        'error_metrics': '📊 Prediction Accuracy',
        'distribution_summary': '📋 Summary Statistics',
        'kullback_leibler': '📚 Information Gain',
        'cramer_von_mises': '📊 Distribution Equality'
    };
    return names[testName] || testName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

/** Reference: which outcome each engine test targets (matches ml_engine/comparison_engine.py). */
const STATISTICAL_TESTS_GUIDE = [
    { test: 'chi_square', purpose: 'Whether synthetic and real values fall into the same histogram bins (frequency pattern).', keyMetric: 'p-value / match score — higher suggests similar binned counts.' },
    { test: 'ks_test', purpose: 'Whether the two samples follow the same overall distribution (empirical CDF).', keyMetric: 'KS statistic and p-value — smaller D or higher p-value suggests closer distributions.' },
    { test: 'jensen_shannon', purpose: 'Similarity of the two vectors treated as probability masses (symmetric distance).', keyMetric: 'Divergence — lower is closer; match score is derived from 1 − divergence.' },
    { test: 'mann_whitney', purpose: 'Non-parametric comparison of ranks / typical level between the two groups.', keyMetric: 'p-value / match score — higher p-value suggests more similar location.' },
    { test: 't_test', purpose: 'Whether the two groups have the same mean (parametric).', keyMetric: 'p-value / match score — higher p-value suggests similar means.' },
    { test: 'anderson_darling', purpose: 'k-sample test that both samples come from the same distribution (sensitive to tails).', keyMetric: 'p-value or normalized statistic — higher p-value / lower statistic suggests same distribution.' },
    { test: 'wasserstein_distance', purpose: 'Minimum “transport cost” to reshape one empirical distribution into the other.', keyMetric: 'Distance and normalized distance — lower distance means closer distributions.' },
    { test: 'correlation', purpose: 'After trimming to equal length, linear (Pearson) and monotonic (Spearman) alignment point-by-point.', keyMetric: 'Pearson r, Spearman r, average correlation — meaningful only when indices are paired.' },
    { test: 'error_metrics', purpose: 'Mean absolute error and RMSE between aligned synthetic and real series.', keyMetric: 'MAE / RMSE (and normalized) — lower error means closer paired values.' },
    { test: 'distribution_summary', purpose: 'How close means, standard deviations, and medians are between the two samples.', keyMetric: 'Normalized mean/std gaps — smaller gaps mean closer summary statistics.' },
    { test: 'kullback_leibler', purpose: 'Information-theoretic gap between normalized distributions.', keyMetric: 'KL divergence (normalized) — lower divergence means closer distributions.' },
    { test: 'cramer_von_mises', purpose: 'Another two-sample test that both samples share the same underlying distribution.', keyMetric: 'p-value / statistic — higher p-value or lower statistic suggests same distribution.' },
];

function buildStatisticalTestsGuideHtml() {
    const rows = STATISTICAL_TESTS_GUIDE.map((r) => `
        <tr>
            <td><strong>${escapeHtml(formatTestName(r.test))}</strong><span class="stat-tests-id"> (${escapeHtml(r.test)})</span></td>
            <td>${escapeHtml(r.purpose)}</td>
            <td>${escapeHtml(r.keyMetric)}</td>
        </tr>
    `).join('');
    return `
        <div class="stat-tests-guide">
            <h4 class="stat-tests-guide-title">What each statistical test measures</h4>
            <p class="stat-tests-guide-intro">Twelve complementary checks compare synthetic vs real numeric responses. Match each row below to the same <code>test</code> name in your results.</p>
            <div class="stat-tests-guide-scroll">
                <table class="stat-tests-guide-table">
                    <thead>
                        <tr><th>Test</th><th>What it assesses</th><th>Key metric to read</th></tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </div>
    `;
}

// Derive a short "Study Name" from file-comparison titles; no file names or "vs" shown.
function formatSurveyTitle(rawTitle) {
    if (!rawTitle) return '';
    let title = String(rawTitle).trim();
    const prefix = 'File Comparison:';
    if (title.startsWith(prefix)) {
        const rest = title.slice(prefix.length).trim();
        const firstPart = rest.split(/\s+vs\s+/i)[0] || rest;
        let name = firstPart
            .replace(/\.[^.\s]+$/, '')  // strip extension
            .replace(/_AI_Summary$|_Human_Summary$|_AI$|_Human$|_Synthetic$|_Real$/i, '')
            .replace(/[_-]+/g, ' ')
            .trim();
        if (!name) name = 'Validation run';
        return `Study Name: ${name}`;
    }
    return title.replace(/\.[^.\s]+$/, '').replace(/[_-]+/g, ' ').trim() || 'Study';
}

// Return only the display name (value part) for "Study Name: value" so the label can be bold and value normal weight.
function formatSurveyName(rawTitle) {
    const full = formatSurveyTitle(rawTitle);
    if (full.startsWith('Study Name: ')) return full.slice(12);
    return full;
}

// Generate sparkline SVG chart (Excel-style mini chart)
function generateSparkline(data, id, color) {
    if (!data || data.length === 0) return '<div class="sparkline-placeholder">No data</div>';
    
    const width = 120;
    const height = 40;
    const padding = 4;
    const chartWidth = width - (padding * 2);
    const chartHeight = height - (padding * 2);
    
    // Normalize data to fit chart
    const allValues = [];
    data.forEach(d => {
        allValues.push(d.syn, d.real);
    });
    const maxVal = Math.max(...allValues, 1);
    const minVal = Math.min(...allValues, 0);
    const range = maxVal - minVal || 1;
    
    // Generate points for synthetic (top line)
    const synPoints = data.map((d, i) => {
        const x = padding + (i / (data.length - 1 || 1)) * chartWidth;
        const y = padding + chartHeight - ((d.syn - minVal) / range) * chartHeight;
        return `${x},${y}`;
    }).join(' ');
    
    // Generate points for real (bottom line)
    const realPoints = data.map((d, i) => {
        const x = padding + (i / (data.length - 1 || 1)) * chartWidth;
        const y = padding + chartHeight - ((d.real - minVal) / range) * chartHeight;
        return `${x},${y}`;
    }).join(' ');
    
    return `
        <svg class="sparkline-chart" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
            <defs>
                <linearGradient id="grad-${id}-syn" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:${color};stop-opacity:0.8" />
                    <stop offset="100%" style="stop-color:${color};stop-opacity:0.2" />
                </linearGradient>
                <linearGradient id="grad-${id}-real" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" style="stop-color:${color};stop-opacity:0.6" />
                    <stop offset="100%" style="stop-color:${color};stop-opacity:0.1" />
                </linearGradient>
            </defs>
            <polyline points="${synPoints}" fill="none" stroke="${color}" stroke-width="2" opacity="0.8" />
            <polyline points="${realPoints}" fill="none" stroke="${color}" stroke-width="2" opacity="0.6" />
            ${data.map((d, i) => {
                const x = padding + (i / (data.length - 1 || 1)) * chartWidth;
                const synY = padding + chartHeight - ((d.syn - minVal) / range) * chartHeight;
                const realY = padding + chartHeight - ((d.real - minVal) / range) * chartHeight;
                return `
                    <circle cx="${x}" cy="${synY}" r="2" fill="${color}" opacity="0.8" />
                    <circle cx="${x}" cy="${realY}" r="2" fill="${color}" opacity="0.6" />
                `;
            }).join('')}
        </svg>
    `;
}

// User Role System - Based on Account Privileges
let currentUserRole = null; // Will be fetched from backend
let authToken = localStorage.getItem('authToken') || null;

/** Last user activity (ms); survives refresh so idle + hard refresh still end the session. */
const AUTH_LAST_ACTIVITY_KEY = 'authLastActivity';
/** Match default backend ACCESS_TOKEN_EXPIRE_MINUTES (30). */
const AUTH_SESSION_IDLE_MS = 30 * 60 * 1000;
const SESSION_CHECK_INTERVAL_MS = 60 * 1000;
const AUTH_ACTIVITY_TOUCH_MIN_MS = 10 * 1000;
let _authActivityTouchClock = 0;
let _sessionGuardsInstalled = false;

function decodeJwtPayload(token) {
    if (!token || typeof token !== 'string') return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    try {
        let b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const pad = b64.length % 4 ? 4 - (b64.length % 4) : 0;
        b64 += '='.repeat(pad);
        return JSON.parse(atob(b64));
    } catch {
        return null;
    }
}

function getJwtExpirationMs(token) {
    const p = decodeJwtPayload(token);
    return typeof p?.exp === 'number' ? p.exp * 1000 : null;
}

function touchAuthActivityForce() {
    if (!authToken) return;
    _authActivityTouchClock = Date.now();
    localStorage.setItem(AUTH_LAST_ACTIVITY_KEY, String(_authActivityTouchClock));
}

function touchAuthActivity() {
    if (!authToken) return;
    const now = Date.now();
    if (now - _authActivityTouchClock < AUTH_ACTIVITY_TOUCH_MIN_MS) return;
    touchAuthActivityForce();
}

function ensureAuthActivityBaseline() {
    authToken = localStorage.getItem('authToken') || null;
    if (!authToken) return;
    const raw = localStorage.getItem(AUTH_LAST_ACTIVITY_KEY);
    if (!raw || !Number.isFinite(parseInt(raw, 10))) {
        touchAuthActivityForce();
    }
}

function enforceAuthSessionEndIfNeeded() {
    const token = authToken || localStorage.getItem('authToken');
    if (!token) {
        authToken = null;
        return;
    }
    authToken = token;
    const expMs = getJwtExpirationMs(token);
    if (expMs != null && Date.now() >= expMs - 2000) {
        endAuthSession('expired');
        return;
    }
    const raw = localStorage.getItem(AUTH_LAST_ACTIVITY_KEY);
    const last = raw ? parseInt(raw, 10) : NaN;
    if (!Number.isFinite(last)) {
        touchAuthActivityForce();
        return;
    }
    if (Date.now() - last > AUTH_SESSION_IDLE_MS) {
        endAuthSession('idle');
    }
}

/**
 * Clears auth and returns to public reports view.
 * @param {'user'|'idle'|'expired'|'invalid'} reason
 */
function endAuthSession(reason) {
    const hadToken = !!(authToken || localStorage.getItem('authToken'));
    authToken = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem(AUTH_LAST_ACTIVITY_KEY);
    currentUserRole = null;
    if (!hadToken) return;
    invalidateSurveysCache();
    updateNavigationForRole();
    updateUserDisplay();
    currentReportsPage = 1;
    showSection('reports');
    if (reason === 'idle') {
        showNotification('You were logged out due to inactivity.', 'warning', 6000);
    } else if (reason === 'expired' || reason === 'invalid') {
        showNotification('Your session has expired. Please sign in again.', 'warning', 6000);
    } else if (reason === 'user') {
        showNotification('Logged out successfully', 'info');
    }
}

function installSessionGuards() {
    if (_sessionGuardsInstalled) return;
    _sessionGuardsInstalled = true;
    const bump = () => touchAuthActivity();
    ['pointerdown', 'keydown', 'scroll', 'touchstart', 'click'].forEach((evt) => {
        window.addEventListener(evt, bump, { passive: true, capture: true });
    });
    window.addEventListener('pageshow', () => {
        authToken = localStorage.getItem('authToken') || null;
        ensureAuthActivityBaseline();
        enforceAuthSessionEndIfNeeded();
    });
    setInterval(() => enforceAuthSessionEndIfNeeded(), SESSION_CHECK_INTERVAL_MS);
}

// Fetch user privileges from backend
async function fetchUserPrivileges() {
    try {
        const headers = {};
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }
        
        const response = await fetch('/api/auth/check-privileges', {
            headers: headers
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
                currentUserRole = data.is_super_user ? 'super' : 'user';
                touchAuthActivityForce();
                updateNavigationForRole();
                updateUserDisplay();
                return data;
            } else {
                currentUserRole = null;
                if (localStorage.getItem('authToken')) {
                    endAuthSession('invalid');
                    return { authenticated: false, role: null, is_super_user: false };
                }
                return { authenticated: false, role: null, is_super_user: false };
            }
        } else {
            currentUserRole = null;
            return { authenticated: false, role: null, is_super_user: false };
        }
    } catch (error) {
        console.error('Error fetching user privileges:', error);
        currentUserRole = null;
        return { authenticated: false, role: null, is_super_user: false };
    } finally {
        // Always update UI after fetching privileges
        updateNavigationForRole();
        updateUserDisplay();
    }
}

// Login function
async function login(username, password) {
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        if (response.ok) {
            const data = await response.json();
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            touchAuthActivityForce();
            currentUserRole = data.user.role === 'super' ? 'super' : 'user';
            updateNavigationForRole();
            updateUserDisplay();
            currentReportsPage = 1;
            showSection('reports');
            showNotification('Login successful!', 'success');
            return data;
        } else {
            const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
            showNotification(errorData.detail || 'Login failed', 'error');
            return null;
        }
    } catch (error) {
        console.error('Login error:', error);
        showNotification('Login failed. Please try again.', 'error');
        return null;
    }
}

// Logout function (explicit user action)
function logout() {
    endAuthSession('user');
}

// Handle login form submission
async function handleLogin() {
    const username = document.getElementById('login-username')?.value;
    const password = document.getElementById('login-password')?.value;
    
    if (!username || !password) {
        showNotification('Please enter username and password', 'warning');
        return;
    }
    
    const result = await login(username, password);
    if (result) {
        updateUserDisplay();
    }
}

// New User registration modal
function openRegisterModal() {
    const modal = document.getElementById('register-modal');
    if (modal) {
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
        document.getElementById('register-username')?.focus();
        document.getElementById('register-error').style.display = 'none';
    }
}

function closeRegisterModal() {
    const modal = document.getElementById('register-modal');
    if (modal) {
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
        document.getElementById('register-form')?.reset();
        document.getElementById('register-error').style.display = 'none';
    }
}

async function register(username, email, password) {
    const body = { username, password };
    if (email && email.trim()) body.email = email.trim();
    const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: 'Registration failed' }));
        throw new Error(data.detail || 'Registration failed');
    }
    return response.json();
}

async function handleRegister(event) {
    event.preventDefault();
    const username = document.getElementById('register-username')?.value?.trim();
    const email = document.getElementById('register-email')?.value?.trim();
    const password = document.getElementById('register-password')?.value;
    const confirmPassword = document.getElementById('register-password-confirm')?.value;
    const errEl = document.getElementById('register-error');

    if (!username || username.length < 2) {
        errEl.textContent = 'Username must be at least 2 characters.';
        errEl.style.display = 'block';
        return;
    }
    if (password.length < 6) {
        errEl.textContent = 'Password must be at least 6 characters.';
        errEl.style.display = 'block';
        return;
    }
    if (password !== confirmPassword) {
        errEl.textContent = 'Passwords do not match.';
        errEl.style.display = 'block';
        return;
    }

    errEl.style.display = 'none';
    try {
        await register(username, email || null, password);
        closeRegisterModal();
        const loggedIn = await login(username, password);
        if (loggedIn) {
            updateUserDisplay();
            showNotification('Account created. You are now logged in.', 'success');
        }
    } catch (e) {
        errEl.textContent = e.message || 'Registration failed.';
        errEl.style.display = 'block';
    }
}

// Update user display in sidebar
function updateUserDisplay() {
    const userInfoDisplay = document.getElementById('user-info-display');
    const loginFormDisplay = document.getElementById('login-form-display');
    const usernameDisplay = document.getElementById('username-display');
    
    if (authToken) {
        // Show user info, hide login form
        if (userInfoDisplay) userInfoDisplay.style.display = 'block';
        if (loginFormDisplay) loginFormDisplay.style.display = 'none';
        if (usernameDisplay) usernameDisplay.textContent = 'Loading...';
        
        // Fetch full user info
        fetch('/api/auth/me', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        }).then(res => {
            if (res.ok) {
                return res.json();
            }
        }).then(user => {
            if (user && usernameDisplay) {
                usernameDisplay.textContent = user.username;
            }
        }).catch(() => {
            if (usernameDisplay) usernameDisplay.textContent = 'User';
        });
    } else {
        // Show login form, hide user info
        if (userInfoDisplay) userInfoDisplay.style.display = 'none';
        if (loginFormDisplay) loginFormDisplay.style.display = 'block';
    }

    // Dashboard: show Start New Validation / View All Experiments only when logged in
    const dashboardActions = document.getElementById('dashboard-actions');
    if (dashboardActions) dashboardActions.style.display = authToken ? '' : 'none';

    // Results header button: "Dashboard" when not logged in, "Run New Validation" when logged in
    const resultsHeaderBtn = document.getElementById('results-header-action-btn');
    if (resultsHeaderBtn) {
        if (authToken) {
            resultsHeaderBtn.textContent = '← Run New Validation';
            resultsHeaderBtn.onclick = () => showSection('validation');
        } else {
            resultsHeaderBtn.textContent = '← Dashboard';
            resultsHeaderBtn.onclick = () => showSection('reports');
        }
    }

    // Results empty state button (when visible)
    const resultsEmptyBtn = document.getElementById('results-empty-action-btn');
    if (resultsEmptyBtn) {
        if (authToken) {
            resultsEmptyBtn.textContent = 'Go to Validation Runs';
            resultsEmptyBtn.onclick = () => showSection('validation');
        } else {
            resultsEmptyBtn.textContent = 'Go to Dashboard';
            resultsEmptyBtn.onclick = () => showSection('reports');
        }
    }
}

function updateNavigationForRole() {
    const navHome = document.getElementById('nav-home');
    const navDashboardReports = document.getElementById('nav-dashboard-reports');
    const navSurveys = document.getElementById('nav-surveys');
    const navValidation = document.getElementById('nav-validation');
    const navResults = document.getElementById('nav-results');
    const navIndustrySurveys = document.getElementById('nav-industry-surveys');
    const navMarketResearch = document.getElementById('nav-market-research');
    
    if (currentUserRole === null) {
        // Not logged in: show only Dashboard & Reports
        if (navHome) navHome.style.display = 'none';
        if (navDashboardReports) navDashboardReports.style.display = '';
        if (navSurveys) navSurveys.style.display = 'none';
        if (navValidation) navValidation.style.display = 'none';
        if (navResults) navResults.style.display = 'none';
        if (navIndustrySurveys) navIndustrySurveys.style.display = 'none';
        if (navMarketResearch) navMarketResearch.style.display = 'none';
    } else if (currentUserRole === 'user') {
        // User: show all except maybe admin-only in the future
        if (navHome) navHome.style.display = '';
        if (navDashboardReports) navDashboardReports.style.display = '';
        if (navSurveys) navSurveys.style.display = '';
        if (navValidation) navValidation.style.display = '';
        if (navResults) navResults.style.display = '';
        if (navIndustrySurveys) navIndustrySurveys.style.display = '';
        if (navMarketResearch) navMarketResearch.style.display = '';
    } else {
        // Super User: Show all tabs
        if (navHome) navHome.style.display = '';
        if (navDashboardReports) navDashboardReports.style.display = '';
        if (navSurveys) navSurveys.style.display = '';
        if (navValidation) navValidation.style.display = '';
        if (navResults) navResults.style.display = '';
        if (navIndustrySurveys) navIndustrySurveys.style.display = '';
        if (navMarketResearch) navMarketResearch.style.display = '';
    }
}

// Combined Dashboard & Reports function for regular users
function showCombinedDashboardReports() {
    currentReportsPage = 1;
    showSection('reports');
}

// Initialize navigation on page load
document.addEventListener('DOMContentLoaded', async () => {
    initOmiNarrator();
    installSessionGuards();
    ensureAuthActivityBaseline();
    enforceAuthSessionEndIfNeeded();
    // First, set up basic UI state
    updateNavigationForRole();
    updateUserDisplay();

    // Allow pressing Enter in password field to trigger login
    const passwordInput = document.getElementById('login-password');
    if (passwordInput) {
        passwordInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                handleLogin();
            }
        });
    }
    
    try {
        // Fetch user privileges from backend
        const authData = await fetchUserPrivileges();
        
        // Load default page based on authentication status
        if (authData && authData.authenticated) {
            currentReportsPage = 1;
            showSection('reports');
        } else {
            currentReportsPage = 1;
            showSection('reports');
        }
    } catch (error) {
        console.error('Error during initialization:', error);
        // Fallback: show Dashboard & Reports if anything fails
        showSection('reports');
    }
    
    // Restore sidebar state - collapse by default
    const sidebarCollapsed = localStorage.getItem('sidebarCollapsed');
    if (sidebarCollapsed === null || sidebarCollapsed === 'true') {
        // Default to collapsed
        const appShell = document.querySelector('.app-shell');
        if (appShell) {
            appShell.classList.add('sidebar-collapsed');
            localStorage.setItem('sidebarCollapsed', 'true');
        }
    }
    
    // File input change handlers
    document.getElementById('file-synthetic')?.addEventListener('change', (e) => {
        const file = e.target.files[0];
        document.getElementById('file-synthetic-info').textContent = 
            file ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)` : 'No file selected';
    });
    
    document.getElementById('file-real')?.addEventListener('change', (e) => {
        const file = e.target.files[0];
        document.getElementById('file-real-info').textContent = 
            file ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)` : 'No file selected';
    });

    document.getElementById('market-research-submit')?.addEventListener('click', runMarketResearchReverseEngineer);

    document.getElementById('market-research-load-sample')?.addEventListener('click', loadSamplePdfText);
    document.getElementById('market-research-download-pdf')?.addEventListener('click', downloadMarketResearchPdf);
    document.getElementById('market-research-download-csv')?.addEventListener('click', downloadMarketResearchCsv);

    // Close register modal on overlay click or Escape
    document.getElementById('register-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'register-modal') closeRegisterModal();
    });
    document.getElementById('lead-capture-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'lead-capture-modal') closeLeadCaptureModal();
    });
    document.getElementById('mix-popup-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'mix-popup-modal') closeMixPopup();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.getElementById('register-modal');
            if (modal && modal.style.display === 'flex') closeRegisterModal();
            const leadModal = document.getElementById('lead-capture-modal');
            if (leadModal && leadModal.style.display === 'flex') closeLeadCaptureModal();
            const mixModal = document.getElementById('mix-popup-modal');
            if (mixModal && mixModal.style.display === 'flex') closeMixPopup();
        }
    });
});

// Display results in Semilattice.ai style
function displaySemilatticeStyleResults(data, surveyId, targetDiv) {
    if (!targetDiv) {
        console.error('displaySemilatticeStyleResults: targetDiv is null');
        return;
    }
    
    try {
        const survey = data.survey || {};
        const fileInfo = data.file_info || {};
        let questionComparisons = data.question_comparisons || [];
        if (!questionComparisons || questionComparisons.length === 0) {
            const results = data.results || {};
            questionComparisons = results.question_comparisons || data.question_comparisons || [];
        }
        
        const acc01 = normalizeAccuracy01(data.overall_accuracy ?? data.accuracy);
        const accuracyValue = acc01 != null ? acc01 : 0;
        const accuracy = (accuracyValue * 100).toFixed(1);
        const accentColor = acc01 != null ? matchScoreAccentColor(acc01) : '#6b7280';
    
    const createdDate = survey.created_at ? new Date(survey.created_at).toLocaleString() : 'N/A';
    const validatedDate = survey.validated_at ? new Date(survey.validated_at).toLocaleString() : 'N/A';
    
    // Model details section – compact; no synthetic/real file names
    const modelDetailsHtml = `
        <div class="model-details-card model-details-compact">
            <div class="model-details-header">
                <div>
                    <h3><strong class="seed-label-bold">Study Name:</strong> <span class="seed-value-normal">${formatSurveyName(survey.title || 'Survey Comparison')}</span></h3>
                    <p class="model-description">${survey.description || 'Comparison between synthetic and real survey responses'}</p>
                </div>
                <div class="model-id-section">
                    <div class="model-id">
                        <span class="model-id-label">ID:</span>
                        <span class="model-id-value" id="survey-id-display">${surveyId || survey.id || 'N/A'}</span>
                        <button class="copy-btn" onclick="copyToClipboard('${surveyId || survey.id || ''}')" title="Copy ID">📋</button>
                    </div>
                </div>
            </div>
            <div class="model-details-grid">
                <div class="model-detail-item">
                    <div class="model-detail-label">Target Population</div>
                    <div class="model-detail-value">Survey Respondents</div>
                </div>
                <div class="model-detail-item">
                    <div class="model-detail-label">Created</div>
                    <div class="model-detail-value">${createdDate}</div>
                </div>
                <div class="model-detail-item">
                    <div class="model-detail-label">Validated</div>
                    <div class="model-detail-value">${validatedDate}</div>
                </div>
                <div class="model-detail-item">
                    <div class="model-detail-label">Question Count</div>
                    <div class="model-detail-value">${questionComparisons.length > 0 ? questionComparisons.length : (fileInfo.synthetic_question_count || fileInfo.real_question_count || 0)}</div>
                </div>
                <div class="model-detail-item">
                    <div class="model-detail-label">Overall File Accuracy</div>
                    <div class="model-detail-value" style="color: ${accentColor}">${accuracy}%</div>
                </div>
            </div>
        </div>
    `;
    
    // Statistical Methodology Section
    const methodologyHtml = `
        <div class="statistical-methodology-section">
            <div class="methodology-header">
                <h3>📊 Statistical Methodology</h3>
                <p class="methodology-description">Our validation framework uses 12 comprehensive statistical tests to assess the similarity between synthetic and real survey responses:</p>
            </div>
            <div class="methodology-tests-grid">
                <div class="methodology-test-item">
                    <div class="test-method-icon">📊</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Chi-Square Test</div>
                        <div class="test-method-desc">Compares frequency distributions to assess pattern matching</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">📈</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Kolmogorov-Smirnov Test</div>
                        <div class="test-method-desc">Evaluates cumulative distribution similarity</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">📉</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Jensen-Shannon Divergence</div>
                        <div class="test-method-desc">Measures probability distribution similarity</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">🔍</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Mann-Whitney U Test</div>
                        <div class="test-method-desc">Compares medians between distributions</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">📐</div>
                    <div class="test-method-content">
                        <div class="test-method-name">T-Test</div>
                        <div class="test-method-desc">Assesses mean value differences</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">✅</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Anderson-Darling Test</div>
                        <div class="test-method-desc">Tests if samples come from same distribution</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">📏</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Wasserstein Distance</div>
                        <div class="test-method-desc">Measures minimum cost to transform distributions</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">🔗</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Correlation Tests</div>
                        <div class="test-method-desc">Pearson & Spearman correlation analysis</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">📊</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Error Metrics</div>
                        <div class="test-method-desc">Mean Absolute Error & Root Mean Square Error</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">📋</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Distribution Summary</div>
                        <div class="test-method-desc">Compares mean, median, and standard deviation</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">📚</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Kullback-Leibler Divergence</div>
                        <div class="test-method-desc">Measures information gain between distributions</div>
                    </div>
                </div>
                <div class="methodology-test-item">
                    <div class="test-method-icon">📊</div>
                    <div class="test-method-content">
                        <div class="test-method-name">Cramér-von Mises Test</div>
                        <div class="test-method-desc">Two-sample distribution equality test</div>
                    </div>
                </div>
            </div>
            <div class="methodology-note">
                <strong>Note:</strong> Each test provides a match score (0–100%). Higher scores indicate closer alignment between synthetic and real response patterns.
                Overall accuracy is derived from the combined test results.
            </div>
        </div>
    `;
    
    // Tabs - always show Question-by-Question tab first, then Summary if no question data
    const tabsHtml = `
        <div class="results-tabs">
            <button class="results-tab active" onclick="switchResultsTab('questions')" id="tab-questions">Question-by-Question ${questionComparisons.length > 0 ? `(${questionComparisons.length})` : ''}</button>
            ${questionComparisons.length === 0 ? `<button class="results-tab" onclick="switchResultsTab('summary')" id="tab-summary">Summary</button>` : ''}
        </div>
    `;
    
    // Question-by-question table with option-level comparison (no sparklines)
    let questionsTableHtml = '';
    if (questionComparisons.length > 0) {
        questionsTableHtml = `
            <div id="tab-content-questions" class="results-tab-content active">
                <div class="questions-table-container">
                    <table class="questions-table">
                        <thead>
                            <tr>
                                <th>Question</th>
                                <th>Options Comparison</th>
                                <th>Type</th>
                                <th>Match Score</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${questionComparisons.map((q, idx) => {
                                const qScore = q.match_score != null ? Number(q.match_score) : null;
                                const qAccent = qScore != null && !Number.isNaN(qScore) ? matchScoreAccentColor(qScore) : '#6b7280';
                                const matchPercent = qScore != null && !Number.isNaN(qScore) ? (qScore * 100).toFixed(1) : '—';
                                const optionComparisons = q.option_comparisons || [];
                                
                                // Bar chart: Y = options, X = count; Humans = green, Synthetic = red; count beside each bar
                                const HUMAN_COLOR = '#22c55e';
                                const SYNTHETIC_COLOR = '#ef4444';
                                let optionsHtml = '';
                                if (optionComparisons.length > 0) {
                                    const maxCount = Math.max(1, ...optionComparisons.flatMap(opt => [opt.real_count || 0, opt.synthetic_count || 0]));
                                    optionsHtml = `
                                        <div class="q-bar-chart" role="img" aria-label="Humans vs Synthetic comparison">
                                            <div class="q-bar-chart-legend">
                                                <span class="q-bar-legend-item" style="background:${HUMAN_COLOR}"></span> Humans
                                                <span class="q-bar-legend-item" style="background:${SYNTHETIC_COLOR}"></span> Synthetic
                                            </div>
                                            <div class="q-bar-chart-y-axis-label">Option</div>
                                            <div class="q-bar-chart-bars">
                                                ${optionComparisons.map(opt => {
                                                    const synCount = opt.synthetic_count || 0;
                                                    const realCount = opt.real_count || 0;
                                                    const realPct = Math.round((realCount / maxCount) * 100);
                                                    const synPct = Math.round((synCount / maxCount) * 100);
                                                    const realDisplay = Math.round(realCount);
                                                    const synDisplay = Math.round(synCount);
                                                    return `
                                                        <div class="q-bar-row">
                                                            <div class="q-bar-y-label" title="${opt.option}">${opt.option}</div>
                                                            <div class="q-bar-group">
                                                                <div class="q-bar-slot">
                                                                    <div class="q-bar q-bar-human" style="width:${realPct}%; background:${HUMAN_COLOR};" title="Humans: ${realDisplay}"></div>
                                                                    <span class="q-bar-count-inline human">${realDisplay}</span>
                                                                </div>
                                                                <div class="q-bar-slot">
                                                                    <div class="q-bar q-bar-synthetic" style="width:${synPct}%; background:${SYNTHETIC_COLOR};" title="Synthetic: ${synDisplay}"></div>
                                                                    <span class="q-bar-count-inline synthetic">${synDisplay}</span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    `;
                                                }).join('')}
                                            </div>
                                        </div>
                                    `;
                                } else {
                                    const synTotal = q.synthetic_total || 0;
                                    const realTotal = q.real_total || 0;
                                    const maxCount = Math.max(realTotal, synTotal, 1);
                                    const realPct = Math.round((realTotal / maxCount) * 100);
                                    const synPct = Math.round((synTotal / maxCount) * 100);
                                    const realDisplay = Math.round(realTotal);
                                    const synDisplay = Math.round(synTotal);
                                    optionsHtml = `
                                        <div class="q-bar-chart">
                                            <div class="q-bar-chart-legend">
                                                <span class="q-bar-legend-item" style="background:${HUMAN_COLOR}"></span> Humans
                                                <span class="q-bar-legend-item" style="background:${SYNTHETIC_COLOR}"></span> Synthetic
                                            </div>
                                            <div class="q-bar-row">
                                                <div class="q-bar-y-label">Total</div>
                                                <div class="q-bar-group">
                                                    <div class="q-bar-slot">
                                                        <div class="q-bar q-bar-human" style="width:${realPct}%; background:${HUMAN_COLOR};" title="Humans: ${realDisplay}"></div>
                                                        <span class="q-bar-count-inline human">${realDisplay}</span>
                                                    </div>
                                                    <div class="q-bar-slot">
                                                        <div class="q-bar q-bar-synthetic" style="width:${synPct}%; background:${SYNTHETIC_COLOR};" title="Synthetic: ${synDisplay}"></div>
                                                        <span class="q-bar-count-inline synthetic">${synDisplay}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    `;
                                }
                                
                                return `
                                    <tr>
                                        <td class="question-cell">
                                            <div class="question-number">${idx + 1}</div>
                                            <div class="question-text">${q.question_name || q.question_id}</div>
                                        </td>
                                        <td class="answer-options-cell">
                                            <div class="options-comparison-container">
                                                ${optionsHtml}
                                            </div>
                                        </td>
                                        <td class="type-cell">${q.type || 'Single-Choice'}</td>
                                        <td class="match-score-cell" style="color: ${qAccent}; font-weight: 600;">${matchPercent === '—' ? '—' : matchPercent + '%'}</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    } else {
        questionsTableHtml = `
            <div id="tab-content-questions" class="results-tab-content active">
                <div class="empty-state">
                    <p>No question-by-question comparison data available. This feature requires file uploads with structured question data.</p>
                </div>
            </div>
        `;
    }
    
    // Summary tab content
    const summaryHtml = `
        <div id="tab-content-summary" class="results-tab-content">
            <div class="summary-section">
                <h4>Statistical Tests</h4>
                <div class="test-results-grid">
                    ${data.tests ? data.tests.filter(t => !t.error).map(test => {
                        const m = test.match_score != null ? Number(test.match_score) : null;
                        const testAccent = m != null && !Number.isNaN(m) ? matchScoreAccentColor(m) : '#6b7280';
                        const matchPct = m != null && !Number.isNaN(m) ? (m * 100).toFixed(1) : '—';
                        return `
                            <div class="test-result-card" style="border-left-color: ${testAccent}">
                                <div class="test-result-name">${formatTestName(test.test)}</div>
                                <div class="test-result-status" style="color: ${testAccent}">${matchPct === '—' ? '—' : matchPct + '%'}</div>
                            </div>
                        `;
                    }).join('') : '<p>No test results available</p>'}
                </div>
            </div>
        </div>
    `;
    
        targetDiv.innerHTML = `
            ${modelDetailsHtml}
            ${tabsHtml}
            ${questionsTableHtml}
            ${questionComparisons.length === 0 ? summaryHtml : ''}
            ${methodologyHtml}
            <div class="results-actions">
                ${currentUserRole ? `<button onclick="showSection('validation')" class="btn-primary">Run New Validation</button>` : `<button onclick="showSection('reports')" class="btn-primary">← Dashboard</button>`}
                <button onclick="downloadReport('${surveyId || ''}', 'html')" class="btn-download">📄 Download HTML Report</button>
                <button onclick="downloadReport('${surveyId || ''}', 'json')" class="btn-download">📋 Download JSON</button>
            </div>
        `;
    } catch (error) {
        console.error('Error in displaySemilatticeStyleResults:', error);
        console.error('Data received:', data);
        console.error('SurveyId:', surveyId);
        targetDiv.innerHTML = `
            <div class="empty-results-state error-state-enhanced">
                <div class="error-icon-animated">
                    <div class="error-icon-circle-large">
                        <span class="error-icon-emoji-large">⚠️</span>
                    </div>
                    <div class="error-pulse-ring-large"></div>
                    <div class="error-pulse-ring-large"></div>
                </div>
                <h3 class="error-title-enhanced">Error Displaying Results</h3>
                <p class="error-message-enhanced">There was an error rendering the results. Check the console for details.</p>
                <div class="error-details-enhanced">
                    <code>${error.message}</code>
                </div>
                <button onclick="showSection('${currentUserRole ? 'validation' : 'reports'}')" class="btn-primary error-action-button">${currentUserRole ? 'Go to Validation Runs' : 'Go to Dashboard'}</button>
            </div>
        `;
    }
}

// Switch between result tabs
function switchResultsTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.results-tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.results-tab').forEach(btn => btn.classList.remove('active'));
    
    // Show selected tab
    const tabContent = document.getElementById(`tab-content-${tabName}`);
    const tabButton = document.getElementById(`tab-${tabName}`);
    if (tabContent) tabContent.classList.add('active');
    if (tabButton) tabButton.classList.add('active');
}

// Copy to clipboard
function copyToClipboard(text) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
        // Show feedback
        const btn = event?.target || document.querySelector('.copy-btn');
        if (btn) {
            const original = btn.textContent;
            btn.textContent = '✓';
            setTimeout(() => {
                btn.textContent = original;
            }, 2000);
        }
    }).catch(err => {
        console.error('Failed to copy:', err);
        showNotification('Failed to copy to clipboard. Please try again.', 'error');
    });
}

// Tab switching
function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`tab-content-${tab}`).classList.add('active');
    document.getElementById(`tab-${tab}`).classList.add('active');
}

// Toggle sidebar collapse
function toggleSidebar() {
    const appShell = document.querySelector('.app-shell');
    if (!appShell) return;
    const isMobile = window.matchMedia('(max-width: 768px)').matches;
    if (isMobile) {
        appShell.classList.toggle('mobile-menu-open');
        const overlay = document.getElementById('sidebar-overlay');
        if (overlay) overlay.setAttribute('aria-hidden', appShell.classList.contains('mobile-menu-open') ? 'false' : 'true');
        document.body.style.overflow = appShell.classList.contains('mobile-menu-open') ? 'hidden' : '';
    } else {
        appShell.classList.toggle('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', appShell.classList.contains('sidebar-collapsed'));
    }
}

function closeMobileMenu() {
    const appShell = document.querySelector('.app-shell');
    if (appShell && appShell.classList.contains('mobile-menu-open')) {
        appShell.classList.remove('mobile-menu-open');
        const overlay = document.getElementById('sidebar-overlay');
        if (overlay) overlay.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }
}


// Define compareFiles function
async function compareFiles() {
    const syntheticFile = document.getElementById('file-synthetic')?.files[0];
    const realFile = document.getElementById('file-real')?.files[0];
    const surveyIdInput = document.getElementById('file-survey-id');
    const surveyId = surveyIdInput ? surveyIdInput.value.trim() : null;
    const method = document.getElementById('extraction-method')?.value || 'totals';
    
    if (!syntheticFile || !realFile) {
        showNotification('Please select both files (Synthetic and Real) to compare.', 'warning');
        return;
    }
    
    // Validate file types
    const validExtensions = ['.xlsx', '.xls', '.csv'];
    const synExt = syntheticFile.name.substring(syntheticFile.name.lastIndexOf('.')).toLowerCase();
    const realExt = realFile.name.substring(realFile.name.lastIndexOf('.')).toLowerCase();
    
    if (!validExtensions.includes(synExt) || !validExtensions.includes(realExt)) {
        showNotification('Invalid file type. Please upload Excel (.xlsx, .xls) or CSV (.csv) files only.', 'error');
        return;
    }
    if ((syntheticFile.size || 0) > (typeof MAX_UPLOAD_FILE_BYTES !== 'undefined' ? MAX_UPLOAD_FILE_BYTES : 900 * 1024) ||
        (realFile.size || 0) > (typeof MAX_UPLOAD_FILE_BYTES !== 'undefined' ? MAX_UPLOAD_FILE_BYTES : 900 * 1024)) {
        showNotification('One or both files are too large (max ~900 KB each) to avoid upload limits. Use smaller files.', 'error');
        return;
    }
    
    // Show loading state - update button text
    const compareButton = document.querySelector('button[onclick*="compareFiles"]');
    const originalButtonText = compareButton?.textContent || 'Compare Files';
    if (compareButton) {
        compareButton.disabled = true;
        compareButton.textContent = 'Processing...';
    }
    
    try {
        omiPlay('task', 'Comparing files now. I will guide you to the results.');
        const formData = new FormData();
        formData.append('synthetic_file', syntheticFile);
        formData.append('real_file', realFile);
        formData.append('method', method);
        if (surveyId) {
            formData.append('survey_id', surveyId);
        }
        
        const res = await fetch('/api/validation/compare-files', {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            const errorText = await res.text();
            let errorDetail = 'File comparison failed';
            try {
                const errorJson = JSON.parse(errorText);
                errorDetail = errorJson.detail || errorDetail;
            } catch (e) {
                errorDetail = errorText || errorDetail;
            }
            throw new Error(errorDetail);
        }
        
        const data = await res.json();

        // Store results and navigate to results page
        storeResultsAndNavigate(data, data.survey_id);
        showNotification('Files compared successfully! Viewing results...', 'success', 3000);
        omiPlay('celebrate', 'Comparison complete! Opening results.');

        invalidateSurveysCache();
        await Promise.all([loadDashboard(), loadSurveys(), loadReports(currentReportsPage || 1)]);

    } catch (e) {
        console.error('Error in compareFiles:', e);
        console.error('Error stack:', e.stack);
        omiPlay('caution', 'Comparison failed. Check inputs and try again.');
        showErrorDisplay(
            'File Comparison Failed',
            'Unable to compare files. Please check file formats and try again.',
            e.message,
            '<button onclick="showSection(\'validation\')" class="btn-primary">Try Again</button>'
        );
    } finally {
        // Restore button
        if (compareButton) {
            compareButton.disabled = false;
            compareButton.textContent = originalButtonText;
        }
    }
}

// Ensure compareFiles is globally accessible (for onclick handlers)
if (typeof window !== 'undefined') {
    window.compareFiles = compareFiles;
}

// Sophisticated Notification System with Animations
function showNotification(message, type = 'error', duration = 5000) {
    if (type === 'success') omiPlay('celebrate', message);
    else if (type === 'warning' || type === 'error') omiPlay('caution', message);
    else omiPlay('idle', message);
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.notification-toast');
    existingNotifications.forEach(n => n.remove());
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification-toast notification-${type}`;
    
    // Set icons and colors based on type
    const config = {
        error: {
            icon: '❌',
            color: '#ef4444',
            title: 'Error',
            bg: 'rgba(239, 68, 68, 0.1)',
            border: '#ef4444'
        },
        warning: {
            icon: '⚠️',
            color: '#f59e0b',
            title: 'Warning',
            bg: 'rgba(245, 158, 11, 0.1)',
            border: '#f59e0b'
        },
        success: {
            icon: '✅',
            color: '#10b981',
            title: 'Success',
            bg: 'rgba(16, 185, 129, 0.1)',
            border: '#10b981'
        },
        info: {
            icon: 'ℹ️',
            color: '#00D4EC',
            title: 'Info',
            bg: 'rgba(0, 212, 236, 0.1)',
            border: '#00D4EC'
        }
    };
    
    const cfg = config[type] || config.error;
    
    notification.innerHTML = `
        <div class="notification-content">
            <div class="notification-icon" style="background: ${cfg.bg}; border-color: ${cfg.border};">
                <span class="notification-icon-emoji">${cfg.icon}</span>
            </div>
            <div class="notification-body">
                <div class="notification-title" style="color: ${cfg.color};">${cfg.title}</div>
                <div class="notification-message">${message}</div>
            </div>
            <button class="notification-close" onclick="this.closest('.notification-toast').remove()">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M15 5L5 15M5 5l10 10"/>
                </svg>
            </button>
        </div>
        <div class="notification-progress" style="background: ${cfg.color};"></div>
    `;
    
    // Add to page
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.classList.add('notification-show');
    }, 10);
    
    // Auto remove after duration
    const progressBar = notification.querySelector('.notification-progress');
    progressBar.style.animation = `notificationProgress ${duration}ms linear`;
    
    setTimeout(() => {
        notification.classList.remove('notification-show');
        setTimeout(() => notification.remove(), 300);
    }, duration);
    
    // Add click to dismiss
    notification.addEventListener('click', (e) => {
        if (!e.target.closest('.notification-close')) {
            notification.classList.remove('notification-show');
            setTimeout(() => notification.remove(), 300);
        }
    });
}

// Enhanced Error Display Component
function showErrorDisplay(title, message, details = null, actionButton = null) {
    const errorContainer = document.getElementById('error-display-container') || createErrorContainer();
    
    const errorId = 'error-' + Date.now();
    const errorHtml = `
        <div class="error-display-card" id="${errorId}">
            <div class="error-display-icon">
                <div class="error-icon-circle">
                    <span class="error-icon-emoji">⚠️</span>
                </div>
                <div class="error-pulse-ring"></div>
                <div class="error-pulse-ring"></div>
            </div>
            <div class="error-display-content">
                <h3 class="error-display-title">${title}</h3>
                <p class="error-display-message">${message}</p>
                ${details ? `<div class="error-display-details"><code>${details}</code></div>` : ''}
                ${actionButton ? `<div class="error-display-actions">${actionButton}</div>` : ''}
            </div>
            <button class="error-display-close" onclick="document.getElementById('${errorId}').remove()">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
            </button>
        </div>
    `;
    
    errorContainer.insertAdjacentHTML('beforeend', errorHtml);
    
    const errorCard = document.getElementById(errorId);
    setTimeout(() => errorCard.classList.add('error-display-visible'), 10);
    
    return errorId;
}

function createErrorContainer() {
    const container = document.createElement('div');
    container.id = 'error-display-container';
    container.className = 'error-display-container';
    document.body.appendChild(container);
    return container;
}


// Update displayValidationResults to accept optional resultsDiv parameter
function displayValidationResults(data, surveyId, resultsDiv = null) {
    const targetDiv = resultsDiv || document.getElementById('validation-results') || document.getElementById('validation-results-manual');
    if (!targetDiv) return;
    
    const acc01 = normalizeAccuracy01(data.overall_accuracy);
    const accuracyPct = (acc01 != null ? acc01 : 0) * 100;
    const accuracy = accuracyPct.toFixed(1);

    function qualityFromAccuracy01(a) {
        const p = (a != null ? a : 0) * 100;
        if (p >= 85) {
            return {
                icon: '✅',
                title: 'Strong match',
                description: 'Your synthetic data closely matches the real data. Ready for use!',
                color: '#10b981',
            };
        }
        if (p >= 75) {
            return {
                icon: '⚠️',
                title: 'Good match',
                description: 'Your synthetic data is similar to real data with some minor differences.',
                color: '#f59e0b',
            };
        }
        if (p >= 50) {
            return {
                icon: '❌',
                title: 'Needs improvement',
                description: 'Significant differences detected. Consider refining your synthetic data generation.',
                color: '#ef4444',
            };
        }
        return {
            icon: '🔴',
            title: 'Weak match',
            description: 'Poor match. Review detailed results and adjust your data generation strategy.',
            color: '#7c3aed',
        };
    }

    const qualityInfo = qualityFromAccuracy01(acc01);
    
    // Build simplified test list (no complex categorization)
    let testsHtml = '';
    if (data.tests && data.tests.length > 0) {
        const validTests = data.tests.filter(t => !t.error).sort((a, b) => {
            const ma = a.match_score != null ? Number(a.match_score) : -1;
            const mb = b.match_score != null ? Number(b.match_score) : -1;
            return mb - ma;
        });
        
        validTests.forEach(test => {
            const m = test.match_score != null ? Number(test.match_score) : null;
            const testAccent = m != null && !Number.isNaN(m) ? matchScoreAccentColor(m) : '#6b7280';
            const matchLabel = m != null && !Number.isNaN(m) ? `${(m * 100).toFixed(1)}% match` : '—';
            const metrics = formatTestMetrics(test);
            
            testsHtml += `
                <div class="test-item-simple">
                    <div class="test-item-header-simple">
                        <div class="test-name-simple">
                            ${formatTestName(test.test)}
                        </div>
                        <div class="test-status-simple" style="color: ${testAccent}">
                            ${matchLabel}
                        </div>
                    </div>
                    ${metrics}
                </div>
            `;
        });
    }
    
    function getSimpleMetricLabel(key) {
        const labels = {
            'match_score': 'Match Quality',
            'p_value': 'Confidence Level',
            'distance': 'Difference',
            'normalized_distance': 'Difference (Normalized)',
            'average_correlation': 'Similarity Score',
            'normalized_mae': 'Average Error',
            'normalized_rmse': 'Error Range',
            'pearson_r': 'Linear Relationship',
            'spearman_r': 'Rank Relationship',
            'mean_difference': 'Average Difference',
            'std_difference': 'Variability Difference'
        };
        return labels[key.toLowerCase()] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    function formatValueForDisplay(value, key) {
        if (typeof value !== 'number') return value;
        
        // For percentages and scores (0-1 range)
        if (['match_score', 'p_value', 'average_correlation', 'pearson_r', 'spearman_r'].includes(key.toLowerCase())) {
            return `${(value * 100).toFixed(1)}%`;
        }
        
        // For normalized metrics (0-1 range)
        if (key.toLowerCase().includes('normalized')) {
            return `${(value * 100).toFixed(1)}%`;
        }
        
        // For small numbers, use percentage
        if (Math.abs(value) < 1 && Math.abs(value) > 0.01) {
            return `${(value * 100).toFixed(1)}%`;
        }
        
        // For very small numbers
        if (Math.abs(value) < 0.0001 && value !== 0) {
            return value.toExponential(2);
        }
        
        // Default: 4 decimal places
        return value.toFixed(4);
    }
    
    function formatTestMetrics(test) {
        // Only show the most important, user-friendly metric
        const keyMetrics = ['match_score', 'p_value', 'average_correlation', 'normalized_distance', 'normalized_mae'];
        let mainMetric = null;
        let mainValue = null;
        
        for (const key of keyMetrics) {
            if (test[key] !== undefined && test[key] !== null) {
                mainMetric = getSimpleMetricLabel(key);
                mainValue = formatValueForDisplay(test[key], key);
                break;
            }
        }
        
        if (!mainMetric) {
            // Fallback to first available metric
            for (const [key, value] of Object.entries(test)) {
                if (key !== 'test' && key !== 'tier' && key !== 'interpretation' && typeof value === 'number') {
                    mainMetric = getSimpleMetricLabel(key);
                    mainValue = formatValueForDisplay(value, key);
                    break;
                }
            }
        }
        
        if (mainMetric && mainValue) {
            return `
                <div class="simple-metric">
                    <div class="simple-metric-value">${mainValue}</div>
                    <div class="simple-metric-label">${mainMetric}</div>
                </div>
            `;
        }
        
        return '<div class="simple-metric"><div class="simple-metric-value">—</div></div>';
    }
    
    const progressPercent = Math.min(95, Math.max(12, Math.round(accuracyPct)));
    
    const successfulTests = data.tests ? data.tests.filter(t => !t.error).length : 0;
    const totalTests = data.tests ? data.tests.length : 0;

    let recBody = '';
    if (acc01 != null && acc01 >= 0.85) {
        recBody = '<p>Your synthetic data is excellent! It closely matches the patterns and characteristics of real data. You can confidently use this data for your analysis.</p>';
    } else if (acc01 != null && acc01 >= 0.75) {
        recBody = `<p>Your synthetic data is good but could be improved. The data is similar to real data, but there are some differences. Consider:</p>
                <ul>
                    <li>Reviewing the data generation process</li>
                    <li>Adjusting parameters to better match real patterns</li>
                    <li>Collecting more training data if possible</li>
                </ul>`;
    } else if (acc01 != null && acc01 >= 0.5) {
        recBody = `<p>Your synthetic data needs improvement. There are significant differences from real data. Consider:</p>
                <ul>
                    <li>Revisiting your data generation model</li>
                    <li>Checking for systematic biases</li>
                    <li>Using different generation techniques</li>
                    <li>Consulting with data science experts</li>
                </ul>`;
    } else {
        recBody = `<p>Your synthetic data needs significant improvement. Match quality is below 50%. Consider:</p>
                <ul>
                    <li>Revisiting your data generation model and parameters</li>
                    <li>Checking for systematic biases and data alignment</li>
                    <li>Using different generation techniques or more representative training data</li>
                    <li>Consulting with data science experts</li>
                </ul>`;
    }
    
    targetDiv.innerHTML = `
        <div class="results-header">
            <h3>🎉 Validation Complete!</h3>
            <div class="download-buttons">
                <button onclick="downloadReport('${surveyId}', 'html')" class="btn-download">📄 Download Report</button>
            </div>
        </div>
        
        <!-- Main Result Card - Always show overall file accuracy -->
        <div class="main-result-card" style="border-color: ${qualityInfo.color}">
            <div class="main-result-icon" style="color: ${qualityInfo.color}">${qualityInfo.icon}</div>
            <div class="main-result-content">
                <h2 style="color: ${qualityInfo.color}">${qualityInfo.title}</h2>
                <p class="main-result-description">${qualityInfo.description}</p>
                <div class="accuracy-display">
                    <div class="accuracy-label">Overall File Match Score</div>
                    <div class="accuracy-value" style="color: ${qualityInfo.color}">${accuracy}%</div>
                    <div class="progress-bar-container">
                        <div class="progress-bar" style="width: ${progressPercent}%; background: ${qualityInfo.color}"></div>
                    </div>
                </div>
            </div>
        </div>
        
        ${buildStatisticalTestsGuideHtml()}
        
        ${(data.question_comparisons && data.question_comparisons.length === 0) ? `
        <!-- Quick Stats (only show if no question comparisons) -->
        <div class="quick-stats">
            <div class="quick-stat">
                <div class="quick-stat-icon">✅</div>
                <div class="quick-stat-content">
                    <div class="quick-stat-value">${successfulTests}/${totalTests}</div>
                    <div class="quick-stat-label">Tests Passed</div>
                </div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-icon">📊</div>
                <div class="quick-stat-content">
                    <div class="quick-stat-value">${data.synthetic_size || 0}</div>
                    <div class="quick-stat-label">Synthetic Responses</div>
                </div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-icon">📋</div>
                <div class="quick-stat-content">
                    <div class="quick-stat-value">${data.real_size || 0}</div>
                    <div class="quick-stat-label">Real Responses</div>
                </div>
            </div>
        </div>
        
        <!-- Test Results (Simplified) -->
        <div class="test-results-simple">
            <h4>📈 Quality Checks</h4>
            <p class="section-description">We ran ${totalTests} different checks to compare your synthetic data with real data. Each check looks at a different aspect of how well they match.</p>
            ${testsHtml || '<p class="empty-state">No test results available</p>'}
        </div>
        ` : ''}
        
        ${data.file_info ? `
        <!-- File Information -->
        <div class="file-info-box">
            <h4>📁 Files Compared</h4>
            <div class="file-info-grid">
                <div class="file-info-item">
                    <div class="file-info-label">File A (Synthetic)</div>
                    <div class="file-info-value">${data.file_info.synthetic_file}</div>
                    <div class="file-info-detail">${data.file_info.synthetic_responses_count} values</div>
                </div>
                <div class="file-info-item">
                    <div class="file-info-label">File B (Real)</div>
                    <div class="file-info-value">${data.file_info.real_file}</div>
                    <div class="file-info-detail">${data.file_info.real_responses_count} values</div>
                </div>
                <div class="file-info-item">
                    <div class="file-info-label">Extraction Method</div>
                    <div class="file-info-value">${data.file_info.extraction_method === 'totals' ? 'Totals (sum per column)' : 'All responses'}</div>
                </div>
            </div>
        </div>
        ` : ''}
        
        <!-- Recommendations -->
        <div class="recommendations-box" style="border-left-color: ${qualityInfo.color}">
            <h4>💡 What This Means</h4>
            ${recBody}
        </div>
    `;
}

