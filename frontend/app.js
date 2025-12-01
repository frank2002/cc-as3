// Configuration - UPDATED BY SCRIPT
const CONFIG = {
    API_ENDPOINT: 'https://x9tt0zrzx0.execute-api.us-east-1.amazonaws.com/prod',
    API_KEY: 'LrFIQdIhETaq2ZWTjs0MjKpu3HAcA4g3tLc30hM0',
    PHOTOS_BUCKET: 'photo-album-photos-1764482476'
};

// DOM Elements
const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');
const searchResults = document.getElementById('search-results');
const fileInput = document.getElementById('file-input');
const customLabelsInput = document.getElementById('custom-labels');
const uploadBtn = document.getElementById('upload-btn');
const uploadStatus = document.getElementById('upload-status');

// Event Listeners
searchBtn.addEventListener('click', handleSearch);
searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSearch();
    }
});
uploadBtn.addEventListener('click', handleUpload);

/**
 * Handle photo search
 */
async function handleSearch() {
    const query = searchInput.value.trim();

    if (!query) {
        showMessage(searchResults, 'Please enter a search query', 'error');
        return;
    }

    // Show loading state
    searchBtn.disabled = true;
    searchResults.innerHTML = '<div class="loading"><div class="spinner"></div><p>Searching...</p></div>';

    try {
        console.log('Calling API:', `${CONFIG.API_ENDPOINT}/search?q=${query}`);

        // Call search API
        const response = await fetch(`${CONFIG.API_ENDPOINT}/search?q=${encodeURIComponent(query)}`, {
            method: 'GET',
            headers: {
                'x-api-key': CONFIG.API_KEY,
                'Content-Type': 'application/json'
            }
        });

        console.log('Response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('API Error:', errorText);
            throw new Error(`Search failed: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        console.log('Response data:', data);
        displaySearchResults(data.results || []);

    } catch (error) {
        console.error('Search error:', error);
        showMessage(searchResults, `Error: ${error.message}`, 'error');
    } finally {
        searchBtn.disabled = false;
    }
}

/**
 * Display search results
 */
function displaySearchResults(photos) {
    searchResults.innerHTML = '';

    if (!photos || photos.length === 0) {
        searchResults.innerHTML = `
            <div class="no-results">
                <p>No photos found</p>
                <p style="font-size: 0.9em; color: #999;">Try a different search query or upload some photos!</p>
            </div>
        `;
        return;
    }

    photos.forEach(photo => {
        const card = createPhotoCard(photo);
        searchResults.appendChild(card);
    });
}

/**
 * Create photo card element
 */
function createPhotoCard(photo) {
    const card = document.createElement('div');
    card.className = 'photo-card';

    const img = document.createElement('img');
    img.src = photo.url;
    img.alt = 'Photo';
    img.onerror = () => {
        img.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="250" height="200"%3E%3Crect fill="%23ddd" width="250" height="200"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="14" fill="%23999"%3EImage not found%3C/text%3E%3C/svg%3E';
    };

    const labelsDiv = document.createElement('div');
    labelsDiv.className = 'photo-labels';

    const labelsTitle = document.createElement('h3');
    labelsTitle.textContent = 'Labels:';
    labelsDiv.appendChild(labelsTitle);

    if (photo.labels && photo.labels.length > 0) {
        photo.labels.forEach(label => {
            const tag = document.createElement('span');
            tag.className = 'label-tag';
            tag.textContent = label;
            labelsDiv.appendChild(tag);
        });
    } else {
        const noLabels = document.createElement('span');
        noLabels.textContent = 'No labels';
        noLabels.style.color = '#999';
        noLabels.style.fontSize = '0.9em';
        labelsDiv.appendChild(noLabels);
    }

    card.appendChild(img);
    card.appendChild(labelsDiv);

    return card;
}

/**
 * Handle photo upload
 */
async function handleUpload() {
    const file = fileInput.files[0];

    if (!file) {
        showUploadStatus('Please select a file to upload', 'error');
        return;
    }

    // Validate file type
    if (!file.type.startsWith('image/')) {
        showUploadStatus('Please select an image file', 'error');
        return;
    }

    // Get custom labels
    const customLabels = customLabelsInput.value.trim();

    uploadBtn.disabled = true;
    showUploadStatus('Uploading photo...', 'info');

    try {
        // Generate unique filename
        const timestamp = Date.now();
        const filename = `${timestamp}-${file.name}`;

        console.log('Uploading to:', `${CONFIG.API_ENDPOINT}/photos/${filename}`);

        // Prepare headers
        const headers = {
            'x-api-key': CONFIG.API_KEY,
            'Content-Type': file.type
        };

        // Add custom labels header if provided
        if (customLabels) {
            headers['x-amz-meta-customLabels'] = customLabels;
            console.log('Custom labels:', customLabels);
        }

        // Upload to S3 via API Gateway
        const response = await fetch(`${CONFIG.API_ENDPOINT}/photos/${filename}`, {
            method: 'PUT',
            headers: headers,
            body: file
        });

        console.log('Upload response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Upload error:', errorText);
            throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
        }

        showUploadStatus('Photo uploaded successfully!', 'success');

        // Clear form
        fileInput.value = '';
        customLabelsInput.value = '';

        // Clear success message after 5 seconds
        setTimeout(() => {
            uploadStatus.style.display = 'none';
        }, 5000);

    } catch (error) {
        console.error('Upload error:', error);
        showUploadStatus(`Error: ${error.message}`, 'error');
    } finally {
        uploadBtn.disabled = false;
    }
}

/**
 * Show upload status message
 */
function showUploadStatus(message, type) {
    uploadStatus.className = `status-message ${type}`;
    uploadStatus.textContent = message;
    uploadStatus.style.display = 'block';
}

/**
 * Show message in a container
 */
function showMessage(container, message, type) {
    container.innerHTML = `
        <div class="status-message ${type}">
            ${message}
        </div>
    `;
}

// Initialize
console.log('Photo Album App Initialized');
console.log('Configuration:');
console.log('- API Endpoint:', CONFIG.API_ENDPOINT);
console.log('- Photos Bucket:', CONFIG.PHOTOS_BUCKET);
console.log('- API Key:', CONFIG.API_KEY ? 'Set' : 'NOT SET');
