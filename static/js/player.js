document.addEventListener('DOMContentLoaded', function() {
    // Initialize video player
    const videoContainer = document.getElementById('video-container');
    
    if (!videoContainer) return;
    
    const videoSlug = videoContainer.dataset.slug;
    const videoStatus = videoContainer.dataset.status;
    const playerType = videoContainer.dataset.playerType || 'native';
    const videoSourceHls = videoContainer.dataset.hlsSource;
    const videoSourceMp4 = videoContainer.dataset.mp4Source;
    
    // Initialize player if video is completed and player hasn't been loaded yet
    if (videoStatus === 'completed' && !videoContainer.querySelector('video')) {
        console.log('Initializing player for completed video');
        if (playerType === 'hls' && videoSourceHls) {
            initializeHlsPlayer(videoSourceHls);
        } else if (videoSourceMp4) {
            initializeNativePlayer(videoSourceMp4);
        }
        
        // Update the volume icon based on muted state (now unmuted by default)
        setTimeout(() => {
            const volumeBtn = document.querySelector('.volume-btn');
            if (volumeBtn) {
                volumeBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
            }
        }, 500);
    }
    
    /**
     * Initialize HLS.js player for adaptive streaming
     */
    function initializeHlsPlayer(sourceUrl) {
        // Create custom player container
        const video = document.createElement('video');
        video.id = 'video-player';
        video.className = 'streamable-player';
        video.controls = false; // We'll create custom controls
        video.autoplay = true; // Enable autoplay
        video.muted = false; // Unmuted by default
        video.preload = 'auto';
        video.playsInline = true; // Better mobile support
        video.loop = true; // Enable looping
        
        videoContainer.appendChild(video);
        
        // Create wrapper for controls and progress bar
        const controlWrapper = document.createElement('div');
        controlWrapper.className = 'video-control-wrapper';
        
        // Create custom controls
        const controls = document.createElement('div');
        controls.className = 'video-player-controls';
        
        // Create progress bar
        const progressBar = document.createElement('div');
        progressBar.className = 'video-progress-bar';
        const progressValue = document.createElement('div');
        progressValue.className = 'video-progress-value';
        progressBar.appendChild(progressValue);
        
        // Create time preview element for scrubber
        const timePreview = document.createElement('div');
        timePreview.className = 'video-time-preview';
        progressBar.appendChild(timePreview);
        
        // Create play/pause button
        const playPauseBtn = document.createElement('button');
        playPauseBtn.className = 'custom-video-control play-pause-btn';
        playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
        playPauseBtn.title = "Play/Pause";
        
        // Create backward skip button (10s)
        const backwardBtn = document.createElement('button');
        backwardBtn.className = 'skip-button backward-btn';
        backwardBtn.innerHTML = '<i class="fas fa-undo"></i>';
        backwardBtn.title = "Back 10 seconds";
        
        // Create forward skip button (10s)
        const forwardBtn = document.createElement('button');
        forwardBtn.className = 'skip-button forward-btn';
        forwardBtn.innerHTML = '<i class="fas fa-redo"></i>';
        forwardBtn.title = "Forward 10 seconds";
        
        // Create time display
        const timeDisplay = document.createElement('span');
        timeDisplay.className = 'time-display';
        timeDisplay.textContent = '0:00 / 0:00';
        
        // Create volume container with slider
        const volumeContainer = document.createElement('div');
        volumeContainer.className = 'volume-container';
        
        // Create volume button
        const volumeBtn = document.createElement('button');
        volumeBtn.className = 'custom-video-control volume-btn';
        volumeBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
        volumeBtn.title = "Toggle mute";
        
        // Create volume slider
        const volumeSlider = document.createElement('div');
        volumeSlider.className = 'volume-slider';
        
        const volumeLevel = document.createElement('div');
        volumeLevel.className = 'volume-level';
        volumeSlider.appendChild(volumeLevel);
        volumeContainer.appendChild(volumeBtn);
        volumeContainer.appendChild(volumeSlider);
        
        // Create speed control
        const speedContainer = document.createElement('div');
        speedContainer.className = 'speed-container';
        
        const speedButton = document.createElement('button');
        speedButton.className = 'speed-button';
        speedButton.innerHTML = '1x';
        speedButton.title = "Playback speed";
        
        const speedDropdown = document.createElement('div');
        speedDropdown.className = 'speed-dropdown';
        
        const speedOptions = [
            { text: '0.5x', value: 0.5 },
            { text: '0.75x', value: 0.75 },
            { text: 'Normal', value: 1 },
            { text: '1.25x', value: 1.25 },
            { text: '1.5x', value: 1.5 },
            { text: '2x', value: 2 }
        ];
        
        speedOptions.forEach(option => {
            const speedOption = document.createElement('div');
            speedOption.className = 'speed-option' + (option.value === 1 ? ' active' : '');
            speedOption.textContent = option.text;
            speedOption.dataset.speed = option.value;
            speedDropdown.appendChild(speedOption);
        });
        
        speedContainer.appendChild(speedButton);
        speedContainer.appendChild(speedDropdown);
        
        // Create PiP button if supported
        const pipButton = document.createElement('button');
        pipButton.className = 'pip-button';
        pipButton.innerHTML = '<i class="fas fa-external-link-alt"></i>';
        pipButton.title = "Picture in Picture";
        
        // Create fullscreen button
        const fullscreenBtn = document.createElement('button');
        fullscreenBtn.className = 'custom-video-control video-fullscreen-btn';
        fullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>';
        fullscreenBtn.title = "Fullscreen";
        
        // Add controls to container
        controls.appendChild(playPauseBtn);
        controls.appendChild(backwardBtn);
        controls.appendChild(forwardBtn);
        controls.appendChild(timeDisplay);
        controls.appendChild(volumeContainer);
        controls.appendChild(speedContainer);
        controls.appendChild(pipButton);
        controls.appendChild(fullscreenBtn);
        
        // Build control wrapper
        controlWrapper.appendChild(progressBar);
        controlWrapper.appendChild(controls);
        
        // Add control wrapper to video container
        videoContainer.appendChild(controlWrapper);
        
        // Control event listeners
        playPauseBtn.addEventListener('click', function() {
            if (video.paused) {
                video.play();
                playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
            } else {
                video.pause();
                playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
            }
        });
        
        // Skip backward 10 seconds
        backwardBtn.addEventListener('click', function() {
            video.currentTime = Math.max(0, video.currentTime - 10);
        });
        
        // Skip forward 10 seconds
        forwardBtn.addEventListener('click', function() {
            video.currentTime = Math.min(video.duration, video.currentTime + 10);
        });
        
        // Volume controls
        volumeBtn.addEventListener('click', function() {
            video.muted = !video.muted;
            if (video.muted) {
                volumeBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
                volumeLevel.style.width = '0%';
            } else {
                volumeBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
                volumeLevel.style.width = (video.volume * 100) + '%';
            }
        });
        
        // Volume slider
        volumeSlider.addEventListener('click', function(e) {
            const rect = volumeSlider.getBoundingClientRect();
            const pos = (e.clientX - rect.left) / rect.width;
            video.volume = Math.max(0, Math.min(1, pos));
            volumeLevel.style.width = (video.volume * 100) + '%';
            if (video.volume === 0) {
                video.muted = true;
                volumeBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
            } else {
                video.muted = false;
                volumeBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
            }
        });
        
        // Speed control
        speedButton.addEventListener('click', function() {
            if (speedDropdown.style.display === 'flex') {
                speedDropdown.style.display = 'none';
            } else {
                speedDropdown.style.display = 'flex';
            }
        });
        
        // Hide speed dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!speedContainer.contains(e.target)) {
                speedDropdown.style.display = 'none';
            }
        });
        
        // Speed options
        speedDropdown.querySelectorAll('.speed-option').forEach(option => {
            option.addEventListener('click', function() {
                const speed = parseFloat(this.dataset.speed);
                video.playbackRate = speed;
                speedButton.innerHTML = speed === 1 ? '1x' : this.textContent;
                
                // Update active status
                speedDropdown.querySelectorAll('.speed-option').forEach(opt => {
                    opt.classList.remove('active');
                });
                this.classList.add('active');
                
                speedDropdown.style.display = 'none';
            });
        });
        
        // Picture-in-Picture
        if ('pictureInPictureEnabled' in document) {
            pipButton.addEventListener('click', function() {
                if (document.pictureInPictureElement) {
                    document.exitPictureInPicture();
                } else {
                    video.requestPictureInPicture();
                }
            });
        } else {
            pipButton.style.display = 'none';
        }
        
        // Fullscreen
        fullscreenBtn.addEventListener('click', function() {
            if (!document.fullscreenElement) {
                videoContainer.requestFullscreen().catch(err => {
                    console.error(`Error attempting to enable fullscreen: ${err.message}`);
                });
                fullscreenBtn.innerHTML = '<i class="fas fa-compress"></i>';
            } else {
                document.exitFullscreen();
                fullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>';
            }
        });
        
        // Progress bar update
        video.addEventListener('timeupdate', function() {
            if (video.duration) {
                const progress = (video.currentTime / video.duration) * 100;
                progressValue.style.width = `${progress}%`;
                
                // Update time display
                const currentMinutes = Math.floor(video.currentTime / 60);
                const currentSeconds = Math.floor(video.currentTime % 60);
                const durationMinutes = Math.floor(video.duration / 60);
                const durationSeconds = Math.floor(video.duration % 60);
                
                timeDisplay.textContent = `${currentMinutes}:${currentSeconds < 10 ? '0' : ''}${currentSeconds} / ${durationMinutes}:${durationSeconds < 10 ? '0' : ''}${durationSeconds}`;
            }
        });
        
        // Progress bar click handling
        progressBar.addEventListener('click', function(e) {
            const rect = progressBar.getBoundingClientRect();
            const pos = (e.clientX - rect.left) / rect.width;
            video.currentTime = pos * video.duration;
        });
        
        // Progress bar hover for time preview
        progressBar.addEventListener('mousemove', function(e) {
            const rect = progressBar.getBoundingClientRect();
            const pos = Math.min(Math.max(0, (e.clientX - rect.left) / rect.width), 1);
            
            if (video.duration) {
                // Calculate time at cursor position
                const previewTime = pos * video.duration;
                const previewMinutes = Math.floor(previewTime / 60);
                const previewSeconds = Math.floor(previewTime % 60);
                
                // Update time preview text and position
                timePreview.textContent = `${previewMinutes}:${previewSeconds < 10 ? '0' : ''}${previewSeconds}`;
                timePreview.style.left = `${pos * 100}%`;
            }
        });
        
        // Check if HLS.js is supported
        if (Hls.isSupported()) {
            const hls = new Hls({
                debug: false,
                enableWorker: true,
                lowLatencyMode: false, // Disable low latency to focus on stability
                backBufferLength: 30, // Reduced buffer length
                maxBufferLength: 30, // Maximum buffer size in seconds
                maxMaxBufferLength: 60, // Maximum buffer size when in ABR algorithm decides to switch to a higher quality level
                maxBufferHole: 0.5, // Maximum interval holes allowed in buffer
                maxStarvationDelay: 4, // Maximum delay before playback starvation
                highBufferWatchdogPeriod: 2, // Time to wait before declaring buffer out-of-bounds
                nudgeMaxRetry: 5, // Maximum amount of nudge retries allowed for a simple buffer stall
                startFragPrefetch: true, // Start prefetching the first fragment
                abrEwmaDefaultEstimate: 500000, // Default bandwidth estimate (500kbps)
                testBandwidth: true // Test the available bandwidth before loading segments
            });
            
            hls.loadSource(sourceUrl);
            hls.attachMedia(video);
            
            hls.on(Hls.Events.MANIFEST_PARSED, function() {
                console.log('HLS manifest parsed, ready to play');
                video.play().catch(error => {
                    console.log('Autoplay prevented by browser, waiting for user interaction');
                    playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
                });
            });
            
            // Make the entire video clickable for play/pause
            video.addEventListener('click', function() {
                if (video.paused) {
                    video.play();
                    playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
                } else {
                    video.pause();
                    playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
                }
            });
            
            hls.on(Hls.Events.ERROR, function(event, data) {
                console.error('HLS error:', data);
                if (data.fatal) {
                    switch(data.type) {
                        case Hls.ErrorTypes.NETWORK_ERROR:
                            console.log('Fatal network error, trying to recover');
                            hls.startLoad();
                            break;
                        case Hls.ErrorTypes.MEDIA_ERROR:
                            console.log('Fatal media error, trying to recover');
                            hls.recoverMediaError();
                            break;
                        default:
                            console.error('Fatal error, cannot recover');
                            // Try falling back to direct MP4 playback
                            if (videoSourceMp4) {
                                console.log('Falling back to MP4 playback');
                                video.src = videoSourceMp4;
                                video.load();
                                video.play().catch(e => console.error('Playback error:', e));
                            } else {
                                hls.destroy();
                            }
                            break;
                    }
                }
            });
            
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            // Native HLS support (Safari)
            video.src = sourceUrl;
        } else {
            // Fallback to MP4 if available
            if (videoSourceMp4) {
                video.src = videoSourceMp4;
            } else {
                videoContainer.innerHTML = '<div class="alert alert-danger">Your browser does not support HLS playback and no fallback is available.</div>';
            }
        }
    }
    
    /**
     * Initialize native HTML5 video player
     */
    function initializeNativePlayer(sourceUrl) {
        // Create custom player container similar to HLS player
        const video = document.createElement('video');
        video.id = 'video-player';
        video.className = 'streamable-player';
        video.controls = false; // We'll use custom controls
        video.autoplay = true; // Enable autoplay
        video.muted = false; // Unmuted by default
        video.preload = 'auto';
        video.playsInline = true; // Better mobile support
        video.crossOrigin = 'anonymous'; // Allow CORS
        video.loop = true; // Enable looping
        
        const source = document.createElement('source');
        source.src = sourceUrl;
        source.type = 'video/mp4';
        
        video.appendChild(source);
        videoContainer.appendChild(video);
        
        // Create wrapper for controls and progress bar
        const controlWrapper = document.createElement('div');
        controlWrapper.className = 'video-control-wrapper';
        
        // Create custom controls
        const controls = document.createElement('div');
        controls.className = 'video-player-controls';
        
        // Create progress bar
        const progressBar = document.createElement('div');
        progressBar.className = 'video-progress-bar';
        const progressValue = document.createElement('div');
        progressValue.className = 'video-progress-value';
        progressBar.appendChild(progressValue);
        
        // Create time preview element for scrubber
        const timePreview = document.createElement('div');
        timePreview.className = 'video-time-preview';
        progressBar.appendChild(timePreview);
        
        // Create play/pause button
        const playPauseBtn = document.createElement('button');
        playPauseBtn.className = 'custom-video-control play-pause-btn';
        playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
        playPauseBtn.title = "Play/Pause";
        
        // Create backward skip button (10s)
        const backwardBtn = document.createElement('button');
        backwardBtn.className = 'skip-button backward-btn';
        backwardBtn.innerHTML = '<i class="fas fa-undo"></i>';
        backwardBtn.title = "Back 10 seconds";
        
        // Create forward skip button (10s)
        const forwardBtn = document.createElement('button');
        forwardBtn.className = 'skip-button forward-btn';
        forwardBtn.innerHTML = '<i class="fas fa-redo"></i>';
        forwardBtn.title = "Forward 10 seconds";
        
        // Create time display
        const timeDisplay = document.createElement('span');
        timeDisplay.className = 'time-display';
        timeDisplay.textContent = '0:00 / 0:00';
        
        // Create volume container with slider
        const volumeContainer = document.createElement('div');
        volumeContainer.className = 'volume-container';
        
        // Create volume button
        const volumeBtn = document.createElement('button');
        volumeBtn.className = 'custom-video-control volume-btn';
        volumeBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
        volumeBtn.title = "Toggle mute";
        
        // Create volume slider
        const volumeSlider = document.createElement('div');
        volumeSlider.className = 'volume-slider';
        
        const volumeLevel = document.createElement('div');
        volumeLevel.className = 'volume-level';
        volumeSlider.appendChild(volumeLevel);
        volumeContainer.appendChild(volumeBtn);
        volumeContainer.appendChild(volumeSlider);
        
        // Create speed control
        const speedContainer = document.createElement('div');
        speedContainer.className = 'speed-container';
        
        const speedButton = document.createElement('button');
        speedButton.className = 'speed-button';
        speedButton.innerHTML = '1x';
        speedButton.title = "Playback speed";
        
        const speedDropdown = document.createElement('div');
        speedDropdown.className = 'speed-dropdown';
        
        const speedOptions = [
            { text: '0.5x', value: 0.5 },
            { text: '0.75x', value: 0.75 },
            { text: 'Normal', value: 1 },
            { text: '1.25x', value: 1.25 },
            { text: '1.5x', value: 1.5 },
            { text: '2x', value: 2 }
        ];
        
        speedOptions.forEach(option => {
            const speedOption = document.createElement('div');
            speedOption.className = 'speed-option' + (option.value === 1 ? ' active' : '');
            speedOption.textContent = option.text;
            speedOption.dataset.speed = option.value;
            speedDropdown.appendChild(speedOption);
        });
        
        speedContainer.appendChild(speedButton);
        speedContainer.appendChild(speedDropdown);
        
        // Create PiP button if supported
        const pipButton = document.createElement('button');
        pipButton.className = 'pip-button';
        pipButton.innerHTML = '<i class="fas fa-external-link-alt"></i>';
        pipButton.title = "Picture in Picture";
        
        // Create fullscreen button
        const fullscreenBtn = document.createElement('button');
        fullscreenBtn.className = 'custom-video-control video-fullscreen-btn';
        fullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>';
        fullscreenBtn.title = "Fullscreen";
        
        // Add controls to container
        controls.appendChild(playPauseBtn);
        controls.appendChild(backwardBtn);
        controls.appendChild(forwardBtn);
        controls.appendChild(timeDisplay);
        controls.appendChild(volumeContainer);
        controls.appendChild(speedContainer);
        controls.appendChild(pipButton);
        controls.appendChild(fullscreenBtn);
        
        // Build control wrapper
        controlWrapper.appendChild(progressBar);
        controlWrapper.appendChild(controls);
        
        // Add control wrapper to video container
        videoContainer.appendChild(controlWrapper);
        
        // Add buffering indicator
        const bufferingIndicator = document.createElement('div');
        bufferingIndicator.className = 'buffering-indicator d-none position-absolute top-50 start-50 translate-middle';
        bufferingIndicator.innerHTML = '<div class="spinner-border text-light" role="status"><span class="visually-hidden">Loading...</span></div>';
        videoContainer.appendChild(bufferingIndicator);
        
        // Update volume button display to reflect unmuted state
        video.addEventListener('loadedmetadata', function() {
            if (!video.muted) {
                volumeBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
                volumeLevel.style.width = (video.volume * 100) + '%';
            }
        });
        
        // Control event listeners
        playPauseBtn.addEventListener('click', function() {
            if (video.paused) {
                video.play();
                playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
            } else {
                video.pause();
                playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
            }
        });
        
        // Skip backward 10 seconds
        backwardBtn.addEventListener('click', function() {
            video.currentTime = Math.max(0, video.currentTime - 10);
        });
        
        // Skip forward 10 seconds
        forwardBtn.addEventListener('click', function() {
            video.currentTime = Math.min(video.duration, video.currentTime + 10);
        });
        
        // Volume controls
        volumeBtn.addEventListener('click', function() {
            video.muted = !video.muted;
            if (video.muted) {
                volumeBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
                volumeLevel.style.width = '0%';
            } else {
                volumeBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
                volumeLevel.style.width = (video.volume * 100) + '%';
            }
        });
        
        // Volume slider
        volumeSlider.addEventListener('click', function(e) {
            const rect = volumeSlider.getBoundingClientRect();
            const pos = (e.clientX - rect.left) / rect.width;
            video.volume = Math.max(0, Math.min(1, pos));
            volumeLevel.style.width = (video.volume * 100) + '%';
            if (video.volume === 0) {
                video.muted = true;
                volumeBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
            } else {
                video.muted = false;
                volumeBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
            }
        });
        
        // Speed control
        speedButton.addEventListener('click', function() {
            if (speedDropdown.style.display === 'flex') {
                speedDropdown.style.display = 'none';
            } else {
                speedDropdown.style.display = 'flex';
            }
        });
        
        // Hide speed dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (!speedContainer.contains(e.target)) {
                speedDropdown.style.display = 'none';
            }
        });
        
        // Speed options
        speedDropdown.querySelectorAll('.speed-option').forEach(option => {
            option.addEventListener('click', function() {
                const speed = parseFloat(this.dataset.speed);
                video.playbackRate = speed;
                speedButton.innerHTML = speed === 1 ? '1x' : this.textContent;
                
                // Update active status
                speedDropdown.querySelectorAll('.speed-option').forEach(opt => {
                    opt.classList.remove('active');
                });
                this.classList.add('active');
                
                speedDropdown.style.display = 'none';
            });
        });
        
        // Picture-in-Picture
        if ('pictureInPictureEnabled' in document) {
            pipButton.addEventListener('click', function() {
                if (document.pictureInPictureElement) {
                    document.exitPictureInPicture();
                } else {
                    video.requestPictureInPicture();
                }
            });
        } else {
            pipButton.style.display = 'none';
        }
        
        // Fullscreen
        fullscreenBtn.addEventListener('click', function() {
            if (!document.fullscreenElement) {
                videoContainer.requestFullscreen().catch(err => {
                    console.error(`Error attempting to enable fullscreen: ${err.message}`);
                });
                fullscreenBtn.innerHTML = '<i class="fas fa-compress"></i>';
            } else {
                document.exitFullscreen();
                fullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>';
            }
        });
        
        // Progress bar update
        video.addEventListener('timeupdate', function() {
            if (video.duration) {
                const progress = (video.currentTime / video.duration) * 100;
                progressValue.style.width = `${progress}%`;
                
                // Update time display
                const currentMinutes = Math.floor(video.currentTime / 60);
                const currentSeconds = Math.floor(video.currentTime % 60);
                const durationMinutes = Math.floor(video.duration / 60);
                const durationSeconds = Math.floor(video.duration % 60);
                
                timeDisplay.textContent = `${currentMinutes}:${currentSeconds < 10 ? '0' : ''}${currentSeconds} / ${durationMinutes}:${durationSeconds < 10 ? '0' : ''}${durationSeconds}`;
            }
        });
        
        // Progress bar click handling
        progressBar.addEventListener('click', function(e) {
            const rect = progressBar.getBoundingClientRect();
            const pos = (e.clientX - rect.left) / rect.width;
            video.currentTime = pos * video.duration;
        });
        
        // Progress bar hover for time preview
        progressBar.addEventListener('mousemove', function(e) {
            const rect = progressBar.getBoundingClientRect();
            const pos = Math.min(Math.max(0, (e.clientX - rect.left) / rect.width), 1);
            
            if (video.duration) {
                // Calculate time at cursor position
                const previewTime = pos * video.duration;
                const previewMinutes = Math.floor(previewTime / 60);
                const previewSeconds = Math.floor(previewTime % 60);
                
                // Update time preview text and position
                timePreview.textContent = `${previewMinutes}:${previewSeconds < 10 ? '0' : ''}${previewSeconds}`;
                timePreview.style.left = `${pos * 100}%`;
            }
        });
        
        // Show buffering indicator when waiting for data
        video.addEventListener('waiting', function() {
            bufferingIndicator.classList.remove('d-none');
        });
        
        // Hide buffering indicator when playing
        video.addEventListener('playing', function() {
            bufferingIndicator.classList.add('d-none');
        });
        
        // Start playing when loaded
        video.addEventListener('loadedmetadata', function() {
            video.play().catch(error => {
                console.log('Autoplay prevented by browser, waiting for user interaction');
                playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
            });
        });
        
        // Make the entire video clickable for play/pause
        video.addEventListener('click', function() {
            if (video.paused) {
                video.play();
                playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
            } else {
                video.pause();
                playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
            }
        });
        
        // Error handling
        video.addEventListener('error', function(e) {
            console.error('Video playback error', e);
            // Try to diagnose the error
            const errorMessage = document.createElement('div');
            errorMessage.className = 'alert alert-danger mt-3';
            
            switch (e.target.error.code) {
                case e.target.error.MEDIA_ERR_ABORTED:
                    errorMessage.textContent = 'You aborted the video playback.';
                    break;
                case e.target.error.MEDIA_ERR_NETWORK:
                    errorMessage.textContent = 'A network error caused the video download to fail.';
                    break;
                case e.target.error.MEDIA_ERR_DECODE:
                    errorMessage.textContent = 'The video playback was aborted due to a corruption problem or because the video used features your browser did not support.';
                    break;
                case e.target.error.MEDIA_ERR_SRC_NOT_SUPPORTED:
                    errorMessage.textContent = 'The video format is not supported by your browser.';
                    break;
                default:
                    errorMessage.textContent = 'An unknown error occurred.';
                    break;
            }
            
            // Append error message after video container
            videoContainer.parentNode.insertBefore(errorMessage, videoContainer.nextSibling);
        });
    }
    
    // Check status of the video periodically if still processing
    if (videoStatus !== 'completed' && videoStatus !== 'failed') {
        console.log('Video still processing, starting status polling');
        const pollInterval = setInterval(function() {
            fetch(`/api/videos/${videoSlug}/status`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'completed') {
                        console.log('Video processing completed, reloading page');
                        clearInterval(pollInterval);
                        window.location.reload();
                    } else if (data.status === 'failed') {
                        console.error('Video processing failed:', data.error);
                        clearInterval(pollInterval);
                        // Show error message
                        const errorContainer = document.getElementById('video-status');
                        if (errorContainer) {
                            errorContainer.innerHTML = `<div class="alert alert-danger">Processing failed: ${data.error || 'Unknown error'}</div>`;
                        }
                    }
                })
                .catch(error => {
                    console.error('Error checking video status:', error);
                });
        }, 5000);
    } else {
        console.log('Video already processed, no polling needed');
    }
    
    /**
     * Copy text to clipboard
     */
    function fallbackCopy(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
        } catch (err) {
            console.error('Fallback: Oops, unable to copy', err);
        }
        
        document.body.removeChild(textArea);
    }
    
    /**
     * Show copy success message
     */
    function showCopySuccess(button) {
        const originalText = button.textContent;
        button.textContent = 'Copied!';
        button.classList.add('btn-success');
        button.classList.remove('btn-primary');
        
        setTimeout(() => {
            button.textContent = originalText;
            button.classList.add('btn-primary');
            button.classList.remove('btn-success');
        }, 2000);
    }
    
    // Initialize copy button functionality
    const copyButtons = document.querySelectorAll('.copy-link-btn');
    copyButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const text = this.dataset.copyText || window.location.href;
            
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(text).then(() => {
                    showCopySuccess(this);
                }).catch(err => {
                    console.error('Could not copy text: ', err);
                    fallbackCopy(text);
                    showCopySuccess(this);
                });
            } else {
                fallbackCopy(text);
                showCopySuccess(this);
            }
        });
    });
});