function showSection(id) {
    // Check if user is authenticated before showing protected sections
    // Home and Industry Surveys are accessible without login
    if (currentUserRole === null && id !== 'industry-surveys' && id !== 'home') {
        showNotification('Please log in to access this page', 'warning');
        id = 'home'; // Redirect to Home
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

    if(id==='surveys') loadSurveys();
    else if(id==='dashboard' || id==='reports') {
        // Combined Dashboard & Reports - load both
        loadDashboard();
        loadReports(currentReportsPage);
    }
    else if(id==='industry-surveys') {
        loadIndustrySurveys();
    }
    else if(id==='results') {
        loadResultsPage();
    }
    else if(id==='market-research') {
        // Optional: reset output panel when entering
    }
    // Home section doesn't need any loading function
}

async function loadSurveys() {
    try {
        const r = await fetch('/api/surveys/');
        const surveys = await r.json();
        document.getElementById('surveys-list').innerHTML = surveys.map(s =>
            `<div class="survey-card">
                <h3>${s.title}</h3>
                <p>Accuracy: ${s.accuracy_score ?? 'N/A'}</p>
                <small>ID: ${s.id}</small>
            </div>`
        ).join('');
    } catch(e) { console.error(e); }
}

async function loadDashboard() {
    try {
        const r = await fetch('/api/surveys/');
        const surveys = await r.json();
        const totalSurveys = surveys.length;
        document.getElementById('total-surveys').textContent = totalSurveys;
        
        const validatedSurveys = surveys.filter(s => s.accuracy_score !== null && s.accuracy_score !== undefined);
        document.getElementById('validated-surveys').textContent = validatedSurveys.length;
        
        // Calculate average accuracy
        if (validatedSurveys.length > 0) {
            const totalAccuracy = validatedSurveys.reduce((sum, s) => {
                const acc = parseFloat(s.accuracy_score) || 0;
                return sum + acc;
            }, 0);
            const avgAccuracy = (totalAccuracy / validatedSurveys.length) * 100;
            document.getElementById('avg-accuracy').textContent = avgAccuracy.toFixed(1) + '%';
        } else {
            document.getElementById('avg-accuracy').textContent = '0%';
        }
    } catch(e) { 
        console.error('Error loading dashboard:', e);
        document.getElementById('total-surveys').textContent = '0';
        document.getElementById('validated-surveys').textContent = '0';
        document.getElementById('avg-accuracy').textContent = '0%';
    }
}

function createNewSurvey() {
    const title = prompt('Survey title:');
    if(!title) return;
    fetch('/api/surveys/', {method:'POST', body: JSON.stringify({title}), 
           headers:{'Content-Type':'application/json'}}).then(() => loadSurveys());
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
        
        // refresh dashboard stats
        await loadDashboard();
        await loadSurveys();
    } catch (e) {
        console.error(e);
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
    console.log('loadIndustrySurveys() called');
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
            tier: 'TIER_1',
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
            tier: 'TIER_1',
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
            tier: 'TIER_2',
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
            tier: 'TIER_1',
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
            tier: 'TIER_2',
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
            tier: 'TIER_2',
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
        const tierColors = {
            'TIER_1': '#10b981',
            'TIER_2': '#f59e0b',
            'TIER_3': '#ef4444',
            'TIER_4': '#7c3aed'
        };
        const tierColor = tierColors[survey.tier] || '#6b7280';
        
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
                    <span class="tier-badge" style="background: ${tierColor}">${survey.tier}</span>
                </div>
                <p class="industry-survey-description">${survey.description}</p>
                <div class="industry-survey-stats">
                    <div class="industry-stat">
                        <div class="industry-stat-label">Accuracy</div>
                        <div class="industry-stat-value" style="color: ${tierColor};">${survey.accuracy}%</div>
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
    } catch (err) {
        statusEl.textContent = err.message || 'Failed to load sample PDF';
        statusEl.className = 'market-research-status error';
        showNotification(err.message || 'Sample PDF not found. Place sample_market_research_report.pdf in project root.', 'warning');
    }
}

