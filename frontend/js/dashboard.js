// Dashboard functionality for AI Video Gallery
const API_BASE_URL = 'http://localhost:5000/api';

// Global variables
let currentPage = 1;
let totalPages = 1;
let videos = [];
let socket = null;
let filters = {
    status: '',
    sort: 'created_at_desc',
    search: ''
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    checkAuthentication();
    initializeDashboard();
    initializeWebSocket();
    loadStatistics();
    loadVideos();
});

function checkAuthentication() {
    const user = localStorage.getItem('user');
    if (!user) {
        window.location.href = 'index.html';
    }
}

function initializeDashboard() {
    // Set up event listeners
    document.getElementById('statusFilter').addEventListener('change', handleFilterChange);
    document.getElementById('sortBy').addEventListener('change', handleSortChange);
    document.getElementById('searchQuery').addEventListener('input', debounce(handleSearchChange, 500));
}

function initializeWebSocket() {
    // Connect to WebSocket for real-time updates
    socket = io(API_BASE_URL.replace('/api', ''));
    
    socket.on('connect', () => {
        console.log('Connected to WebSocket');
        
        // Join user room
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        if (user.id) {
            socket.emit('join_user_room', { user_id: user.id });
        }
    });

    // Listen for processing updates
    socket.on('processing_update', (data) => {
        updateVideoStatus(data);
        if (data.status === 'completed' || data.status === 'failed') {
            loadStatistics(); // Refresh stats
        }
    });

    socket.on('upload_complete', (data) => {
        // Add new video to the grid
        if (currentPage === 1) {
            loadVideos(); // Reload to show new video
        }
        loadStatistics();
    });
}

async function loadStatistics() {
    try {
        const response = await fetch(`${API_BASE_URL}/videos`, {
            credentials: 'include'
        });
        
        if (response.ok) {
            const data = await response.json();
            updateStatistics(data.videos);
        }
    } catch (error) {
        console.error('Failed to load statistics:', error);
    }
}

function updateStatistics(videos) {
    let stats = {
        total: videos.length,
        processing: 0,
        completed: 0,
        totalSize: 0
    };
    
    videos.forEach(video => {
        if (video.status === 'processing') stats.processing++;
        if (video.status === 'completed') stats.completed++;
        stats.totalSize += video.file_size || 0;
    });
    
    // Update UI
    document.getElementById('totalVideos').textContent = stats.total;
    document.getElementById('processingVideos').textContent = stats.processing;
    document.getElementById('completedVideos').textContent = stats.completed;
    document.getElementById('totalSize').textContent = formatFileSize(stats.totalSize);
}

async function loadVideos(page = 1) {
    showLoading(true);
    
    try {
        const params = new URLSearchParams({
            page: page,
            per_page: 12
        });
        
        const response = await fetch(`${API_BASE_URL}/videos?${params}`, {
            credentials: 'include'
        });
        
        if (response.ok) {
            const data = await response.json();
            videos = data.videos;
            currentPage = data.pagination.page;
            totalPages = data.pagination.pages;
            
            applyFiltersAndSort();
            renderPagination();
        } else {
            showError('Failed to load videos');
        }
    } catch (error) {
        console.error('Failed to load videos:', error);
        showError('Network error. Please try again.');
    } finally {
        showLoading(false);
    }
}

function applyFiltersAndSort() {
    let filteredVideos = [...videos];
    
    // Apply status filter
    if (filters.status) {
        filteredVideos = filteredVideos.filter(video => video.status === filters.status);
    }
    
    // Apply search filter
    if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        filteredVideos = filteredVideos.filter(video => 
            video.title.toLowerCase().includes(searchLower) ||
            (video.description && video.description.toLowerCase().includes(searchLower)) ||
            (video.tags && video.tags.some(tag => tag.toLowerCase().includes(searchLower)))
        );
    }
    
    // Apply sorting
    filteredVideos.sort((a, b) => {
        switch (filters.sort) {
            case 'created_at_desc':
                return new Date(b.created_at) - new Date(a.created_at);
            case 'created_at_asc':
                return new Date(a.created_at) - new Date(b.created_at);
            case 'title_asc':
                return a.title.localeCompare(b.title);
            case 'title_desc':
                return b.title.localeCompare(a.title);
            case 'size_desc':
                return (b.file_size || 0) - (a.file_size || 0);
            default:
                return 0;
        }
    });
    
    displayVideos(filteredVideos);
}

function displayVideos(videosToDisplay) {
    const grid = document.getElementById('videoGrid');
    const emptyState = document.getElementById('emptyState');
    
    if (videosToDisplay.length === 0) {
        grid.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }
    
    emptyState.style.display = 'none';
    grid.innerHTML = '';
    
    videosToDisplay.forEach(video => {
        const card = createVideoCard(video);
        grid.appendChild(card);
    });
}

