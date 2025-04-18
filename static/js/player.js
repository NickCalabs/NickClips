document.addEventListener('DOMContentLoaded', function() {
    // Initialize video player
    const videoContainer = document.getElementById('video-container');
    
    if (!videoContainer) return;
    
    const videoSlug = videoContainer.dataset.slug;
    const videoStatus = videoContainer.dataset.status;
    const playerType = videoContainer.dataset.playerType || 'native';
    const videoSourceHls = videoContainer.dataset.hlsSource;
    const videoSourceMp4 = videoContainer.dataset.mp4Source;
    
    // Only initialize player if video is completed
    if (videoStatus === 'completed') {
        if (playerType === 'hls' && videoSourceHls) {
            initializeHlsPlayer(videoSourceHls);
        } else if (videoSourceMp4) {
            initializeNativePlayer(videoSourceMp4);
        }
    }
    
    /**
     * Initialize HLS.js player for adaptive streaming
     */
    function initializeHlsPlayer(sourceUrl) {
        const video = document.createElement('video');
        video.id = 'video-player';
        video.className = 'video-js vjs-default-skin vjs-big-play-centered';
        video.controls = true;
        video.autoplay = false;
        video.preload = 'auto';
        video.playsInline = true; // Better mobile support
        
        videoContainer.appendChild(video);
        
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
        const video = document.createElement('video');
        video.id = 'video-player';
        video.className = 'w-100';
        video.controls = true;
        video.autoplay = false;
        video.preload = 'auto'; // Changed from 'metadata' to 'auto' for better buffering
        video.playsInline = true; // Better mobile support
        video.crossOrigin = 'anonymous'; // Allow CORS
        video.style.maxHeight = '80vh';
        
        const source = document.createElement('source');
        source.src = sourceUrl;
        source.type = 'video/mp4';
        
        video.appendChild(source);
        videoContainer.appendChild(video);
        
        // Add buffering indicator
        const bufferingIndicator = document.createElement('div');
        bufferingIndicator.className = 'buffering-indicator d-none position-absolute top-50 start-50 translate-middle';
        bufferingIndicator.innerHTML = '<div class="spinner-border text-light" role="status"><span class="visually-hidden">Loading...</span></div>';
        videoContainer.appendChild(bufferingIndicator);
        
        // Show buffering indicator when waiting for data
        video.addEventListener('waiting', function() {
            bufferingIndicator.classList.remove('d-none');
        });
        
        // Hide buffering indicator when playing
        video.addEventListener('playing', function() {
            bufferingIndicator.classList.add('d-none');
        });
        
        // Error handling
        video.addEventListener('error', function(e) {
            console.error('Video playback error', e);
            // Try to diagnose the error
            const errorCode = video.error ? video.error.code : 'unknown';
            console.error(`Video error code: ${errorCode}`);
            
            if (videoSourceHls && !videoContainer.querySelector('.alert')) {
                console.log('Trying fallback to HLS');
                // Try HLS fallback if MP4 fails
                videoContainer.innerHTML = '';
                initializeHlsPlayer(videoSourceHls);
            } else {
                videoContainer.innerHTML += '<div class="alert alert-danger mt-3">Error playing video. Please try again later.</div>';
            }
        });
    }
    
    // Copy link to clipboard functionality
    const copyLinkBtn = document.getElementById('copy-link-btn');
    if (copyLinkBtn) {
        copyLinkBtn.addEventListener('click', function() {
            const videoUrl = window.location.href;
            
            // Use the clipboard API if available
            if (navigator.clipboard) {
                navigator.clipboard.writeText(videoUrl)
                    .then(() => {
                        showCopySuccess(copyLinkBtn);
                    })
                    .catch(err => {
                        console.error('Could not copy text: ', err);
                        fallbackCopy(videoUrl);
                    });
            } else {
                fallbackCopy(videoUrl);
            }
        });
    }
    
    // Fallback copy method using textarea
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
            const successful = document.execCommand('copy');
            if (successful) {
                showCopySuccess(copyLinkBtn);
            }
        } catch (err) {
            console.error('Fallback: Could not copy text: ', err);
        }
        
        document.body.removeChild(textArea);
    }
    
    // Show copy success message
    function showCopySuccess(button) {
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-check"></i> Copied!';
        button.classList.remove('btn-outline-secondary');
        button.classList.add('btn-success');
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.classList.remove('btn-success');
            button.classList.add('btn-outline-secondary');
        }, 2000);
    }
});
