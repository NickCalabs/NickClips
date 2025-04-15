document.addEventListener('DOMContentLoaded', function() {
    // File upload form handling
    const uploadForm = document.getElementById('upload-form');
    const uploadProgress = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const uploadStatus = document.getElementById('upload-status');
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(uploadForm);
            
            // Check if a file was selected
            const fileInput = document.getElementById('file-input');
            if (fileInput.files.length === 0) {
                showAlert('Please select a file to upload', 'danger');
                return;
            }
            
            // Show progress bar
            uploadProgress.classList.remove('d-none');
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', 0);
            uploadStatus.textContent = 'Uploading...';
            
            // Upload the file
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/upload', true);
            
            xhr.upload.onprogress = function(e) {
                if (e.lengthComputable) {
                    const percent = Math.round((e.loaded / e.total) * 100);
                    progressBar.style.width = percent + '%';
                    progressBar.setAttribute('aria-valuenow', percent);
                    uploadStatus.textContent = `Uploading... ${percent}%`;
                }
            };
            
            xhr.onload = function() {
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        uploadStatus.textContent = 'Upload complete! Processing video...';
                        progressBar.classList.remove('progress-bar-animated');
                        progressBar.classList.add('bg-success');
                        
                        // Redirect to video page
                        setTimeout(function() {
                            window.location.href = response.redirect;
                        }, 1000);
                    } catch (e) {
                        showAlert('Error parsing server response', 'danger');
                    }
                } else {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        showAlert(response.error || 'Upload failed', 'danger');
                    } catch (e) {
                        showAlert('Upload failed', 'danger');
                    }
                    uploadProgress.classList.add('d-none');
                }
            };
            
            xhr.onerror = function() {
                showAlert('Upload failed. Please try again.', 'danger');
                uploadProgress.classList.add('d-none');
            };
            
            xhr.send(formData);
        });
    }
    
    // URL download form handling
    const downloadForm = document.getElementById('download-form');
    const downloadStatus = document.getElementById('download-status');
    
    if (downloadForm) {
        downloadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const urlInput = document.getElementById('url-input');
            const url = urlInput.value.trim();
            
            if (!url) {
                showAlert('Please enter a valid URL', 'danger');
                return;
            }
            
            // Show loading state
            const submitBtn = downloadForm.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            
            // Send the request
            fetch('/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: url })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    showAlert(data.error, 'danger');
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Download';
                } else {
                    downloadStatus.textContent = 'Download started! You will be redirected to the video page...';
                    downloadStatus.classList.remove('d-none');
                    
                    // Redirect to video page
                    setTimeout(function() {
                        window.location.href = data.redirect;
                    }, 1000);
                }
            })
            .catch(error => {
                showAlert('Failed to process the URL. Please try again.', 'danger');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Download';
            });
        });
    }
    
    // Video status polling (for video page)
    const videoStatus = document.getElementById('video-status');
    const videoContainer = document.getElementById('video-container');
    const videoSlug = videoContainer ? videoContainer.dataset.slug : null;
    
    if (videoSlug && videoStatus) {
        // Poll for video status updates
        let pollInterval = setInterval(function() {
            fetch(`/api/video/${videoSlug}`)
                .then(response => response.json())
                .then(data => {
                    updateVideoStatus(data);
                    
                    // If video is completed, stop polling and update UI
                    if (data.status === 'completed') {
                        clearInterval(pollInterval);
                        
                        // Update UI without reloading the page
                        videoStatus.innerHTML = `<div class="alert alert-success">Processing complete!</div>`;
                        
                        // Update the video container with player
                        const videoContainer = document.getElementById('video-container');
                        if (videoContainer) {
                            // Set the necessary data attributes
                            videoContainer.dataset.status = 'completed';
                            videoContainer.dataset.playerType = data.hls_path ? 'hls' : 'native';
                            
                            if (data.hls_path) {
                                videoContainer.dataset.hlsSource = `/uploads/${data.hls_path}`;
                            }
                            
                            if (data.processed_path) {
                                videoContainer.dataset.mp4Source = `/uploads/${data.processed_path}`;
                            }
                            
                            // Initialize the appropriate player
                            if (typeof initializeHlsPlayer === 'function' && data.hls_path) {
                                initializeHlsPlayer(`/uploads/${data.hls_path}`);
                            } else if (typeof initializeNativePlayer === 'function' && data.processed_path) {
                                initializeNativePlayer(`/uploads/${data.processed_path}`);
                            } else {
                                // If player.js functions aren't available, reload the page as fallback
                                location.reload();
                            }
                        }
                    } else if (data.status === 'failed') {
                        clearInterval(pollInterval);
                        videoStatus.innerHTML = `<div class="alert alert-danger">Processing failed: ${data.error || 'Unknown error'}</div>`;
                    }
                })
                .catch(error => {
                    console.error('Error polling for video status:', error);
                });
        }, 5000); // Poll every 5 seconds
    }
    
    // Dashboard video management
    const deleteButtons = document.querySelectorAll('.delete-video');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (confirm('Are you sure you want to delete this video? This action cannot be undone.')) {
                const videoSlug = this.dataset.slug;
                
                fetch(`/api/video/${videoSlug}/delete`, {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const videoCard = this.closest('.video-card');
                        videoCard.remove();
                        showAlert('Video deleted successfully', 'success');
                    } else {
                        showAlert('Failed to delete video', 'danger');
                    }
                })
                .catch(error => {
                    showAlert('Error deleting video', 'danger');
                });
            }
        });
    });
    
    // Edit video details functionality for dashboard
    const editButtons = document.querySelectorAll('.edit-video');
    editButtons.forEach(button => {
        button.addEventListener('click', function() {
            const videoCard = this.closest('.video-card');
            const videoSlug = this.dataset.slug;
            const titleElement = videoCard.querySelector('.video-title');
            const descriptionElement = videoCard.querySelector('.video-description');
            
            const currentTitle = titleElement.textContent;
            const currentDescription = descriptionElement.textContent || '';
            
            // Replace title with input
            titleElement.innerHTML = `<input type="text" class="form-control edit-title" value="${currentTitle}">`;
            
            // Replace description with textarea
            descriptionElement.innerHTML = `<textarea class="form-control edit-description">${currentDescription}</textarea>`;
            
            // Replace edit button with save button
            this.innerHTML = '<i class="fas fa-save"></i> Save';
            this.classList.remove('edit-video');
            this.classList.add('save-video');
            
            // Add event listener to save button
            this.addEventListener('click', function saveHandler() {
                const newTitle = videoCard.querySelector('.edit-title').value.trim();
                const newDescription = videoCard.querySelector('.edit-description').value.trim();
                
                fetch(`/api/video/${videoSlug}/update`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        title: newTitle,
                        description: newDescription
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Restore elements
                        titleElement.textContent = newTitle;
                        descriptionElement.textContent = newDescription;
                        
                        // Restore edit button
                        this.innerHTML = '<i class="fas fa-edit"></i> Edit';
                        this.classList.remove('save-video');
                        this.classList.add('edit-video');
                        
                        // Remove the save handler
                        this.removeEventListener('click', saveHandler);
                        
                        showAlert('Video updated successfully', 'success');
                    } else {
                        showAlert('Failed to update video', 'danger');
                    }
                })
                .catch(error => {
                    showAlert('Error updating video', 'danger');
                });
            });
        });
    });
    
    // Helper function to update video status display
    function updateVideoStatus(video) {
        if (!videoStatus) return;
        
        let statusHtml = '';
        
        switch (video.status) {
            case 'pending':
                statusHtml = '<div class="alert alert-info">Your video is pending processing...</div>';
                break;
            case 'downloading':
                statusHtml = '<div class="alert alert-info">Downloading video from source...</div>';
                break;
            case 'processing':
                statusHtml = `
                    <div class="alert alert-info">
                        <div class="d-flex align-items-center">
                            <strong>Processing your video...</strong>
                            <div class="spinner-border ms-auto" role="status" aria-hidden="true"></div>
                        </div>
                    </div>
                `;
                break;
            case 'completed':
                statusHtml = '<div class="alert alert-success">Processing complete!</div>';
                break;
            case 'failed':
                statusHtml = `<div class="alert alert-danger">Processing failed: ${video.error || 'Unknown error'}</div>`;
                break;
            default:
                statusHtml = '<div class="alert alert-secondary">Unknown status</div>';
        }
        
        videoStatus.innerHTML = statusHtml;
    }
    
    // Helper function to show alerts
    function showAlert(message, type) {
        const alertsContainer = document.getElementById('alerts-container');
        if (!alertsContainer) return;
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.role = 'alert';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertsContainer.appendChild(alert);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => {
                alertsContainer.removeChild(alert);
            }, 150);
        }, 5000);
    }
});
