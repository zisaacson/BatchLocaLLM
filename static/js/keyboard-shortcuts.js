/**
 * Keyboard Shortcuts
 * 
 * Global keyboard shortcuts for the curation interface.
 */

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (event) => {
        // Ignore if user is typing in an input/textarea
        if (event.target.tagName === 'INPUT' || 
            event.target.tagName === 'TEXTAREA' || 
            event.target.tagName === 'SELECT') {
            
            // Allow Ctrl+S even in inputs
            if (event.ctrlKey && event.key === 's') {
                event.preventDefault();
                submitCurrentAnnotation();
            }
            return;
        }
        
        // Arrow keys: Navigate tasks
        if (event.key === 'ArrowLeft') {
            event.preventDefault();
            navigateTask(-1);
        } else if (event.key === 'ArrowRight') {
            event.preventDefault();
            navigateTask(1);
        }
        
        // Ctrl+S: Save annotation
        else if (event.ctrlKey && event.key === 's') {
            event.preventDefault();
            submitCurrentAnnotation();
        }
        
        // Ctrl+E: Export
        else if (event.ctrlKey && event.key === 'e') {
            event.preventDefault();
            showExportModal();
        }
        
        // Ctrl+R: Refresh
        else if (event.ctrlKey && event.key === 'r') {
            event.preventDefault();
            refresh();
        }
        
        // Escape: Close modal
        else if (event.key === 'Escape') {
            hideExportModal();
        }
    });
}

function navigateTask(direction) {
    if (tasks.length === 0) return;
    
    let newIndex = currentTaskIndex + direction;
    
    // Wrap around
    if (newIndex < 0) {
        newIndex = tasks.length - 1;
    } else if (newIndex >= tasks.length) {
        newIndex = 0;
    }
    
    selectTask(newIndex);
}

function submitCurrentAnnotation() {
    const form = document.getElementById('annotation-form');
    if (form && form.checkValidity()) {
        form.dispatchEvent(new Event('submit', { cancelable: true }));
    } else {
        showToast('Please fill in all required fields', 'warning');
    }
}

// Make function globally available
window.setupKeyboardShortcuts = setupKeyboardShortcuts;

