// JavaScript for the review dashboard
let currentBlockId = null;
let blocks = [];

// DOM elements
const blockList = document.getElementById('blockList');
const refreshBtn = document.getElementById('refreshBtn');
const exportBtn = document.getElementById('exportBtn');
const exportFormat = document.getElementById('exportFormat');
const reviewModal = document.getElementById('reviewModal');
const closeModal = document.querySelector('.close');
const blockContent = document.getElementById('blockContent');
const reviewStatus = document.getElementById('reviewStatus');
const reviewerName = document.getElementById('reviewerName');
const reviewNotes = document.getElementById('reviewNotes');
const saveReview = document.getElementById('saveReview');

// Event listeners
refreshBtn.addEventListener('click', loadBlocks);
exportBtn.addEventListener('click', exportApproved);
closeModal.addEventListener('click', () => {
    reviewModal.style.display = 'none';
});
saveReview.addEventListener('click', saveCurrentReview);

// Close modal when clicking outside of it
window.addEventListener('click', (event) => {
    if (event.target === reviewModal) {
        reviewModal.style.display = 'none';
    }
});

// Load all blocks on page load
document.addEventListener('DOMContentLoaded', loadBlocks);

// Function to load blocks from the backend
async function loadBlocks() {
    try {
        const response = await fetch('/api/blocks');
        blocks = await response.json();
        renderBlocks();
    } catch (error) {
        console.error('Error loading blocks:', error);
        alert('Error loading blocks. Please check the console for details.');
    }
}

// Function to render blocks in the UI
function renderBlocks() {
    blockList.innerHTML = '';
    
    blocks.forEach(block => {
        const blockCard = document.createElement('div');
        blockCard.className = 'block-card';
        blockCard.innerHTML = `
            <span class="block-type">${block.type}</span>
            <div class="block-content">${block.content.substring(0, 150)}${block.content.length > 150 ? '...' : ''}</div>
            <span class="block-status status-${block.review_status}">${block.review_status}</span>
        `;
        
        blockCard.addEventListener('click', () => openReviewModal(block));
        blockList.appendChild(blockCard);
    });
}

// Function to open the review modal with block details
function openReviewModal(block) {
    currentBlockId = block.id;
    
    blockContent.innerHTML = `
        <h3>Page ${block.page || 'Unknown'}</h3>
        <p><strong>Type:</strong> ${block.type}</p>
        <div><strong>Content:</strong></div>
        <div style="margin-top: 10px; padding: 10px; background-color: #f8f9fa; border-radius: 4px;">${block.content}</div>
    `;
    
    reviewStatus.value = block.review_status || 'pending';
    reviewerName.value = block.reviewer || '';
    reviewNotes.value = block.notes || '';
    
    reviewModal.style.display = 'block';
}

// Function to save the current review
async function saveCurrentReview() {
    if (!currentBlockId) {
        alert('No block is currently being reviewed.');
        return;
    }
    
    const reviewData = {
        review_status: reviewStatus.value,
        reviewer: reviewerName.value,
        notes: reviewNotes.value,
        updated_at: new Date().toISOString()
    };
    
    try {
        const response = await fetch(`/api/blocks/${currentBlockId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(reviewData)
        });
        
        if (response.ok) {
            // Update the local block data
            const blockIndex = blocks.findIndex(b => b.id === currentBlockId);
            if (blockIndex !== -1) {
                blocks[blockIndex].review_status = reviewData.review_status;
                blocks[blockIndex].reviewer = reviewData.reviewer;
                blocks[blockIndex].notes = reviewData.notes;
            }
            
            // Update the UI
            renderBlocks();
            
            // Close the modal
            reviewModal.style.display = 'none';
            
            alert('Review saved successfully!');
        } else {
            console.error('Error saving review:', await response.text());
            alert('Error saving review. Please check the console for details.');
        }
    } catch (error) {
        console.error('Error saving review:', error);
        alert('Error saving review. Please check the console for details.');
    }
}

// Function to export approved content
async function exportApproved() {
    const format = exportFormat.value;
    
    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ format: format })
        });
        
        if (response.ok) {
            const content = await response.text();
            
            // Create a download link
            const blob = new Blob([content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `approved_content.${format}`;
            document.body.appendChild(a);
            a.click();
            
            // Clean up
            setTimeout(() => {
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }, 100);
        } else {
            console.error('Error exporting:', await response.text());
            alert('Error exporting content. Please check the console for details.');
        }
    } catch (error) {
        console.error('Error exporting:', error);
        alert('Error exporting content. Please check the console for details.');
    }
}