let lastMarketResearchData = null;

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
                if (data.ai_used === false && data.message) {
                    statusEl.innerHTML = '<strong>Placeholder only.</strong> ' + escapeHtml(data.message);
                    statusEl.className = 'market-research-status error';
                } else {
                    statusEl.textContent = 'Done.';
                    statusEl.className = 'market-research-status success';
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
            if (data.ai_used === false && data.message) {
                statusEl.innerHTML = '<strong>Placeholder only.</strong> ' + escapeHtml(data.message);
                statusEl.className = 'market-research-status error';
            } else {
                statusEl.textContent = 'Done.';
                statusEl.className = 'market-research-status success';
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
            if (data.ai_used === false && data.message) {
                statusEl.innerHTML = '<strong>Placeholder only.</strong> ' + escapeHtml(data.message);
                statusEl.className = 'market-research-status error';
            } else {
                statusEl.textContent = 'Done.';
                statusEl.className = 'market-research-status success';
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
        if (data.ai_used === false && data.message) {
            statusEl.innerHTML = '<strong>Placeholder only.</strong> ' + escapeHtml(data.message);
            statusEl.className = 'market-research-status error';
        } else {
            statusEl.textContent = 'Done.';
            statusEl.className = 'market-research-status success';
        }
    } catch (err) {
        statusEl.textContent = err.message || 'Request failed.';
        statusEl.className = 'market-research-status error';
        console.error('Market research reverse engineer error:', err);
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

// Pagination state
let currentReportsPage = 1;
const reportsPerPage = 4; // 2x2 grid = 4 items

async function loadReports(page = 1) {
    console.log('loadReports() called, page:', page);
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
        console.log('Fetching surveys from /api/surveys/');
        const r = await fetch('/api/surveys/');
        if (!r.ok) {
            throw new Error(`HTTP error! status: ${r.status}`);
        }
        const surveys = await r.json();
        console.log(`Received ${surveys.length} surveys`);
        
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
        
        console.log(`Found ${validatedSurveys.length} validated surveys out of ${surveys.length} total`);
        
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
        
        reportsList.innerHTML = paginatedSurveys.map(s => {
            const tier = s.confidence_tier || 'N/A';
            const accuracy = s.accuracy_score ? (s.accuracy_score * 100).toFixed(1) : 'N/A';
            const tierColors = {
                'TIER_1': '#10b981',
                'TIER_2': '#f59e0b',
                'TIER_3': '#ef4444',
                'TIER_4': '#7c3aed'
            };
            const tierColor = tierColors[tier] || '#6b7280';
            const validatedDate = s.validated_at ? new Date(s.validated_at).toLocaleDateString() : 'N/A';
            
            // Extract test accuracies from test_suite_report
            const report = s.test_suite_report || {};
            const tests = report.tests || [];
            const testSummary = report.test_summary || {};
            
            // Count tests by tier and calculate average accuracy
            const testAccuracies = tests
                .filter(t => t.match_score !== undefined && !t.error)
                .map(t => (t.match_score * 100).toFixed(1));
            
            const tier1Tests = tests.filter(t => t.tier === 'TIER_1' && !t.error).length;
            const tier2Tests = tests.filter(t => t.tier === 'TIER_2' && !t.error).length;
            const tier3Tests = tests.filter(t => t.tier === 'TIER_3' && !t.error).length;
            const tier4Tests = tests.filter(t => t.tier === 'TIER_4' && !t.error).length;
            const totalTests = tests.filter(t => !t.error).length;
            
            // Get file info for seed characteristics
            const fileInfo = s.synthetic_personas || {};
            const sourceFile = typeof fileInfo === 'object' && fileInfo.source_file ? fileInfo.source_file : 'N/A';
            const questionCount = s.test_suite_report?.question_comparisons?.length || fileInfo.question_data?.length || 0;
            
            // Get top 5 test results with accuracies
            const topTests = tests
                .filter(t => t.match_score !== undefined && !t.error)
                .slice(0, 5)
                .map(t => ({
                    name: formatTestName(t.test),
                    accuracy: (t.match_score * 100).toFixed(1),
                    tier: t.tier
                }));
            
            return `
                <div class="report-card-2x2">
                    <!-- Top Half: Seed Characteristics -->
                    <div class="report-card-seed-section">
                        <div class="seed-section-header">
                            <h3 class="seed-section-title">${s.title || 'Untitled Survey'}</h3>
                            <span class="tier-badge" style="background: ${tierColor}">${tier}</span>
                        </div>
                        <div class="seed-characteristics">
                            <div class="seed-char-item">
                                <span class="seed-char-label">Survey ID</span>
                                <span class="seed-char-value">${s.id.substring(0, 8)}...</span>
                            </div>
                            <div class="seed-char-item">
                                <span class="seed-char-label">Source File</span>
                                <span class="seed-char-value" title="${sourceFile}">${sourceFile.length > 25 ? sourceFile.substring(0, 25) + '...' : sourceFile}</span>
                            </div>
                            <div class="seed-char-item">
                                <span class="seed-char-label">Questions</span>
                                <span class="seed-char-value">${questionCount}</span>
                            </div>
                            <div class="seed-char-item">
                                <span class="seed-char-label">Validated</span>
                                <span class="seed-char-value">${validatedDate}</span>
                            </div>
                            <div class="seed-char-item">
                                <span class="seed-char-label">Status</span>
                                <span class="seed-char-value">${s.validation_status || 'VALIDATED'}</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Bottom Half: Synthetic People Results -->
                    <div class="report-card-synthetic-section">
                        <div class="synthetic-section-header">
                            <h4 class="synthetic-section-title">Synthetic People Results</h4>
                            <span class="overall-accuracy-badge" style="color: ${tierColor}; border-color: ${tierColor};">${accuracy}%</span>
                        </div>
                        <div class="synthetic-test-results">
                            <div class="test-results-grid">
                                ${topTests.map(test => {
                                    const testTierColor = tierColors[test.tier] || '#6b7280';
                                    return `
                                        <div class="test-result-item">
                                            <span class="test-result-name">${test.name}</span>
                                            <span class="test-result-accuracy" style="color: ${testTierColor};">${test.accuracy}%</span>
                                            <span class="test-result-badge" style="background: ${testTierColor}20; color: ${testTierColor};">${test.tier}</span>
                                        </div>
                                    `;
                                }).join('')}
                                ${totalTests > 5 ? `
                                <div class="test-result-item more-tests">
                                    <span class="test-result-name">+ ${totalTests - 5} more tests</span>
                                </div>
                                ` : ''}
                            </div>
                            <div class="test-summary-stats">
                                <div class="summary-stat">
                                    <span class="summary-label">Total Tests</span>
                                    <span class="summary-value">${totalTests}</span>
                                </div>
                                <div class="summary-stat">
                                    <span class="summary-label">Tier 1</span>
                                    <span class="summary-value" style="color: #10b981;">${tier1Tests}</span>
                                </div>
                                <div class="summary-stat">
                                    <span class="summary-label">Tier 2</span>
                                    <span class="summary-value" style="color: #f59e0b;">${tier2Tests}</span>
                                </div>
                                <div class="summary-stat">
                                    <span class="summary-label">Tier 3</span>
                                    <span class="summary-value" style="color: #ef4444;">${tier3Tests}</span>
                                </div>
                                <div class="summary-stat">
                                    <span class="summary-label">Tier 4</span>
                                    <span class="summary-value" style="color: #7c3aed;">${tier4Tests}</span>
                                </div>
                            </div>
                        </div>
                        <div class="report-card-actions-2x2">
                            <button onclick="viewReport('${s.id}')" class="btn-view-details">View Details</button>
                            <button onclick="downloadReport('${s.id}', 'html')" class="btn-download-small">📄</button>
                            <button onclick="downloadReport('${s.id}', 'json')" class="btn-download-small">📋</button>
                        </div>
                    </div>
                </div>
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
        
        console.log('Reports rendered successfully');
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
    
    console.log('Storing results:', { surveyId, hasData: !!resultsData });
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
        // Show empty state
        resultsContent.innerHTML = `
            <div class="empty-results-state">
                <div class="empty-icon">📊</div>
                <h3>No Results Yet</h3>
                <p>Run a validation from the Validation Runs page to see results here.</p>
                <button onclick="showSection('validation')" class="btn-primary">Go to Validation Runs</button>
            </div>
        `;
        return;
    }
    
    try {
        const parsed = JSON.parse(stored);
        const data = parsed.data || parsed;
        const surveyId = parsed.surveyId || parsed.survey_id || data.survey_id;
        
        console.log('Loading results for surveyId:', surveyId);
        console.log('Data structure:', Object.keys(data));
        
        // If we have surveyId, try to fetch full results with question comparisons
        if (surveyId) {
            try {
                const res = await fetch(`/api/validation/results/${surveyId}`);
                if (res.ok) {
                    const fullData = await res.json();
                    console.log('Fetched full results:', Object.keys(fullData));
                    displaySemilatticeStyleResults(fullData, surveyId, resultsContent);
                    return;
                } else {
                    const errorText = await res.text();
                    console.warn('Failed to fetch full results:', res.status, errorText);
                }
            } catch (e) {
                console.warn('Could not fetch full results, using stored data:', e);
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
            console.error('Semilattice style display failed, using fallback:', e);
            // Fallback to old display function
            displayValidationResults(displayData, surveyId, resultsContent);
        }
    } catch (e) {
        console.error('Error loading results:', e);
        console.error('Stored data:', stored);
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
                <button onclick="showSection('validation')" class="btn-primary error-action-button">Go to Validation Runs</button>
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
                updateNavigationForRole();
                updateUserDisplay();
                return data;
            } else {
                // Not authenticated - show only Industry Surveys
                currentUserRole = null;
                return { authenticated: false, role: null, is_super_user: false };
            }
        } else {
            // If auth endpoint fails, show only Industry Surveys
            currentUserRole = null;
            return { authenticated: false, role: null, is_super_user: false };
        }
    } catch (error) {
        console.error('Error fetching user privileges:', error);
        // On error, show only Industry Surveys
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
            currentUserRole = data.user.role === 'super' ? 'super' : 'user';
            updateNavigationForRole();
            updateUserDisplay();
            // Navigate to reports page after successful login
            showSection('reports');
            loadReports(1);
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

// Logout function
function logout() {
    authToken = null;
    localStorage.removeItem('authToken');
    currentUserRole = null; // No role after logout - show Home
    updateNavigationForRole();
    updateUserDisplay();
    // Navigate to Home page after logout
    showSection('home');
    showNotification('Logged out successfully', 'info');
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

// Update user display in sidebar
function updateUserDisplay() {
    const userInfoDisplay = document.getElementById('user-info-display');
    const loginFormDisplay = document.getElementById('login-form-display');
    const usernameDisplay = document.getElementById('username-display');
    const userRoleDisplay = document.getElementById('user-role-display');
    
    if (authToken && currentUserRole) {
        // Show user info, hide login form
        if (userInfoDisplay) userInfoDisplay.style.display = 'block';
        if (loginFormDisplay) loginFormDisplay.style.display = 'none';
        if (usernameDisplay) usernameDisplay.textContent = 'Loading...';
        if (userRoleDisplay) userRoleDisplay.textContent = currentUserRole === 'super' ? 'Super User' : 'Regular User';
        
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
}

function updateNavigationForRole() {
    const sections = ['home', 'dashboard', 'surveys', 'validation', 'results', 'industry-surveys', 'market-research', 'reports'];
    
    // Get navigation items
    const navHome = document.getElementById('nav-home');
    const navDashboardReports = document.getElementById('nav-dashboard-reports');
    const navSurveys = document.getElementById('nav-surveys');
    const navValidation = document.getElementById('nav-validation');
    const navResults = document.getElementById('nav-results');
    const navIndustrySurveys = document.getElementById('nav-industry-surveys');
    const navMarketResearch = document.getElementById('nav-market-research');
    
    if (currentUserRole === null) {
        // Not logged in: Show Home and Industry Surveys
        if (navHome) navHome.style.display = '';
        if (navDashboardReports) navDashboardReports.style.display = 'none';
        if (navSurveys) navSurveys.style.display = 'none';
        if (navValidation) navValidation.style.display = 'none';
        if (navResults) navResults.style.display = 'none';
        if (navIndustrySurveys) navIndustrySurveys.style.display = '';
        if (navMarketResearch) navMarketResearch.style.display = 'none';
    } else if (currentUserRole === 'user') {
        // User: Show Home, Dashboard+Reports (combined), Test Results, Industry Surveys, Market Research
        if (navHome) navHome.style.display = '';
        if (navDashboardReports) navDashboardReports.style.display = '';
        if (navSurveys) navSurveys.style.display = 'none';
        if (navValidation) navValidation.style.display = 'none';
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
    showSection('reports');
    loadDashboard();
    loadReports(1);
}

// Initialize navigation on page load
document.addEventListener('DOMContentLoaded', async () => {
    // First, set up basic UI state
    updateNavigationForRole();
    updateUserDisplay();
    
    try {
        // Fetch user privileges from backend
        const authData = await fetchUserPrivileges();
        
        // Load default page based on authentication status
        if (authData && authData.authenticated) {
            // If logged in, load reports as default
            showSection('reports');
            loadReports(1);
        } else {
            // If not logged in, show Home page
            showSection('home');
        }
    } catch (error) {
        console.error('Error during initialization:', error);
        // Fallback: show Home if anything fails
        showSection('home');
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
});

// Display results in Semilattice.ai style
function displaySemilatticeStyleResults(data, surveyId, targetDiv) {
    if (!targetDiv) {
        console.error('displaySemilatticeStyleResults: targetDiv is null');
        return;
    }
    
    try {
        // Handle different data structures
        const survey = data.survey || {};
        const fileInfo = data.file_info || {};
        let questionComparisons = data.question_comparisons || [];
        
        // Debug logging
        console.log('displaySemilatticeStyleResults - Data keys:', Object.keys(data));
        console.log('displaySemilatticeStyleResults - questionComparisons:', questionComparisons);
        console.log('displaySemilatticeStyleResults - questionComparisons type:', typeof questionComparisons);
        console.log('displaySemilatticeStyleResults - questionComparisons length:', Array.isArray(questionComparisons) ? questionComparisons.length : 'not an array');
        
        // Also check results.question_comparisons (nested structure)
        if (!questionComparisons || questionComparisons.length === 0) {
            const results = data.results || {};
            questionComparisons = results.question_comparisons || data.question_comparisons || [];
            console.log('Checking nested results.question_comparisons:', questionComparisons);
        }
        
        const tier = data.overall_tier || data.tier || 'N/A';
        const accuracyValue = data.overall_accuracy || data.accuracy || 0;
        const accuracy = (typeof accuracyValue === 'number' ? accuracyValue * 100 : parseFloat(accuracyValue) * 100 || 0).toFixed(1);
    
    const tierColors = {
        'TIER_1': '#10b981',
        'TIER_2': '#f59e0b',
        'TIER_3': '#ef4444',
        'TIER_4': '#7c3aed'
    };
    const tierColor = tierColors[tier] || '#6b7280';
    
    // Format dates
    const createdDate = survey.created_at ? new Date(survey.created_at).toLocaleString() : 'N/A';
    const validatedDate = survey.validated_at ? new Date(survey.validated_at).toLocaleString() : 'N/A';
    
    // Model details section (like Semilattice)
    const modelDetailsHtml = `
        <div class="model-details-card">
            <div class="model-details-header">
                <div>
                    <h3>${survey.title || 'Survey Comparison'}</h3>
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
                    <div class="model-detail-value" style="color: ${tierColor}">${accuracy}%</div>
                </div>
                <div class="model-detail-item">
                    <div class="model-detail-label">Status</div>
                    <div class="model-detail-value">
                        <span class="status-badge" style="background: ${tierColor}">${tier}</span>
                    </div>
                </div>
                ${fileInfo.synthetic_file ? `
                <div class="model-detail-item full-width">
                    <div class="model-detail-label">Synthetic File</div>
                    <div class="model-detail-value file-name" title="${fileInfo.synthetic_file}">${fileInfo.synthetic_file}</div>
                </div>
                <div class="model-detail-item full-width">
                    <div class="model-detail-label">Real File</div>
                    <div class="model-detail-value file-name" title="${fileInfo.real_file}">${fileInfo.real_file}</div>
                </div>
                ` : ''}
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
                <strong>Note:</strong> Each test provides a match score (0-100%) and tier classification (TIER_1: >85%, TIER_2: >75%, TIER_3: >50%, TIER_4: ≤50%). 
                The overall accuracy is calculated as the average of all test match scores.
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
    
    // Calculate tier stats
    const tier1Count = questionComparisons.length > 0 ? questionComparisons.filter(q => q.tier === 'TIER_1').length : (data.tests ? data.tests.filter(t => t.tier === 'TIER_1').length : 0);
    const tier2Count = questionComparisons.length > 0 ? questionComparisons.filter(q => q.tier === 'TIER_2').length : 0;
    const tier3Count = questionComparisons.length > 0 ? questionComparisons.filter(q => q.tier === 'TIER_3').length : 0;
    const tier4Count = questionComparisons.length > 0 ? questionComparisons.filter(q => q.tier === 'TIER_4').length : (data.tests ? data.tests.filter(t => t.tier === 'TIER_4').length : 0);
    const totalQuestions = questionComparisons.length > 0 ? questionComparisons.length : (fileInfo.synthetic_question_count || fileInfo.real_question_count || 0);
    const tier1Percent = totalQuestions > 0 ? (tier1Count / totalQuestions * 100).toFixed(0) : 0;
    const tier2Percent = totalQuestions > 0 ? (tier2Count / totalQuestions * 100).toFixed(0) : 0;
    const tier3Percent = totalQuestions > 0 ? (tier3Count / totalQuestions * 100).toFixed(0) : 0;
    const tier4Percent = totalQuestions > 0 ? (tier4Count / totalQuestions * 100).toFixed(0) : 0;
    
    // Get tier emoji and description
    const tierEmoji = tier === 'TIER_1' ? '🎯' : tier === 'TIER_2' ? '✨' : tier === 'TIER_3' ? '📊' : '⚠️';
    const tierDesc = tier === 'TIER_1' ? 'Excellent Match' : tier === 'TIER_2' ? 'Good Match' : tier === 'TIER_3' ? 'Needs Improvement' : 'Needs Significant Improvement';
    
    
    // Question-by-question table with option-level comparison and sparklines
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
                                <th>Sparkline</th>
                                <th>Status</th>
                                <th>Type</th>
                                <th>Match Score</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${questionComparisons.map((q, idx) => {
                                const qTierColor = tierColors[q.tier] || '#6b7280';
                                const matchPercent = (q.match_score * 100).toFixed(1);
                                const optionComparisons = q.option_comparisons || [];
                                
                                // Build option-level comparison display
                                let optionsHtml = '';
                                if (optionComparisons.length > 0) {
                                    optionsHtml = optionComparisons.map(opt => {
                                        const synCount = opt.synthetic_count || 0;
                                        const realCount = opt.real_count || 0;
                                        const maxCount = Math.max(synCount, realCount, 1);
                                        const synPercent = (synCount / maxCount) * 100;
                                        const realPercent = (realCount / maxCount) * 100;
                                        
                                        return `
                                            <div class="option-comparison-item">
                                                <div class="option-label">${opt.option}</div>
                                                <div class="option-bars">
                                                    <div class="option-bar synthetic" style="width: ${synPercent}%; background: ${qTierColor}; opacity: 0.7;" title="Synthetic: ${synCount}"></div>
                                                    <div class="option-bar real" style="width: ${realPercent}%; background: ${qTierColor};" title="Real: ${realCount}"></div>
                                                </div>
                                                <div class="option-values">
                                                    <span class="option-value-syn">S: ${synCount.toFixed(0)}</span>
                                                    <span class="option-value-real">R: ${realCount.toFixed(0)}</span>
                                                </div>
                                            </div>
                                        `;
                                    }).join('');
                                } else {
                                    // Fallback to totals if no option data
                                    const synTotal = q.synthetic_total || 0;
                                    const realTotal = q.real_total || 0;
                                    optionsHtml = `
                                        <div class="option-comparison-item">
                                            <div class="option-label">Total</div>
                                            <div class="option-bars">
                                                <div class="option-bar synthetic" style="width: 50%; background: ${qTierColor}; opacity: 0.7;" title="Synthetic: ${synTotal}"></div>
                                                <div class="option-bar real" style="width: 50%; background: ${qTierColor};" title="Real: ${realTotal}"></div>
                                            </div>
                                            <div class="option-values">
                                                <span class="option-value-syn">S: ${synTotal.toFixed(0)}</span>
                                                <span class="option-value-real">R: ${realTotal.toFixed(0)}</span>
                                            </div>
                                        </div>
                                    `;
                                }
                                
                                // Generate sparkline data
                                const sparklineData = optionComparisons.length > 0 
                                    ? optionComparisons.map(opt => ({
                                        syn: opt.synthetic_count || 0,
                                        real: opt.real_count || 0
                                    }))
                                    : [{ syn: q.synthetic_total || 0, real: q.real_total || 0 }];
                                
                                const sparklineId = `sparkline-${idx}`;
                                const sparklineSvg = generateSparkline(sparklineData, sparklineId, qTierColor);
                                
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
                                        <td class="sparkline-cell">
                                            ${sparklineSvg}
                                        </td>
                                        <td class="status-cell">
                                            <span class="status-badge-small" style="background: ${qTierColor}">${q.status || 'Compared'}</span>
                                        </td>
                                        <td class="type-cell">${q.type || 'Single-Choice'}</td>
                                        <td class="match-score-cell" style="color: ${qTierColor}">${matchPercent}%</td>
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
                    ${data.tests ? data.tests.map(test => {
                        const testTier = test.tier || 'N/A';
                        const testColor = tierColors[testTier] || '#6b7280';
                        return `
                            <div class="test-result-card" style="border-left-color: ${testColor}">
                                <div class="test-result-name">${formatTestName(test.test)}</div>
                                <div class="test-result-status" style="color: ${testColor}">${testTier}</div>
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
            ${methodologyHtml}
            ${questionsTableHtml}
            ${questionComparisons.length === 0 ? summaryHtml : ''}
            <div class="results-actions">
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
                <button onclick="showSection('validation')" class="btn-primary error-action-button">Go to Validation Runs</button>
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
    if (appShell) {
        appShell.classList.toggle('sidebar-collapsed');
        // Save state to localStorage
        localStorage.setItem('sidebarCollapsed', appShell.classList.contains('sidebar-collapsed'));
    }
}


// Define compareFiles function
async function compareFiles() {
    console.log('compareFiles() called');
    
    const syntheticFile = document.getElementById('file-synthetic')?.files[0];
    const realFile = document.getElementById('file-real')?.files[0];
    const surveyIdInput = document.getElementById('file-survey-id');
    const surveyId = surveyIdInput ? surveyIdInput.value.trim() : null;
    const method = document.getElementById('extraction-method')?.value || 'totals';
    
    console.log('Files selected:', {
        synthetic: syntheticFile?.name,
        real: realFile?.name,
        surveyId: surveyId || 'none',
        method: method
    });
    
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
        const formData = new FormData();
        formData.append('synthetic_file', syntheticFile);
        formData.append('real_file', realFile);
        formData.append('method', method);
        if (surveyId) {
            formData.append('survey_id', surveyId);
        }
        
        console.log('Sending request to /api/validation/compare-files');
        const res = await fetch('/api/validation/compare-files', {
            method: 'POST',
            body: formData
        });
        
        console.log('Response status:', res.status);
        
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
        console.log('Comparison successful, data received:', Object.keys(data));
        
        // Store results and navigate to results page
        storeResultsAndNavigate(data, data.survey_id);
        showNotification('Files compared successfully! Viewing results...', 'success', 3000);
        
        // Refresh dashboard and surveys
        await loadDashboard();
        await loadSurveys();
        await loadReports(); // Refresh reports list
        
    } catch (e) {
        console.error('Error in compareFiles:', e);
        console.error('Error stack:', e.stack);
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
    
    const tier = data.overall_tier || 'N/A';
    const accuracy = (data.overall_accuracy * 100).toFixed(1);
    
    const tierColors = {
        'TIER_1': '#10b981',
        'TIER_2': '#f59e0b',
        'TIER_3': '#ef4444',
        'TIER_4': '#7c3aed'
    };
    const tierColor = tierColors[tier] || '#6b7280';
    
    // Build simplified test list (no complex categorization)
    let testsHtml = '';
    if (data.tests && data.tests.length > 0) {
        // Filter out error tests and sort by tier (best first)
        const validTests = data.tests.filter(t => !t.error && t.tier).sort((a, b) => {
            const tierOrder = { 'TIER_1': 1, 'TIER_2': 2, 'TIER_3': 3, 'TIER_4': 4 };
            return (tierOrder[a.tier] || 99) - (tierOrder[b.tier] || 99);
        });
        
        validTests.forEach(test => {
            const testTier = test.tier || 'N/A';
            const testTierColor = tierColors[testTier] || '#6b7280';
            const metrics = formatTestMetrics(test);
            
            const tierEmoji = testTier === 'TIER_1' ? '✅' : testTier === 'TIER_2' ? '⚠️' : testTier === 'TIER_3' ? '❌' : '🔴';
            const tierText = testTier === 'TIER_1' ? 'Excellent' : testTier === 'TIER_2' ? 'Good' : testTier === 'TIER_3' ? 'Needs Work' : 'Poor Match';
            
            testsHtml += `
                <div class="test-item-simple">
                    <div class="test-item-header-simple">
                        <div class="test-name-simple">
                            ${formatTestName(test.test)}
                        </div>
                        <div class="test-status-simple" style="color: ${testTierColor}">
                            ${tierEmoji} ${tierText}
                        </div>
                    </div>
                    ${metrics}
                </div>
            `;
        });
    }
    
    function getTierDescription(tier) {
        const descriptions = {
            'TIER_1': { 
                icon: '✅', 
                title: 'Excellent Match', 
                description: 'Your synthetic data closely matches the real data. Ready for use!',
                color: '#10b981'
            },
            'TIER_2': { 
                icon: '⚠️', 
                title: 'Good Match', 
                description: 'Your synthetic data is similar to real data with some minor differences.',
                color: '#f59e0b'
            },
            'TIER_3': { 
                icon: '❌', 
                title: 'Needs Improvement', 
                description: 'Significant differences detected. Consider refining your synthetic data generation.',
                color: '#ef4444'
            },
            'TIER_4': { 
                icon: '🔴', 
                title: 'Needs Significant Improvement', 
                description: 'Poor match. Review detailed results and adjust your data generation strategy.',
                color: '#7c3aed'
            }
        };
        return descriptions[tier] || { icon: '❓', title: 'Unknown', description: '', color: '#6b7280' };
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
    
    const tierInfo = getTierDescription(tier);
    const progressPercent = tier === 'TIER_1' ? 95 : tier === 'TIER_2' ? 80 : tier === 'TIER_3' ? 60 : 30;
    
    // Count successful tests
    const successfulTests = data.tests ? data.tests.filter(t => t.tier && !t.error).length : 0;
    const totalTests = data.tests ? data.tests.length : 0;
    
    targetDiv.innerHTML = `
        <div class="results-header">
            <h3>🎉 Validation Complete!</h3>
            <div class="download-buttons">
                <button onclick="downloadReport('${surveyId}', 'html')" class="btn-download">📄 Download Report</button>
            </div>
        </div>
        
        <!-- Main Result Card - Always show overall file accuracy -->
        <div class="main-result-card" style="border-color: ${tierInfo.color}">
            <div class="main-result-icon" style="color: ${tierInfo.color}">${tierInfo.icon}</div>
            <div class="main-result-content">
                <h2 style="color: ${tierInfo.color}">${tierInfo.title}</h2>
                <p class="main-result-description">${tierInfo.description}</p>
                <div class="accuracy-display">
                    <div class="accuracy-label">Overall File Match Score</div>
                    <div class="accuracy-value" style="color: ${tierInfo.color}">${accuracy}%</div>
                    <div class="progress-bar-container">
                        <div class="progress-bar" style="width: ${progressPercent}%; background: ${tierInfo.color}"></div>
                    </div>
                </div>
            </div>
        </div>
        
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
        <div class="recommendations-box" style="border-left-color: ${tierInfo.color}">
            <h4>💡 What This Means</h4>
            ${tier === 'TIER_1' ? `
                <p>Your synthetic data is excellent! It closely matches the patterns and characteristics of real data. You can confidently use this data for your analysis.</p>
            ` : tier === 'TIER_2' ? `
                <p>Your synthetic data is good but could be improved. The data is similar to real data, but there are some differences. Consider:</p>
                <ul>
                    <li>Reviewing the data generation process</li>
                    <li>Adjusting parameters to better match real patterns</li>
                    <li>Collecting more training data if possible</li>
                </ul>
            ` : tier === 'TIER_3' ? `
                <p>Your synthetic data needs improvement. There are significant differences from real data. Consider:</p>
                <ul>
                    <li>Revisiting your data generation model</li>
                    <li>Checking for systematic biases</li>
                    <li>Using different generation techniques</li>
                    <li>Consulting with data science experts</li>
                </ul>
            ` : `
                <p>Your synthetic data needs significant improvement. Match quality is below 50%. Consider:</p>
                <ul>
                    <li>Revisiting your data generation model and parameters</li>
                    <li>Checking for systematic biases and data alignment</li>
                    <li>Using different generation techniques or more representative training data</li>
                    <li>Consulting with data science experts</li>
                </ul>
            `}
        </div>
    `;
}

