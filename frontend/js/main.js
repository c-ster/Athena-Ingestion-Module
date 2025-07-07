document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileSelectorBtn = document.getElementById('file-selector-btn');
    const fileList = document.getElementById('file-list');
    const uploadedFilesList = document.getElementById('uploaded-files-list');
    const uploadStatusContainer = document.getElementById('upload-status-container');
    const uploadStatusList = document.getElementById('upload-status-list');

    // --- Event Listeners ---
    fileSelectorBtn.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.classList.remove('drag-over');
        handleFiles(e.dataTransfer.files);
    });

    // --- File Handling and Uploading ---
    function handleFiles(files) {
        const formData = new FormData();
        const fileStatusMap = new Map();

        // Reset and show the status UI
        uploadStatusList.innerHTML = '';
        uploadStatusContainer.style.display = 'block';

        for (const file of files) {
            formData.append('files', file);
            fileStatusMap.set(file.name, { status: 'pending' });

            const safeFilenameId = `status-${file.name.replace(/[^a-zA-Z0-9]/g, '-')}`;
            const listItem = document.createElement('li');
            listItem.id = safeFilenameId;

            const fileNameSpan = document.createElement('span');
            fileNameSpan.textContent = file.name;
            
            const statusSpan = document.createElement('span');
            statusSpan.className = 'upload-status';
            statusSpan.textContent = 'Waiting...';
            statusSpan.style.color = 'gray';

            listItem.appendChild(fileNameSpan);
            listItem.appendChild(statusSpan);
            uploadStatusList.appendChild(listItem);
        }

        // Start SSE connection before uploading
        initializeSSE(fileStatusMap);

        fetch('/api/upload/', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.detail || 'Upload failed') });
            }
            return response.json();
        })
        .then(data => {
            console.log('Upload initiated:', data.message);
        })
        .catch(error => {
            console.error('Upload initiation error:', error);
            uploadStatusList.innerHTML = `<li><span style="color:red">Failed to start upload: ${error.message}</span></li>`;
        });
    }

    function initializeSSE(fileStatusMap) {
        const eventSource = new EventSource('/api/status');
        let completedFiles = 0;

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('SSE Message:', data);

            const { filename, status, detail } = data;
            const safeFilenameId = `status-${filename.replace(/[^a-zA-Z0-9]/g, '-')}`;
            const listItem = document.getElementById(safeFilenameId);
            if (!listItem) return;

            const statusSpan = listItem.querySelector('.upload-status');
            statusSpan.textContent = status;

            if (status === 'Error') {
                statusSpan.style.color = 'red';
                statusSpan.textContent = `Error: ${detail || 'Unknown error'}`;
            } else if (status === 'Complete') {
                statusSpan.style.color = 'green';
            } else {
                statusSpan.style.color = 'orange';
            }

            // Check if all files are done
            if (status === 'Complete' || status === 'Error') {
                if (fileStatusMap.has(filename) && fileStatusMap.get(filename).status !== 'done') {
                    fileStatusMap.get(filename).status = 'done';
                    completedFiles++;
                }
            }

            if (completedFiles === fileStatusMap.size) {
                console.log('All files processed. Closing SSE connection.');
                eventSource.close();
                fetchAndRenderUploadedFiles(); // Refresh the main file list
                
                setTimeout(() => {
                    uploadStatusContainer.style.display = 'none';
                }, 5000);
            }
        };

        eventSource.onerror = (err) => {
            console.error('EventSource failed:', err);
            eventSource.close();
            uploadStatusList.innerHTML += '<li>Connection to status updates lost. Please refresh.</li>';
        };

        eventSource.onopen = () => {
            console.log('SSE connection opened.');
        };
    }

    // --- Fetch and Render Uploaded Files ---
    function fetchAndRenderUploadedFiles() {
        console.log('Fetching uploaded files...');
        fetch('/api/files/')
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Received file data:', data);
                uploadedFilesList.innerHTML = ''; // Clear the list before rendering

                if (data.files && data.files.length > 0) {
                    data.files.forEach(fileInfo => {
                        const li = document.createElement('li');

                        // Create the main row for file info and actions
                        const fileRow = document.createElement('div');
                        fileRow.className = 'file-row';

                        // File Info Div (Left Side)
                        const fileInfoDiv = document.createElement('div');
                        fileInfoDiv.className = 'file-info';
                        const fileLink = document.createElement('a');
                        fileLink.href = `/uploads/${fileInfo.filename}`;
                        fileLink.textContent = fileInfo.filename;
                        fileLink.target = '_blank';
                        fileInfoDiv.appendChild(fileLink);

                        // File Actions Div (Right Side)
                        const fileActions = document.createElement('div');
                        fileActions.className = 'file-actions';

                        if (fileInfo.translated_filename) {
                            const translatedLink = document.createElement('a');
                            translatedLink.href = `/uploads/${fileInfo.translated_filename}`;
                            translatedLink.textContent = 'Open Translated File';
                            translatedLink.className = 'btn-translate';
                            translatedLink.target = '_blank';
                            fileActions.appendChild(translatedLink);
                        }

                        // Append info and actions to the row
                        fileRow.appendChild(fileInfoDiv);
                        fileRow.appendChild(fileActions);

                        // Append the row to the list item
                        li.appendChild(fileRow);

                        // Create Metadata button and container
                        if (fileInfo.metadata) {
                            const metadataButton = document.createElement('button');
                            metadataButton.textContent = 'Show Metadata';
                            metadataButton.className = 'btn-metadata';
                            fileActions.appendChild(metadataButton); // Add button to the actions div

                            const metadataContainer = document.createElement('div');
                            metadataContainer.className = 'metadata-container';
                            const metadata = fileInfo.metadata;

                            let metadataHTML = '<h4>Metadata</h4>';
                            if (metadata.title) {
                                metadataHTML += `<div class="metadata-item"><strong>Title:</strong> ${metadata.title || 'N/A'}</div>`;
                            }
                            if (metadata.author) {
                                metadataHTML += `<div class="metadata-item"><strong>Author:</strong> ${metadata.author || 'N/A'}</div>`;
                            }
                            if (metadata.creation_date) {
                                metadataHTML += `<div class="metadata-item"><strong>Created:</strong> ${new Date(metadata.creation_date).toLocaleString()}</div>`;
                            }
                            if (metadata.abstract) {
                                metadataHTML += `<div class="metadata-item"><strong>Abstract:</strong><div class="metadata-abstract">${metadata.abstract}</div></div>`;
                            }
                            if (metadata.keywords && metadata.keywords.length > 0) {
                                metadataHTML += `<div class="metadata-item"><strong>Keywords:</strong><ul class="keywords-list">`;
                                metadata.keywords.forEach(kw => {
                                    metadataHTML += `<li>${kw}</li>`;
                                });
                                metadataHTML += `</ul></div>`;
                            }
                            
                            metadataContainer.innerHTML = metadataHTML;
                            li.appendChild(metadataContainer); // Append container to the li, below the row

                            metadataButton.addEventListener('click', () => {
                                const isHidden = metadataContainer.style.display === 'none' || metadataContainer.style.display === '';
                                metadataContainer.style.display = isHidden ? 'block' : 'none';
                                metadataButton.textContent = isHidden ? 'Hide Metadata' : 'Show Metadata';
                            });
                        }

                        uploadedFilesList.appendChild(li);
                    });
                } else {
                    console.log('No files found.');
                    uploadedFilesList.innerHTML = '<li>No files uploaded yet.</li>';
                }
            })
            .catch(error => {
                console.error('Error fetching uploaded files:', error);
                uploadedFilesList.innerHTML = '<li>Error loading files.</li>';
            });
    }

    // Initial load of uploaded files
    fetchAndRenderUploadedFiles();
});
