/**
 * WikiArt Preference Study - Frontend Application
 */

class ArtPreferenceStudy {
    constructor() {
        this.sessionId = null;
        this.currentPair = null;
        this.pendingPairPromise = null; // Pair fetch running during mid-study survey
        this.displayTimestamp = null;
        this.phase = 'welcome';
        this.practiceCount = 0;
        this.mainCount = 0;
        this.nPractice = 3;
        this.nMain = 10;
        this.surveyInterval = 5; // Show survey every N main comparisons (loaded from server)
        this.recommendations = [];
        this.selectedRecommendations = []; // Support multi-select
        this.recommendationType = null; // 'auto' or 'manual'
        this.isProcessing = false; // Prevent double-clicks
        this.practiceColorIndex = 0; // Track which color pair to show

        // Ranking state
        this.rankingStartTime = null;
        this.rankingMovements = [];
        this.currentRanking = {}; // position -> image_id mapping

        // Utility visualization state
        this.utilityVizData = null;

        // Timing tracking for pair loading performance
        this.pairLoadingTimes = []; // Array to store loading times in ms
        this.selectionTimestamp = null; // When user made selection

        // Color pairs for practice trials (left, right gradients)
        this.practiceColors = [
            { left: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', right: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' },
            { left: 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)', right: 'linear-gradient(135deg, #fc4a1a 0%, #f7b733 100%)' },
            { left: 'linear-gradient(135deg, #4568dc 0%, #b06ab3 100%)', right: 'linear-gradient(135deg, #ee0979 0%, #ff6a00 100%)' },
        ];

        // Recommendation config (loaded from server)
        this.recommendationConfig = {
            manual_show_n: 3,
            manual_select_n: 1
        };

        // Propensity to Trust items
        this.trustItems = [
            { id: 'trust1', text: 'I usually trust machines until there is a reason not to.' },
            { id: 'trust2', text: 'For the most part, I distrust machines.', reverse: true },
            { id: 'trust3', text: 'In general, I would rely on a machine to assist me.' },
            { id: 'trust4', text: 'My tendency to trust machines is high.' },
            { id: 'trust5', text: 'It is easy for me to trust machines to do their job.' },
            { id: 'trust6', text: 'I am likely to trust a machine even when I have little knowledge about it.' }
        ];

        // ATI items
        this.atiItems = [
            { id: 'ati1', text: 'I like to occupy myself in greater detail with technical systems.' },
            { id: 'ati2', text: 'I like testing the functions of new technical systems.' },
            { id: 'ati3', text: 'I predominantly deal with technical systems because I have to.', reverse: true },
            { id: 'ati4', text: 'When I have a new technical system in front of me, I try it out intensively.' },
            { id: 'ati5', text: 'I enjoy spending time becoming acquainted with a new technical system.' },
            { id: 'ati6', text: 'It is enough for me that a technical system works; I don\'t care how or why.', reverse: true },
            { id: 'ati7', text: 'I try to understand how a technical system exactly works.' },
            { id: 'ati8', text: 'It is enough for me to know the basic functions of a technical system.', reverse: true },
            { id: 'ati9', text: 'I try to make full use of the capabilities of a technical system.' }
        ];

        this.init();
    }

    init() {
        this.bindEvents();
        this.setupKeyboardShortcuts();
        this.generateParticipantId(); // Auto-generate participant ID
    }

    generateParticipantId() {
        // Generate short random ID: P_a4f2 (4 random alphanumeric chars)
        const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
        let randomStr = '';
        for (let i = 0; i < 4; i++) {
            randomStr += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        const autoId = `P_${randomStr}`;

        // Auto-fill the participant ID field
        document.getElementById('participant-id').value = autoId;

        console.log('Auto-generated participant ID:', autoId);
    }

    bindEvents() {
        // Welcome -> Participant screen
        document.getElementById('btn-to-participant').addEventListener('click', () => {
            this.showScreen('participant');
        });

        // Back to welcome
        document.getElementById('btn-back-welcome').addEventListener('click', () => {
            this.showScreen('welcome');
        });

        // Start session
        document.getElementById('btn-start').addEventListener('click', () => this.startSession());

        // Transition screen
        document.getElementById('btn-start-main').addEventListener('click', () => this.startMainStudy());

        // Image selection for practice
        document.getElementById('practice-left').addEventListener('click', () => this.selectImage('left'));
        document.getElementById('practice-right').addEventListener('click', () => this.selectImage('right'));

        // Image selection for main
        document.getElementById('main-left').addEventListener('click', () => this.selectImage('left'));
        document.getElementById('main-right').addEventListener('click', () => this.selectImage('right'));

        // Rating submit button
        document.getElementById('btn-submit-rating').addEventListener('click', () => this.submitRating());

        // Restart button
        document.getElementById('btn-restart').addEventListener('click', () => this.restart());

        // Survey form (mid-study)
        document.getElementById('survey-form').addEventListener('submit', (e) => this.submitSurvey(e));

        // Trust survey form
        document.getElementById('trust-survey-form').addEventListener('submit', (e) => this.submitTrustSurvey(e));

        // ATI survey form
        document.getElementById('ati-survey-form').addEventListener('submit', (e) => this.submitATISurvey(e));

        // Prolific ID form
        document.getElementById('prolific-form').addEventListener('submit', (e) => this.submitProlificId(e));

        // Ranking submit button
        document.getElementById('btn-submit-ranking').addEventListener('click', () => this.submitRanking());
    }

    setupKeyboardShortcuts() {
        // Keyboard shortcuts intentionally disabled — mouse only
    }

    showScreen(screenId) {
        document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
        document.getElementById(`screen-${screenId}`).classList.add('active');
    }

    showModal(modalId) {
        document.getElementById(modalId).classList.add('active');
    }

    hideModal(modalId) {
        document.getElementById(modalId).classList.remove('active');
        // Reset form
        document.getElementById('survey-form').reset();
    }

    async startSession() {
        const participantId = document.getElementById('participant-id').value.trim() || 'anonymous';
        const ageRange = document.getElementById('age-range').value;
        const gender = document.getElementById('gender').value;
        const museumVisits = document.getElementById('museum-visits').value;
        const education = document.getElementById('education').value;

        // Validate required fields
        if (!ageRange || !gender || !museumVisits || !education) {
            alert('Please fill in all required fields (age range, gender, museum visits, and education level).');
            return;
        }

        // Read study parameter from URL (?study=one or ?study=two)
        const urlParams = new URLSearchParams(window.location.search);
        const studyCode = urlParams.get('study');

        try {
            const response = await fetch('/api/start_session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    participant_id: participantId,
                    demographics: {
                        age_range: ageRange,
                        gender: gender,
                        museum_visits: museumVisits,
                        education: education
                    },
                    study: studyCode  // Pass study code to backend
                })
            });

            const data = await response.json();
            if (data.success) {
                this.sessionId = data.session_id;
                this.nPractice = data.n_practice;
                this.nMain = data.n_main;
                this.surveyInterval = data.survey_interval || 5;

                // Load recommendation config
                if (data.recommendations) {
                    this.recommendationConfig = data.recommendations;
                }

                this.phase = 'practice';
                this.practiceColorIndex = 0; // Reset color cycling
                await this.loadFirstPair();
                this.showScreen('practice');
            }
        } catch (error) {
            console.error('Error starting session:', error);
            alert('Failed to start session. Please try again.');
        }
    }

    async loadFirstPair() {
        // For practice: no images needed, just show placeholders immediately
        if (this.phase === 'practice') {
            this.currentPair = {
                image_1: { id: 'practice_a', path: null },
                image_2: { id: 'practice_b', path: null },
            };
            this.displayPair();
            return;
        }

        // For main: fetch first pair and wait for images to load
        try {
            const response = await fetch('/api/get_next_pair', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: this.sessionId })
            });

            const data = await response.json();
            if (data.success) {
                this.currentPair = data.pair;

                // Preload images and wait for them to load
                await Promise.all([
                    this.preloadImage(this.currentPair.image_1.path),
                    this.preloadImage(this.currentPair.image_2.path)
                ]);

                this.displayPair();
            }
        } catch (error) {
            console.error('Error loading first pair:', error);
        }
    }

    preloadImage(src) {
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => resolve();
            img.onerror = () => resolve(); // Resolve even on error to not block
            img.src = src;
        });
    }

    async fetchWithTimeout(url, options, timeoutMs = 15000) {
        // Create timeout promise
        const timeout = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Request timeout')), timeoutMs)
        );

        // Race between fetch and timeout
        return Promise.race([
            fetch(url, options),
            timeout
        ]);
    }

    async fetchNextPair(retryCount = 0) {
        // Fetch next pair from server and store in this.currentPair — no display
        try {
            console.log(`Fetching next pair from server... (attempt ${retryCount + 1})`);
            const startTime = Date.now();

            const response = await this.fetchWithTimeout('/api/get_next_pair', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: this.sessionId })
            }, 8000);

            console.log(`Server responded in ${Date.now() - startTime}ms`);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            if (data.success) {
                this.currentPair = data.pair;

                if (this.selectionTimestamp) {
                    const loadingTime = Date.now() - this.selectionTimestamp;
                    this.pairLoadingTimes.push(loadingTime);
                    console.log(`Pair loading time: ${loadingTime}ms`);
                }
            } else if (data.error) {
                throw new Error(data.error);
            }
        } catch (error) {
            console.error('Error loading pair:', error);
            console.error('Full error details:', error.stack);

            if (retryCount < 2) {
                console.log(`Retrying automatically in 1 second... (retry ${retryCount + 1}/2)`);
                await this.delay(1000);
                return this.fetchNextPair(retryCount + 1);
            } else {
                console.error('All retry attempts failed. Resetting to allow manual retry.');
                this.isProcessing = false;
            }
        }
    }

    async loadNextPair() {
        // Practice: set placeholders and display immediately (no server call)
        if (this.phase === 'practice') {
            this.currentPair = {
                image_1: { id: 'practice_a', path: null },
                image_2: { id: 'practice_b', path: null },
            };
            this.displayPair();
            return;
        }
        // Main: fetch then display
        await this.fetchNextPair();
        this.displayPair();
    }

    displayPair() {
        // Randomize left/right
        const showLeftFirst = Math.random() > 0.5;
        const leftImage = showLeftFirst ? this.currentPair.image_1 : this.currentPair.image_2;
        const rightImage = showLeftFirst ? this.currentPair.image_2 : this.currentPair.image_1;

        // Store which is which for submission
        this.currentPair.leftId = leftImage.id;
        this.currentPair.rightId = rightImage.id;
        this.currentPair.leftMeta = leftImage.metadata || {};
        this.currentPair.rightMeta = rightImage.metadata || {};
        this.displayTimestamp = Date.now();
        this.currentPair.onsetTimestamp = new Date().toISOString(); // Track when pair was shown

        const prefix = this.phase === 'practice' ? 'practice' : 'main';

        const leftCard = document.getElementById(`${prefix}-left`);
        const rightCard = document.getElementById(`${prefix}-right`);

        // Only update images for main phase (practice uses colored placeholders)
        if (this.phase !== 'practice') {
            leftCard.querySelector('img').src = leftImage.path;
            rightCard.querySelector('img').src = rightImage.path;
        } else {
            // Update practice placeholder colors
            this.updatePracticeColors();
        }

        // Reset selection state
        leftCard.classList.remove('selected');
        rightCard.classList.remove('selected');
    }

    updatePracticeColors() {
        const colors = this.practiceColors[this.practiceColorIndex % this.practiceColors.length];
        const leftBox = document.querySelector('#practice-left .placeholder-box');
        const rightBox = document.querySelector('#practice-right .placeholder-box');

        if (leftBox && rightBox) {
            leftBox.style.background = colors.left;
            rightBox.style.background = colors.right;
        }

        // Increment for next trial
        this.practiceColorIndex++;
    }

    async selectImage(side) {
        if (!this.currentPair || this.isProcessing) return;

        // Prevent double-clicks
        this.isProcessing = true;

        const decisionTimestamp = new Date().toISOString(); // When user clicked
        const responseTime = Date.now() - this.displayTimestamp;

        // Record selection timestamp for pair loading timing (only for main phase)
        if (this.phase === 'main') {
            this.selectionTimestamp = Date.now();
        }
        const chosenId = side === 'left' ? this.currentPair.leftId : this.currentPair.rightId;

        // Visual feedback
        const prefix = this.phase === 'practice' ? 'practice' : 'main';
        const selectedCard = document.getElementById(`${prefix}-${side}`);
        selectedCard.classList.add('selected');

        // Show selection feedback text
        const feedbackId = this.phase === 'practice' ? 'practice-selection-feedback' : 'selection-feedback';
        const feedbackEl = document.getElementById(feedbackId);
        if (feedbackEl) {
            feedbackEl.classList.remove('hidden');
        }
        const feedbackShownAt = Date.now();

        try {
            const response = await fetch('/api/submit_comparison', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    image_1: this.currentPair.image_1.id,
                    image_2: this.currentPair.image_2.id,
                    chosen: chosenId,
                    chosen_side: side,
                    response_time_ms: responseTime,
                    onset_timestamp: this.currentPair.onsetTimestamp,
                    decision_timestamp: decisionTimestamp
                })
            });

            const data = await response.json();
            if (data.success) {
                this.practiceCount = data.practice_count;
                this.mainCount = data.main_count;

                // Update utility visualization if in main phase
                if (this.phase === 'main') {
                    this.fetchUtilityViz();
                }

                // Determine what happens next
                const goesToRecommendations = data.phase === 'recommendations';
                const goesToTransition = data.practice_complete && this.phase === 'practice';
                const needsSurvey = this.phase === 'main' && this.surveyInterval > 0 && this.mainCount > 0 && this.mainCount % this.surveyInterval === 0;

                // Kick off fetch in parallel with feedback delay (main phase only) —
                // comparison is already recorded, so the model fits with latest data.
                // Practice is instant so no benefit to starting early.
                // Survey: fetch runs while user fills modal, display waits until modal closes.
                let fetchPromise = null;
                if (this.phase === 'main' && !goesToRecommendations && !goesToTransition) {
                    fetchPromise = this.fetchNextPair();
                    if (needsSurvey) {
                        this.pendingPairPromise = fetchPromise;
                    }
                }

                // Ensure minimum 2500ms feedback display time
                const elapsed = Date.now() - feedbackShownAt;
                const remainingDelay = Math.max(0, 2500 - elapsed);
                await this.delay(remainingDelay);

                if (goesToRecommendations) {
                    if (feedbackEl) feedbackEl.classList.add('hidden');
                    this.hideUtilityViz();
                    this.phase = 'recommendations';
                    this.showModal('survey-modal');
                } else if (goesToTransition) {
                    if (feedbackEl) feedbackEl.classList.add('hidden');
                    this.showScreen('transition');
                } else if (needsSurvey) {
                    if (feedbackEl) feedbackEl.classList.add('hidden');
                    this.showModal('survey-modal');
                } else if (this.phase === 'practice') {
                    if (feedbackEl) feedbackEl.classList.add('hidden');
                    this.loadNextPair();
                } else {
                    if (fetchPromise) await fetchPromise;
                    if (feedbackEl) feedbackEl.classList.add('hidden');
                    this.displayPair();
                }
            }
        } catch (error) {
            console.error('Error submitting comparison:', error);
            console.error('Full error details:', error.stack);
            // Silently recover from error
            // Hide feedback on error
            if (feedbackEl) {
                feedbackEl.classList.add('hidden');
            }
            // Remove selection highlight
            selectedCard.classList.remove('selected');
            // Note: Error logged to console for debugging, but not shown to user
        } finally {
            // Always reset processing flag so user can try again
            this.isProcessing = false;
        }
    }

    async submitSurvey(e) {
        e.preventDefault();

        const formData = new FormData(e.target);
        const surveyData = {
            certainty: formData.get('certainty'),
            know_prefs: formData.get('know-prefs'),
            features_like: formData.get('features-like') || '',
            features_dislike: formData.get('features-dislike') || ''
        };

        try {
            await fetch('/api/save_survey', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    survey_data: surveyData,
                    comparison_number: this.mainCount
                })
            });
        } catch (error) {
            console.error('Error saving survey:', error);
        }

        // Continue based on phase
        if (this.phase === 'recommendations') {
            this.hideModal('survey-modal');
            this.getRecommendations();
        } else {
            // Pair was fetched while survey was open — await it, close modal, then display
            if (this.pendingPairPromise) {
                await this.pendingPairPromise;
                this.pendingPairPromise = null;
            } else {
                await this.fetchNextPair();
            }
            this.hideModal('survey-modal');
            this.displayPair();
        }
    }

    async startMainStudy() {
        const btn = document.getElementById('btn-start-main');
        btn.classList.add('clicked');
        btn.textContent = 'Loading...';

        this.phase = 'main';
        await Promise.all([this.loadFirstPair(), this.delay(2000)]);

        btn.classList.remove('clicked');
        btn.textContent = 'Begin Main Study';
        this.showScreen('main');
    }

    async getRecommendations() {
        this.recommendationType = 'manual';
        this.selectedRecommendations = [];
        this.showScreen('loading');

        try {
            const response = await fetch('/api/get_recommendations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    n_recommendations: this.recommendationConfig.manual_show_n
                })
            });

            const data = await response.json();
            if (data.success && data.recommendations.length > 0) {
                // Randomize the order of recommendations
                this.recommendations = data.recommendations.sort(() => Math.random() - 0.5);
                this.showManualSelection();
            } else {
                alert('Could not generate recommendations. Please try again.');
                this.phase = 'main';
                this.loadNextPair();
            }
        } catch (error) {
            console.error('Error getting recommendations:', error);
            this.phase = 'main';
            this.loadNextPair();
        }
    }

    showManualSelection() {
        this.showScreen('manual-select');
        this.selectedRecommendations = [];

        const grid = document.getElementById('manual-recommendations-grid');
        grid.innerHTML = '';

        this.recommendations.forEach((rec, i) => {
            const card = document.createElement('div');
            card.className = 'recommendation-card';
            card.innerHTML = `<img src="${rec.path}" alt="Option ${i + 1}">`;
            card.dataset.recIndex = i;
            card.addEventListener('click', () => this.selectManualRecommendation(rec, card));
            grid.appendChild(card);
        });

        // Add confirm button for multi-select
        if (this.recommendationConfig.manual_select_n > 1) {
            const confirmBtn = document.createElement('button');
            confirmBtn.className = 'btn btn-primary confirm-selection-btn';
            confirmBtn.textContent = 'Confirm Selection';
            confirmBtn.disabled = true;
            confirmBtn.addEventListener('click', () => this.confirmManualSelection());
            grid.parentElement.appendChild(confirmBtn);
        }
    }

    selectManualRecommendation(rec, card) {
        const maxSelections = this.recommendationConfig.manual_select_n;

        if (maxSelections === 1) {
            // Single select mode
            document.querySelectorAll('#manual-recommendations-grid .recommendation-card').forEach(c => {
                c.classList.remove('selected');
            });
            card.classList.add('selected');
            this.selectedRecommendations = [rec];

            // Show result after short delay
            setTimeout(() => {
                this.showFinalResult();
            }, 500);
        } else {
            // Multi-select mode: toggle selection
            const index = this.selectedRecommendations.findIndex(r => r.image_id === rec.image_id);

            if (index > -1) {
                // Already selected, remove it
                this.selectedRecommendations.splice(index, 1);
                card.classList.remove('selected');
            } else if (this.selectedRecommendations.length < maxSelections) {
                // Add to selection
                this.selectedRecommendations.push(rec);
                card.classList.add('selected');
            }

            // Update confirm button state
            const confirmBtn = document.querySelector('.confirm-selection-btn');
            if (confirmBtn) {
                confirmBtn.disabled = this.selectedRecommendations.length !== maxSelections;
                confirmBtn.textContent = `Confirm Selection (${this.selectedRecommendations.length}/${maxSelections})`;
            }
        }
    }

    confirmManualSelection() {
        if (this.selectedRecommendations.length === 0) return;

        // Only show ranking if multiple items selected
        if (this.recommendationConfig.manual_select_n > 1) {
            this.showRanking();
        } else {
            this.showFinalResult(); // Single-select bypasses ranking
        }
    }

    showRanking() {
        this.showScreen('ranking');
        this.rankingStartTime = Date.now();
        this.rankingMovements = [];
        this.currentRanking = {};

        // Populate source area with selected images
        const sourceContainer = document.getElementById('ranking-source-images');
        sourceContainer.innerHTML = '';

        this.selectedRecommendations.forEach((rec, i) => {
            const imgDiv = document.createElement('div');
            imgDiv.className = 'ranking-image';
            imgDiv.draggable = true;
            imgDiv.dataset.imageId = rec.image_id;
            imgDiv.innerHTML = `<img src="${rec.path}" alt="Artwork ${i + 1}">`;
            sourceContainer.appendChild(imgDiv);
        });

        // Set up drag and drop event listeners
        this.setupRankingDragAndDrop();

        // Ensure continue button is disabled initially
        document.getElementById('btn-submit-ranking').disabled = true;
    }

    setupRankingDragAndDrop() {
        // Get all draggable images
        const images = document.querySelectorAll('.ranking-image');
        const dropZones = document.querySelectorAll('.drop-zone');
        const sourceArea = document.getElementById('ranking-source-images');

        // Set up drag events for images
        images.forEach(img => {
            img.addEventListener('dragstart', (e) => this.handleRankingDragStart(e));
            img.addEventListener('dragend', (e) => this.handleRankingDragEnd(e));
        });

        // Set up drop zones
        dropZones.forEach(zone => {
            zone.addEventListener('dragover', (e) => this.handleRankingDragOver(e));
            zone.addEventListener('dragleave', (e) => this.handleRankingDragLeave(e));
            zone.addEventListener('drop', (e) => this.handleRankingDrop(e));
        });

        // Set up source area as drop zone for unranking
        sourceArea.addEventListener('dragover', (e) => this.handleRankingDragOver(e));
        sourceArea.addEventListener('drop', (e) => this.handleRankingDropToSource(e));
    }

    handleRankingDragStart(e) {
        const imgDiv = e.target.closest('.ranking-image');
        imgDiv.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/html', imgDiv.innerHTML);
        e.dataTransfer.setData('image-id', imgDiv.dataset.imageId);
    }

    handleRankingDragEnd(e) {
        const imgDiv = e.target.closest('.ranking-image');
        imgDiv.classList.remove('dragging');
    }

    handleRankingDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        const dropZone = e.target.closest('.drop-zone');
        if (dropZone) {
            dropZone.classList.add('drag-over');
        }
    }

    handleRankingDragLeave(e) {
        const dropZone = e.target.closest('.drop-zone');
        if (dropZone) {
            dropZone.classList.remove('drag-over');
        }
    }

    handleRankingDrop(e) {
        e.preventDefault();
        const dropZone = e.target.closest('.drop-zone');
        if (!dropZone) return;

        dropZone.classList.remove('drag-over');

        const imageId = e.dataTransfer.getData('image-id');
        const position = parseInt(dropZone.dataset.position);

        // Find the dragged image element
        const draggedImg = document.querySelector(`.ranking-image[data-image-id="${imageId}"]`);
        if (!draggedImg) return;

        // Check if this slot already has an image
        const existingImg = dropZone.querySelector('.ranking-image');
        const sourceArea = document.getElementById('ranking-source-images');

        if (existingImg) {
            // Swap: return existing image to source
            const existingId = existingImg.dataset.imageId;
            sourceArea.appendChild(existingImg);

            // Remove old position from ranking
            for (let pos in this.currentRanking) {
                if (this.currentRanking[pos] === existingId) {
                    delete this.currentRanking[pos];
                    break;
                }
            }

            // Record swap movement
            this.rankingMovements.push({
                timestamp: Date.now() - this.rankingStartTime,
                image_id: existingId,
                action: 'swap_out',
                position: position,
                to: 'source'
            });
        }

        // Place dragged image in slot
        dropZone.appendChild(draggedImg);
        dropZone.classList.add('filled');

        // Update ranking
        const oldPosition = Object.keys(this.currentRanking).find(
            pos => this.currentRanking[pos] === imageId
        );

        if (oldPosition) {
            delete this.currentRanking[oldPosition];
        }

        this.currentRanking[position] = imageId;

        // Record movement
        this.rankingMovements.push({
            timestamp: Date.now() - this.rankingStartTime,
            image_id: imageId,
            action: 'place',
            position: position,
            from: oldPosition ? parseInt(oldPosition) : 'source'
        });

        // Check if all slots are filled
        this.checkRankingComplete();
    }

    handleRankingDropToSource(e) {
        e.preventDefault();
        const imageId = e.dataTransfer.getData('image-id');
        const draggedImg = document.querySelector(`.ranking-image[data-image-id="${imageId}"]`);
        if (!draggedImg) return;

        const sourceArea = document.getElementById('ranking-source-images');

        // Find which position this image was in
        const oldPosition = Object.keys(this.currentRanking).find(
            pos => this.currentRanking[pos] === imageId
        );

        if (oldPosition) {
            // Remove from ranking
            delete this.currentRanking[oldPosition];

            // Clear the drop zone
            const dropZone = document.querySelector(`.drop-zone[data-position="${oldPosition}"]`);
            if (dropZone) {
                dropZone.classList.remove('filled');
            }

            // Record movement
            this.rankingMovements.push({
                timestamp: Date.now() - this.rankingStartTime,
                image_id: imageId,
                action: 'unrank',
                position: null,
                from: parseInt(oldPosition)
            });
        }

        // Return to source
        sourceArea.appendChild(draggedImg);

        // Check completion status
        this.checkRankingComplete();
    }

    checkRankingComplete() {
        const numSlots = document.querySelectorAll('.drop-zone').length;
        const numRanked = Object.keys(this.currentRanking).length;

        const continueBtn = document.getElementById('btn-submit-ranking');
        continueBtn.disabled = numRanked !== numSlots;
    }

    async submitRanking() {
        const rankingTimeMs = Date.now() - this.rankingStartTime;

        // Build final ranking array [1st, 2nd, 3rd, 4th, 5th]
        const finalRanking = [];
        for (let i = 1; i <= 5; i++) {
            if (this.currentRanking[i]) {
                finalRanking.push(this.currentRanking[i]);
            }
        }

        const rankingData = {
            final_ranking: finalRanking,
            ranking_time_ms: rankingTimeMs,
            num_movements: this.rankingMovements.length,
            movements: this.rankingMovements
        };

        // Save to backend
        try {
            await fetch('/api/submit_ranking', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    ranking_data: rankingData
                })
            });
        } catch (error) {
            console.error('Error submitting ranking:', error);
            // Continue anyway - don't block user
        }

        // Reorder selectedRecommendations to match ranking
        const reordered = finalRanking.map(imageId =>
            this.selectedRecommendations.find(rec => rec.image_id === imageId)
        ).filter(rec => rec !== undefined);

        this.selectedRecommendations = reordered;

        // Show final result
        this.showFinalResult();
    }

    showFinalResult() {
        this.showScreen('result');

        // Remove any previous confirm button from manual select
        const oldConfirmBtn = document.querySelector('.confirm-selection-btn');
        if (oldConfirmBtn) oldConfirmBtn.remove();

        const finalArtwork = document.querySelector('.final-artwork');
        const details = document.getElementById('artwork-details');

        if (this.selectedRecommendations.length === 1) {
            // Single recommendation - show as before
            const rec = this.selectedRecommendations[0];
            document.getElementById('final-artwork-img').src = rec.path;

            const meta = rec.metadata || {};
            const title = meta.title || 'Untitled';
            const artistName = meta.artist || 'Unknown Artist';
            const year = meta.year || '';
            const style = meta.style ? meta.style.replace(/_/g, ' ') : 'Unknown Style';
            const titleWithYear = year ? `${title} (${year})` : title;

            details.innerHTML = `
                <div class="title">${titleWithYear}</div>
                <div class="artist">by ${artistName}</div>
                <div class="style">${style}</div>
            `;
        } else {
            // Multiple recommendations - show as gallery
            finalArtwork.innerHTML = '<div class="final-artwork-gallery"></div>';
            const gallery = finalArtwork.querySelector('.final-artwork-gallery');

            this.selectedRecommendations.forEach((rec, i) => {
                const item = document.createElement('div');
                item.className = 'gallery-item';
                item.innerHTML = `<img src="${rec.path}" alt="Selection ${i + 1}">`;
                gallery.appendChild(item);
            });

            // Show combined details
            const detailsHtml = this.selectedRecommendations.map((rec, i) => {
                const meta = rec.metadata || {};
                const title = meta.title || 'Untitled';
                const artistName = meta.artist || 'Unknown Artist';
                return `<div class="multi-detail"><strong>${i + 1}.</strong> ${title} by ${artistName}</div>`;
            }).join('');

            details.innerHTML = detailsHtml;
        }
    }

    async submitRating() {
        const ratingInput = document.querySelector('input[name="final-rating"]:checked');

        if (!ratingInput) {
            alert('Please select a rating before continuing.');
            return;
        }

        const rating = ratingInput.value;

        try {
            await fetch('/api/submit_rating', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    rating: parseInt(rating),
                    recommendation_type: this.recommendationType,
                    selected_artwork: this.selectedRecommendations.length === 1
                        ? this.selectedRecommendations[0]
                        : this.selectedRecommendations
                })
            });

            // Show trust survey instead of going directly to complete
            await this.delay(300);
            this.showTrustSurvey();
        } catch (error) {
            console.error('Error submitting rating:', error);
            this.showTrustSurvey();
        }
    }

    shuffleArray(array) {
        // Fisher-Yates shuffle
        const shuffled = [...array];
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }
        return shuffled;
    }

    showTrustSurvey() {
        this.showScreen('trust-survey');

        // Randomize trust items
        const shuffledItems = this.shuffleArray(this.trustItems);
        const container = document.getElementById('trust-questions-container');
        container.innerHTML = '';

        shuffledItems.forEach((item, index) => {
            const questionDiv = document.createElement('div');
            questionDiv.className = 'survey-question';

            const questionHTML = `
                <label>${index + 1}. ${item.text}</label>
                <div class="scale-options">
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="1" id="${item.id}-1" required>
                        <label for="${item.id}-1">Strongly disagree</label>
                    </div>
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="2" id="${item.id}-2">
                        <label for="${item.id}-2">Somewhat disagree</label>
                    </div>
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="3" id="${item.id}-3">
                        <label for="${item.id}-3">Neither agree nor disagree</label>
                    </div>
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="4" id="${item.id}-4">
                        <label for="${item.id}-4">Somewhat agree</label>
                    </div>
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="5" id="${item.id}-5">
                        <label for="${item.id}-5">Strongly agree</label>
                    </div>
                </div>
            `;

            questionDiv.innerHTML = questionHTML;
            container.appendChild(questionDiv);
        });
    }

    async submitTrustSurvey(e) {
        e.preventDefault();

        const formData = new FormData(e.target);
        const trustData = {};
        const unanswered = [];

        this.trustItems.forEach((item, i) => {
            const val = formData.get(item.id);
            if (!val) { unanswered.push(i + 1); }
            trustData[item.id] = parseInt(val);
        });

        if (unanswered.length > 0) {
            alert(`Please answer all questions before continuing. Missing: question ${unanswered.join(', ')}.`);
            return;
        }

        try {
            await fetch('/api/save_trust_survey', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    trust_data: trustData
                })
            });

            // Skip ATI survey, go directly to Prolific screen
            this.showScreen('prolific');
        } catch (error) {
            console.error('Error saving trust survey:', error);
            this.showScreen('prolific');
        }
    }

    showATISurvey() {
        this.showScreen('ati-survey');

        // Randomize ATI items
        const shuffledItems = this.shuffleArray(this.atiItems);
        const container = document.getElementById('ati-questions-container');
        container.innerHTML = '';

        shuffledItems.forEach((item, index) => {
            const questionDiv = document.createElement('div');
            questionDiv.className = 'survey-question';

            const questionHTML = `
                <label>${index + 1}. ${item.text}</label>
                <div class="scale-options">
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="1" id="${item.id}-1" required>
                        <label for="${item.id}-1">Completely disagree</label>
                    </div>
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="2" id="${item.id}-2">
                        <label for="${item.id}-2">Largely disagree</label>
                    </div>
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="3" id="${item.id}-3">
                        <label for="${item.id}-3">Slightly disagree</label>
                    </div>
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="4" id="${item.id}-4">
                        <label for="${item.id}-4">Slightly agree</label>
                    </div>
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="5" id="${item.id}-5">
                        <label for="${item.id}-5">Largely agree</label>
                    </div>
                    <div class="scale-option">
                        <input type="radio" name="${item.id}" value="6" id="${item.id}-6">
                        <label for="${item.id}-6">Completely agree</label>
                    </div>
                </div>
            `;

            questionDiv.innerHTML = questionHTML;
            container.appendChild(questionDiv);
        });
    }

    async submitATISurvey(e) {
        e.preventDefault();

        const formData = new FormData(e.target);
        const atiData = {};
        const unanswered = [];

        this.atiItems.forEach((item, i) => {
            const val = formData.get(item.id);
            if (!val) { unanswered.push(i + 1); }
            atiData[item.id] = parseInt(val);
        });

        if (unanswered.length > 0) {
            alert(`Please answer all questions before continuing. Missing: question ${unanswered.join(', ')}.`);
            return;
        }

        try {
            await fetch('/api/save_ati_survey', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    ati_data: atiData
                })
            });

            // Show Prolific ID screen
            this.showScreen('prolific');
        } catch (error) {
            console.error('Error saving ATI survey:', error);
            this.showScreen('prolific');
        }
    }

    async submitProlificId(e) {
        e.preventDefault();

        const prolificId = document.getElementById('prolific-id').value.trim();

        if (!prolificId) {
            alert('Please enter your Prolific ID to complete the study.');
            return;
        }

        try {
            await fetch('/api/save_prolific_id', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    prolific_id: prolificId
                })
            });

            // Now show complete screen
            this.showComplete();
        } catch (error) {
            console.error('Error saving Prolific ID:', error);
            // Still show complete screen even if saving fails
            this.showComplete();
        }
    }

    async submitTimingStats() {
        if (this.pairLoadingTimes.length === 0) return;

        // Calculate statistics
        const times = this.pairLoadingTimes;
        const mean = times.reduce((sum, t) => sum + t, 0) / times.length;
        const variance = times.reduce((sum, t) => sum + Math.pow(t - mean, 2), 0) / times.length;
        const std = Math.sqrt(variance);
        const min = Math.min(...times);
        const max = Math.max(...times);

        const stats = {
            session_id: this.sessionId,
            loading_times: times,
            mean: Math.round(mean),
            std: Math.round(std),
            min: min,
            max: max,
            count: times.length
        };

        console.log('=== PAIR LOADING TIME STATISTICS ===');
        console.log(`Mean: ${stats.mean}ms`);
        console.log(`Std: ${stats.std}ms`);
        console.log(`Min: ${stats.min}ms`);
        console.log(`Max: ${stats.max}ms`);
        console.log(`Count: ${stats.count}`);
        console.log('====================================');

        try {
            await fetch('/api/submit_timing_stats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(stats)
            });
        } catch (error) {
            console.error('Error submitting timing stats:', error);
        }
    }

    async showComplete() {
        // Submit timing statistics before showing complete screen
        await this.submitTimingStats();

        this.phase = 'complete';
        this.showScreen('complete');
        document.getElementById('final-session-id').textContent = this.sessionId;
    }

    restart() {
        this.sessionId = null;
        this.currentPair = null;
        this.phase = 'welcome';
        this.practiceCount = 0;
        this.mainCount = 0;
        this.recommendations = [];
        this.selectedRecommendations = [];
        this.recommendationType = null;
        this.utilityVizData = null;
        this.hideUtilityViz();

        this.generateParticipantId(); // Generate new ID for new session
        document.getElementById('age-range').value = '';
        document.getElementById('gender').value = '';
        document.getElementById('museum-visits').value = '';
        document.getElementById('education').value = '';

        // Reset survey forms
        document.getElementById('trust-survey-form').reset();
        document.getElementById('ati-survey-form').reset();

        // Reset final artwork container for next session
        const finalArtwork = document.querySelector('.final-artwork');
        if (finalArtwork) {
            finalArtwork.innerHTML = '<img id="final-artwork-img" src="" alt="Your recommended artwork">';
        }

        this.showScreen('welcome');
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async fetchUtilityViz() {
        try {
            const response = await fetch('/api/get_utility_viz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: this.sessionId })
            });

            const data = await response.json();
            if (data.success && data.has_data) {
                this.utilityVizData = data;
                this.renderUtilityViz();
            } else {
                // No data yet (burn-in phase)
                this.hideUtilityViz();
            }
        } catch (error) {
            console.error('Error fetching utility viz:', error);
            this.hideUtilityViz();
        }
    }

    renderUtilityViz() {
        if (!this.utilityVizData) return;

        const panel = document.getElementById('utility-viz-panel');
        const thumb = document.getElementById('top-image-thumb');
        const svg = document.getElementById('utility-timeline');

        // Update thumbnail
        if (this.utilityVizData.top_image && this.utilityVizData.top_image.path) {
            thumb.src = this.utilityVizData.top_image.path;
        }

        // Render timeline
        this.renderTimelineSVG(svg, this.utilityVizData.timeline);

        // Show panel
        panel.classList.remove('hidden');
    }

    renderTimelineSVG(svg, timeline) {
        if (!timeline || timeline.length === 0) {
            svg.innerHTML = '';
            return;
        }

        // Get SVG dimensions
        const width = 280;
        const height = 60;
        const padding = 5;

        // Calculate scales
        const xScale = (width - 2 * padding) / Math.max(1, timeline.length - 1);

        // Get all utility values for scaling
        const allUtilities = timeline.flatMap(t => [t.max_utility, t.mean_utility]);
        const minUtil = Math.min(...allUtilities);
        const maxUtil = Math.max(...allUtilities);
        const utilRange = maxUtil - minUtil || 1;

        const yScale = (y) => height - padding - ((y - minUtil) / utilRange) * (height - 2 * padding);

        // Build SVG paths
        let meanPath = '';
        let maxPath = '';
        const changeDots = [];
        let currentDot = null;

        timeline.forEach((point, i) => {
            const x = padding + i * xScale;
            const yMean = yScale(point.mean_utility);
            const yMax = yScale(point.max_utility);

            // Build polylines
            if (i === 0) {
                meanPath = `M ${x},${yMean}`;
                maxPath = `M ${x},${yMax}`;
            } else {
                meanPath += ` L ${x},${yMean}`;
                maxPath += ` L ${x},${yMax}`;
            }

            // Mark change points
            if (point.top_changed && i > 0) {
                changeDots.push({ x, y: yMax });
            }

            // Current (last) point
            if (i === timeline.length - 1) {
                currentDot = { x, y: yMax };
            }
        });

        // Build SVG innerHTML
        let svgContent = `
            <path class="timeline-mean-line" d="${meanPath}"></path>
            <path class="timeline-max-line" d="${maxPath}"></path>
        `;

        // Add change dots
        changeDots.forEach(dot => {
            svgContent += `<circle class="timeline-change-dot" cx="${dot.x}" cy="${dot.y}" r="3"></circle>`;
        });

        // Add current dot
        if (currentDot) {
            svgContent += `<circle class="timeline-current-dot" cx="${currentDot.x}" cy="${currentDot.y}" r="4"></circle>`;
        }

        svg.innerHTML = svgContent;
    }

    hideUtilityViz() {
        const panel = document.getElementById('utility-viz-panel');
        if (panel) {
            panel.classList.add('hidden');
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.study = new ArtPreferenceStudy();
});
