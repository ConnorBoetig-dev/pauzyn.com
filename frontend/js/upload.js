// Upload functionality for AI Video Gallery
const API_BASE_URL = 'http://localhost:5000/api';

// Global variables
let selectedFile = null;
let tags = [];
let socket = null;
let currentUploadId = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeUpload();
    loadRecentVideos();
    initializeWebSocket();
});

function initializeUpload() {
    const dropzone = document.getElementById('dropzone');
    const videoInput = document.getElementById('videoInput');
    const uploadForm = document.getElementById('uploadForm');
    const tagInput = document.getElementById('tagInput');

    // Dropzone events
    dropzone.addEventListener('click', () => videoInput.click());
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-over');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('drag-over');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });

    // File input change
    videoInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });

    // Form submission
    uploadForm.addEventListener('submit', handleUpload);

    // Tag input
    tagInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addTag(tagInput.value.trim());
            tagInput.value = '';
        }
    });
}

function initializeWebSocket() {
    // Connect to WebSocket for real-time updates
    socket = io(API_BASE_URL.replace('/api', ''));
    
    socket.on('connect', () => {
        console.log('Connected to WebSocket');
        
        // Join user room if logged in
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        if (user.id) {
            socket.emit('join_user_room', { user_id: user.id });
        }
    });

    socket.on('upload_status', (data) => {
        updateUploadStatus(data);
    });

    socket.on('upload_complete', (data) => {
        handleUploadComplete(data);
    });

    socket.on('upload_error', (data) => {
        handleUploadError(data);
    });

    socket.on('processing_update', (data) => {
        updateProcessingStatus(data);
    });
}

function handleFileSelect(file) {
    // Validate file type
    const allowedTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-matroska', 'video/webm'];
    const fileExtension = file.name.split('.').pop().toLowerCase();
    const allowedExtensions = ['mp4', 'avi', 'mov', 'mkk', 'webm'];
    
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
        showError('Please select a valid video file (MP4, AVI, MOV, MKV, or WebM)');
        return;
    }

    // Check file size (500MB limit)
    const maxSize = 500 * 1024 * 1024; // 500MB
    if (file.size > maxSize) {
        showError('File size exceeds 500MB limit');
        return;
    }

    selectedFile = file;
    displayFileInfo(file);
    showUploadForm();
}

function displayFileInfo(file) {
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);
    document.getElementById('fileType').textContent = file.type || 'Unknown';
    
    // Set default title from filename
    const titleInput = document.getElementById('title');
    if (!titleInput.value) {
        titleInput.value = file.name.replace(/\.[^/.]+$/, '');
    }
}

function showUploadForm() {
    document.getElementById('dropzone').style.display = 'none';
    document.getElementById('uploadForm').style.display = 'block';
}

function cancelUpload() {
    selectedFile = null;
    tags = [];
    document.getElementById('uploadForm').reset();
    document.getElementById('uploadForm').style.display = 'none';
    document.getElementById('dropzone').style.display = 'block';
    document.getElementById('progressContainer').style.display = 'none';
    clearTags();
}

async function handleUpload(e) {
    e.preventDefault();
    
    if (!selectedFile) {
        showError('Please select a video file');
        return;
    }

    const formData = new FormData();
    formData.append('video', selectedFile);
    formData.append('title', document.getElementById('title').value || selectedFile.name);
    formData.append('description', document.getElementById('description').value);
    
    // Add tags
    tags.forEach(tag => {
        formData.append('tags[]', tag);
    });

    // Show progress
    document.getElementById('uploadForm').style.display = 'none';
    document.getElementById('progressContainer').style.display = 'block';
    updateProgress(0);
    updateUploadStatus({ message: 'Starting upload...' });

    try {
        const xhr = new XMLHttpRequest();
        
        // Track upload progress
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                updateProgress(percentComplete);
            }
        });

        xhr.addEventListener('load', function() {
            if (xhr.status === 201) {
                const response = JSON.parse(xhr.responseText);
                currentUploadId = response.video.id;
                showSuccess('Video uploaded successfully!');
                updateUploadStatus({ message: 'Processing video...' });
                // Don't reset form yet - wait for processing to complete
            } else {
                const error = JSON.parse(xhr.responseText);
                showError(error.error || 'Upload failed');
                setTimeout(() => cancelUpload(), 3000);
            }
        });

        xhr.addEventListener('error', function() {
            showError('Network error during upload');
            setTimeout(() => cancelUpload(), 3000);
        });

        // Add auth token or session cookie will be sent automatically
        xhr.open('POST', `${API_BASE_URL}/videos/upload`);
        xhr.withCredentials = true;
        xhr.send(formData);
        
    } catch (error) {
        console.error('Upload error:', error);
        showError('Failed to upload video');
        setTimeout(() => cancelUpload(), 3000);
    }
}

