/**
 * Shared parsing and utility functions for vLLM Batch Server Web Viewers
 */

/**
 * Parse evaluation JSON from LLM response
 * Handles both markdown-wrapped JSON and raw JSON
 * @param {Object} response - The response object from API
 * @returns {Object|null} - Parsed evaluation object or null if parsing fails
 */
function parseEvaluation(response) {
    try {
        const content = response.response?.body?.choices?.[0]?.message?.content || '';
        
        // Try to extract JSON from markdown code block first
        const jsonMatch = content.match(/```json\s*([\s\S]*?)\s*```/);
        if (jsonMatch) {
            return JSON.parse(jsonMatch[1]);
        }
        
        // Try to extract raw JSON
        const rawJsonMatch = content.match(/\{[\s\S]*\}/);
        if (rawJsonMatch) {
            return JSON.parse(rawJsonMatch[0]);
        }
        
        return null;
    } catch (e) {
        console.error('Failed to parse evaluation:', e);
        return null;
    }
}

/**
 * Extract recommendation from response
 * @param {Object} response - The response object from API
 * @returns {string} - Recommendation text or 'N/A'
 */
function extractRecommendation(response) {
    const evaluation = parseEvaluation(response);
    return evaluation?.recommendation || 'N/A';
}

/**
 * Extract candidate name from batch request
 * Looks for **Candidate:** pattern in user message
 * @param {Object} candidate - The candidate object from batch file
 * @returns {string} - Candidate name or ID
 */
function extractCandidateName(candidate) {
    try {
        const messages = candidate.body?.messages || [];
        const userMsg = messages.find(m => m.role === 'user');
        
        if (userMsg && userMsg.content) {
            // Look for **Candidate:** pattern
            const nameMatch = userMsg.content.match(/\*\*Candidate:\*\*\s*([^\n]+)/);
            if (nameMatch) {
                const name = nameMatch[1].trim();
                
                // Also try to get current role for context
                const roleMatch = userMsg.content.match(/\*\*Current Role:\*\*\s*([^\n]+)/);
                if (roleMatch) {
                    const role = roleMatch[1].trim();
                    // Shorten role if too long
                    const shortRole = role.length > 40 ? role.substring(0, 37) + '...' : role;
                    return `${name} (${shortRole})`;
                }
                
                return name;
            }
            
            // Fallback to Name: pattern
            const fallbackMatch = userMsg.content.match(/Name:\s*([^\n]+)/i);
            if (fallbackMatch) {
                return fallbackMatch[1].trim();
            }
        }
    } catch (e) {
        console.error('Failed to extract candidate name:', e);
    }
    
    // Final fallback to custom_id
    return candidate.custom_id?.substring(0, 8) || 'Unknown';
}

/**
 * Extract model name from filename
 * @param {string} filename - The result filename
 * @returns {string} - Human-readable model name
 */
function extractModelName(filename) {
    if (filename.includes('gemma3') || filename.includes('gemma-3')) return 'Gemma 3 4B';
    if (filename.includes('gemma2')) return 'Gemma 2 9B';
    if (filename.includes('llama32_3b') || filename.includes('llama-3.2-3b')) return 'Llama 3.2 3B';
    if (filename.includes('llama32_1b') || filename.includes('llama-3.2-1b')) return 'Llama 3.2 1B';
    if (filename.includes('qwen3_4b') || filename.includes('qwen-3-4b')) return 'Qwen 3 4B';
    if (filename.includes('qwen')) return 'Qwen 2.5-3B';
    if (filename.includes('olmo2_7b') || filename.includes('olmo-2-7b')) return 'OLMo 2 7B';
    if (filename.includes('olmo2_1b') || filename.includes('olmo-2-1b')) return 'OLMo 2 1B';
    if (filename.includes('olmo')) return 'OLMo 2';
    return filename;
}

/**
 * Get CSS class for recommendation badge
 * @param {string} recommendation - The recommendation text
 * @returns {string} - CSS class name
 */
function getRecommendationClass(recommendation) {
    const lower = (recommendation || '').toLowerCase();
    if (lower.includes('strong yes')) return 'rec-strong-yes';
    if (lower.includes('yes')) return 'rec-yes';
    if (lower.includes('maybe') || lower.includes('neutral')) return 'rec-maybe';
    if (lower.includes('strong no')) return 'rec-strong-no';
    if (lower.includes('no')) return 'rec-no';
    return 'rec-maybe';
}

/**
 * Get CSS class for rating badge
 * @param {string} rating - The rating text (Great, Good, Average, Weak, None)
 * @returns {string} - CSS class name
 */
