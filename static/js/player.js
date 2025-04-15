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
        
        videoContainer.appendChild(video);
        
        // Check if HLS.js is supported
        if (Hls.isSupported()) {
            const hls = new Hls({
                debug: false,
                enableWorker: true,
                lowLatencyMode: true,
                backBufferLength: 90
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
                            hls.destroy();
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
        video.preload = 'metadata';
        video.style.maxHeight = '80vh';
        
        const source = document.createElement('source');
        source.src = sourceUrl;
        source.type = 'video/mp4';
        
        video.appendChild(source);
        videoContainer.appendChild(video);
        
        // Error handling
        video.addEventListener('error', function() {
            console.error('Video playback error');
            videoContainer.innerHTML += '<div class="alert alert-danger mt-3">Error playing video. Please try again later.</div>';
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