function createVideoCard(video) {
    const card = document.createElement('div');
    card.className = 'video-card';
    card.setAttribute('data-video-id', video.id);
    
    const thumbnailUrl = video.thumbnail_url || 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="320" height="180" viewBox="0 0 320 180"%3E%3Crect width="320" height="180" fill="%23cccccc"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="Arial" font-size="20" fill="%23666666"%3ENo Thumbnail%3C/text%3E%3C/svg%3E';
    
    const videoTags = video.tags && video.tags.length > 0 
        ? video.tags.slice(0, 3).map(tag => `<span class="video-tag">${tag}</span>`).join('')
        : '';
    
    card.innerHTML = `
        <img src="${thumbnailUrl}" alt="${video.title}" class="video-thumbnail">
        <div class="video-info">
            <div class="video-title" title="${video.title}">${video.title}</div>
            <div class="video-meta">
                ${formatDuration(video.duration)} • ${formatFileSize(video.file_size)}
                ${video.created_at ? ' • ' + formatDate(video.created_at) : ''}
            </div>
            ${videoTags ? `<div class="video-tags">${videoTags}</div>` : ''}
            <span class="video-status status-${video.status}">${formatStatus(video.status)}</span>
        </div>
    `;
    
    card.addEventListener('click', () => viewVideo(video));
    
    return card;
}

function viewVideo(video) {
    // For now, just show video details in a modal or redirect
    // In a full implementation, this would open a video player
    if (video.status === 'completed') {
        // Could open a modal with video player
        alert(`Video: ${video.title}\nStatus: ${video.status}\nDuration: ${formatDuration(video.duration)}`);
    } else {
        showNotification(`This video is currently ${video.status}`, 'info');
    }
}

function updateVideoStatus(data) {
    // Update video card status in real-time
    const card = document.querySelector(`[data-video-id="${data.video_id}"]`);
    if (card) {
        const statusBadge = card.querySelector('.video-status');
        if (statusBadge) {
            statusBadge.textContent = formatStatus(data.status);
            statusBadge.className = `video-status status-${data.status}`;
        }
    }
    
    // Update statistics if needed
    if (data.status === 'completed' || data.status === 'failed') {
        loadStatistics();
    }
}

function renderPagination() {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';
    
    if (totalPages <= 1) return;
    
    // Previous button
    if (currentPage > 1) {
        const prevBtn = createPageButton('Previous', currentPage - 1);
        pagination.appendChild(prevBtn);
    }
    
    // Page numbers
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    if (startPage > 1) {
        pagination.appendChild(createPageButton('1', 1));
        if (startPage > 2) {
            const dots = document.createElement('span');
            dots.textContent = '...';
            dots.style.padding = '0 0.5rem';
            pagination.appendChild(dots);
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const btn = createPageButton(i.toString(), i);
        if (i === currentPage) {
            btn.classList.add('active');
        }
        pagination.appendChild(btn);
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const dots = document.createElement('span');
            dots.textContent = '...';
            dots.style.padding = '0 0.5rem';
            pagination.appendChild(dots);
        }
        pagination.appendChild(createPageButton(totalPages.toString(), totalPages));
    }
    
    // Next button
    if (currentPage < totalPages) {
        const nextBtn = createPageButton('Next', currentPage + 1);
        pagination.appendChild(nextBtn);
    }
}

function createPageButton(text, page) {
    const btn = document.createElement('button');
    btn.className = 'page-btn';
    btn.textContent = text;
    btn.addEventListener('click', () => loadVideos(page));
    return btn;
}

// Event handlers
function handleFilterChange(e) {
    filters.status = e.target.value;
    applyFiltersAndSort();
}

function handleSortChange(e) {
    filters.sort = e.target.value;
    applyFiltersAndSort();
}

function handleSearchChange(e) {
    filters.search = e.target.value;
    applyFiltersAndSort();
}

// Utility functions
function showLoading(show) {
    document.getElementById('loadingSpinner').style.display = show ? 'block' : 'none';
    document.getElementById('videoGrid').style.opacity = show ? '0.5' : '1';
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 Bytes';
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

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    
    return date.toLocaleDateString();
}

function formatStatus(status) {
    const statusMap = {
        'uploaded': 'Uploaded',
        'processing': 'Processing',
        'completed': 'Ready',
        'failed': 'Failed'
    };
    return statusMap[status] || status;
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 2rem;
        border-radius: 5px;
        color: white;
        font-weight: bold;
        z-index: 3000;
        animation: slideIn 0.3s ease;
        background-color: ${type === 'success' ? '#4caf50' : type === 'error' ? '#f44336' : '#2196f3'};
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}