function getRatingClass(rating) {
    const normalized = (rating || '').toLowerCase();
    if (normalized === 'great') return 'rating-great';
    if (normalized === 'good') return 'rating-good';
    if (normalized === 'average') return 'rating-average';
    if (normalized === 'weak') return 'rating-weak';
    if (normalized === 'none') return 'rating-none';
    return 'rating-average';
}

/**
 * Get CSS class for model box
 * @param {string} modelName - The model name
 * @returns {string} - CSS class name
 */
function getModelClass(modelName) {
    if (modelName.includes('Gemma')) return 'model-gemma';
    if (modelName.includes('Llama')) return 'model-llama';
    if (modelName.includes('Qwen')) return 'model-qwen';
    return 'model-gemma'; // default
}

/**
 * Format evaluation criteria section as HTML
 * @param {Object} evaluation - Parsed evaluation object
 * @returns {string} - HTML string
 */
function formatCriteriaSection(evaluation) {
    if (!evaluation || !evaluation.analysis) return '';
    
    const analysis = evaluation.analysis;
    let html = '<div class="criteria-section">';
    
    // Educational Pedigree
    if (analysis.educational_pedigree) {
        const ep = analysis.educational_pedigree;
        html += `
            <div class="criteria-item">
                <span class="criteria-label">🎓 Educational Pedigree:</span>
                <span class="rating-badge ${getRatingClass(ep.rating)}">${ep.rating || 'N/A'}</span>
                ${ep.reasoning ? `<div class="criteria-reasoning">${escapeHtml(ep.reasoning)}</div>` : ''}
            </div>
        `;
    }
    
    // Company Pedigree
    if (analysis.company_pedigree) {
        const cp = analysis.company_pedigree;
        html += `
            <div class="criteria-item">
                <span class="criteria-label">🏢 Company Pedigree:</span>
                <span class="rating-badge ${getRatingClass(cp.rating)}">${cp.rating || 'N/A'}</span>
                ${cp.reasoning ? `<div class="criteria-reasoning">${escapeHtml(cp.reasoning)}</div>` : ''}
            </div>
        `;
    }
    
    // Trajectory
    if (analysis.trajectory) {
        const traj = analysis.trajectory;
        html += `
            <div class="criteria-item">
                <span class="criteria-label">📈 Trajectory:</span>
                <span class="rating-badge ${getRatingClass(traj.rating)}">${traj.rating || 'N/A'}</span>
                ${traj.reasoning ? `<div class="criteria-reasoning">${escapeHtml(traj.reasoning)}</div>` : ''}
            </div>
        `;
    }
    
    // Is Software Engineer
    if (analysis.is_software_engineer) {
        const swe = analysis.is_software_engineer;
        const sweValue = swe.value ? 'Yes' : 'No';
        const sweClass = swe.value ? 'rating-great' : 'rating-weak';
        html += `
            <div class="criteria-item">
                <span class="criteria-label">💻 Is Software Engineer:</span>
                <span class="rating-badge ${sweClass}">${sweValue}</span>
                ${swe.reasoning ? `<div class="criteria-reasoning">${escapeHtml(swe.reasoning)}</div>` : ''}
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} - Escaped HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format token usage statistics
 * @param {Object} usage - Usage object from API response
 * @returns {string} - Formatted HTML string
 */
function formatTokenStats(usage) {
    if (!usage) return '';
    
    return `
        <div class="token-stats">
            <span>📝 ${usage.prompt_tokens || 0}</span>
            <span>💬 ${usage.completion_tokens || 0}</span>
            <span>📊 ${usage.total_tokens || 0}</span>
        </div>
    `;
}

/**
 * Format number with commas
 * @param {number} num - Number to format
 * @returns {string} - Formatted number
 */
function formatNumber(num) {
    return num.toLocaleString();
}

/**
 * Debounce function for search inputs
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} - Debounced function
 */
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

/**
 * Check if two recommendations are different
 * @param {string} rec1 - First recommendation
 * @param {string} rec2 - Second recommendation
 * @returns {boolean} - True if different
 */
function recommendationsAreDifferent(rec1, rec2) {
    const normalize = (rec) => (rec || '').toLowerCase().trim();
    return normalize(rec1) !== normalize(rec2);
}

/**
 * Export data to CSV
 * @param {Array} data - Array of objects to export
 * @param {string} filename - Filename for download
 */
function exportToCSV(data, filename) {
    if (!data || data.length === 0) return;
    
    // Get headers from first object
    const headers = Object.keys(data[0]);
    
    // Build CSV content
    let csv = headers.join(',') + '\n';
    data.forEach(row => {
        csv += headers.map(header => {
            const value = row[header];
            // Escape quotes and wrap in quotes if contains comma
            const escaped = String(value).replace(/"/g, '""');
            return escaped.includes(',') ? `"${escaped}"` : escaped;
        }).join(',') + '\n';
    });
    
    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    window.URL.revokeObjectURL(url);
}