function updateProgress(percent) {
    const progressFill = document.getElementById('progressFill');
    progressFill.style.width = percent + '%';
    progressFill.textContent = Math.round(percent) + '%';
}

function updateUploadStatus(data) {
    const statusElement = document.getElementById('uploadStatus');
    statusElement.textContent = data.message || 'Processing...';
}

function handleUploadComplete(data) {
    updateUploadStatus({ message: 'Upload complete! Video is being processed.' });
    updateProgress(100);
    
    // Reload recent videos
    loadRecentVideos();
    
    // Reset form after delay
    setTimeout(() => {
        cancelUpload();
        showSuccess('Video uploaded and processing started!');
    }, 2000);
}

function handleUploadError(data) {
    showError(data.error || 'Upload failed');
    setTimeout(() => cancelUpload(), 3000);
}

function updateProcessingStatus(data) {
    // Update the status of a video in the recent uploads grid
    const videoCard = document.querySelector(`[data-video-id="${data.video_id}"]`);
    if (videoCard) {
        const statusBadge = videoCard.querySelector('.video-status');
        if (statusBadge) {
            statusBadge.textContent = data.status;
            statusBadge.className = `video-status status-${data.status}`;
        }
    }
}

// Tag management
function addTag(tag) {
    if (tag && !tags.includes(tag) && tags.length < 10) {
        tags.push(tag);
        renderTags();
    }
}

function removeTag(tag) {
    tags = tags.filter(t => t !== tag);
    renderTags();
}

function renderTags() {
    const container = document.getElementById('tagsContainer');
    const input = document.getElementById('tagInput');
    
    // Clear existing tags
    container.querySelectorAll('.tag').forEach(el => el.remove());
    
    // Add tags
    tags.forEach(tag => {
        const tagEl = document.createElement('div');
        tagEl.className = 'tag';
        tagEl.innerHTML = `
            ${tag}
            <span class="tag-remove" onclick="removeTag('${tag}')">&times;</span>
        `;
        container.insertBefore(tagEl, input);
    });
}

function clearTags() {
    tags = [];
    renderTags();
}

// Load recent videos
async function loadRecentVideos() {
    try {
        const response = await fetch(`${API_BASE_URL}/videos?per_page=6`, {
            credentials: 'include'
        });
        
        if (response.ok) {
            const data = await response.json();
            displayVideos(data.videos);
        }
    } catch (error) {
        console.error('Failed to load recent videos:', error);
    }
}

function displayVideos(videos) {
    const grid = document.getElementById('videoGrid');
    grid.innerHTML = '';
    
    if (videos.length === 0) {
        grid.innerHTML = '<p style="text-align: center; color: #666;">No videos uploaded yet</p>';
        return;
    }
    
    videos.forEach(video => {
        const card = createVideoCard(video);
        grid.appendChild(card);
    });
}

function createVideoCard(video) {
    const card = document.createElement('div');
    card.className = 'video-card';
    card.setAttribute('data-video-id', video.id);
    
    const thumbnailUrl = video.thumbnail_url || 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180"%3E%3Crect width="320" height="180" fill="%23cccccc"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="Arial" font-size="20" fill="%23666666"%3ENo Thumbnail%3C/text%3E%3C/svg%3E';
    
    card.innerHTML = `
        <img src="${thumbnailUrl}" alt="${video.title}" class="video-thumbnail">
        <div class="video-info">
            <div class="video-title">${video.title}</div>
            <div class="video-meta">
                ${formatDuration(video.duration)} • ${formatFileSize(video.file_size)}
            </div>
            <span class="video-status status-${video.status}">${video.status}</span>
        </div>
    `;
    
    card.addEventListener('click', () => {
        window.location.href = `dashboard.html#video-${video.id}`;
    });
    
    return card;
}

// Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    if (!seconds) return 'Unknown';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

// Make functions available globally
window.cancelUpload = cancelUpload;
window.removeTag = removeTag;