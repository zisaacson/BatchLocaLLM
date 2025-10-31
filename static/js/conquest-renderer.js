/**
 * Conquest Renderer
 * 
 * Schema-driven rendering engine for conquest curation UI.
 * Dynamically renders data sources and questions based on conquest schema.
 */

const ConquestRenderer = {
    /**
     * Render a complete task
     */
    renderTask(task, schema) {
        // Store current schema for template access
        this.currentSchema = schema;
        this.currentTask = task;

        // Inject custom CSS if provided
        this.injectCustomCSS(schema);

        // Update task header (with template override)
        this.renderTaskHeader(task, schema);

        // Render data sources (with template override)
        this.renderDataSources(task.data, schema.dataSources, schema.id);

        // Render LLM prediction if available
        if (task.predictions && task.predictions.length > 0) {
            this.renderLLMPrediction(task.predictions[0], schema.questions, schema.id);
        } else {
            document.getElementById('llm-prediction').style.display = 'none';
        }

        // Render annotation form
        this.renderAnnotationForm(task, schema.questions);
    },

    /**
     * Inject custom CSS for conquest type
     */
    injectCustomCSS(schema) {
        // Remove previous custom CSS
        const existingStyle = document.getElementById('conquest-custom-css');
        if (existingStyle) {
            existingStyle.remove();
        }

        // Add new custom CSS if provided
        if (schema.rendering && schema.rendering.customCSS) {
            const style = document.createElement('style');
            style.id = 'conquest-custom-css';
            style.textContent = schema.rendering.customCSS;
            document.head.appendChild(style);
        }
    },
    
    /**
     * Render task header (with template override)
     */
    renderTaskHeader(task, schema) {
        const titleEl = document.getElementById('task-title');
        const idEl = document.getElementById('task-id');
        const statusEl = document.getElementById('task-status');

        // Check for custom template
        const template = ConquestTemplates.getTemplate(schema.id);
        if (template && template.renderHeader) {
            const customHeader = template.renderHeader(task, schema);
            titleEl.innerHTML = customHeader;

            // Still update ID and status
            idEl.textContent = `#${task.id}`;
            const isAnnotated = task.annotations && task.annotations.length > 0;
            statusEl.textContent = isAnnotated ? '✅ Annotated' : '⏳ Pending';
            statusEl.className = `task-status ${isAnnotated ? 'completed' : 'pending'}`;
            return;
        }

        // Default rendering
        const title = task.data.name || task.data[schema.dataSources[0]?.id] || `Task ${task.id}`;
        titleEl.textContent = title;

        idEl.textContent = `#${task.id}`;

        const isAnnotated = task.annotations && task.annotations.length > 0;
        statusEl.textContent = isAnnotated ? '✅ Annotated' : '⏳ Pending';
        statusEl.className = `task-status ${isAnnotated ? 'completed' : 'pending'}`;
    },
    
    /**
     * Render data sources (with template override)
     */
    renderDataSources(data, dataSources, conquestType) {
        const container = document.getElementById('data-sources');
        const template = ConquestTemplates.getTemplate(conquestType);

        container.innerHTML = dataSources.map(ds => {
            const value = data[ds.id];
            if (!value) return '';

            // Try custom template first
            if (template && template.renderDataSource) {
                const customRender = template.renderDataSource(ds, value);
                if (customRender) return customRender;
            }

            // Fall back to default
            return this.renderDataSource(ds, value);
        }).filter(Boolean).join('');
    },
    
    /**
     * Render a single data source
     */
    renderDataSource(dataSource, value) {
        const displayFormat = dataSource.displayFormat || 'default';
        
        switch (displayFormat) {
            case 'header':
                return `
                    <div class="data-source data-source-header">
                        <div class="data-source-label">${dataSource.name}</div>
                        <div class="data-source-value" style="font-size: 1.25rem; font-weight: 600;">
                            ${this.escapeHtml(value)}
                        </div>
                    </div>
                `;
            
            case 'list':
                return `
                    <div class="data-source data-source-list">
                        <div class="data-source-label">${dataSource.name}</div>
                        <div class="data-source-value">
                            ${this.renderList(value)}
                        </div>
                    </div>
                `;
            
            case 'collapsible':
                return `
                    <details class="data-source data-source-collapsible">
                        <summary class="data-source-label" style="cursor: pointer;">
                            ${dataSource.name} ▼
                        </summary>
                        <div class="data-source-value" style="margin-top: 0.5rem; white-space: pre-wrap;">
                            ${this.escapeHtml(value)}
                        </div>
                    </details>
                `;
            
            default:
                return `
                    <div class="data-source">
                        <div class="data-source-label">${dataSource.name}</div>
                        <div class="data-source-value">${this.escapeHtml(value)}</div>
                    </div>
                `;
        }
    },
    
    /**
     * Render a list (array or object)
     */
    renderList(value) {
        if (Array.isArray(value)) {
            return `<ul style="margin-left: 1rem;">${value.map(item => 
                `<li>${this.escapeHtml(typeof item === 'object' ? JSON.stringify(item) : item)}</li>`
            ).join('')}</ul>`;
        } else if (typeof value === 'object') {
            return `<ul style="margin-left: 1rem;">${Object.entries(value).map(([k, v]) => 
                `<li><strong>${k}:</strong> ${this.escapeHtml(v)}</li>`
            ).join('')}</ul>`;
        } else {
            return this.escapeHtml(value);
        }
    },
    
    /**
     * Render LLM prediction (with template override)
     */
    renderLLMPrediction(prediction, questions, conquestType) {
        const container = document.getElementById('llm-prediction');
        const answersContainer = document.getElementById('llm-answers');

        container.style.display = 'block';

        const result = prediction.result || {};
        const template = ConquestTemplates.getTemplate(conquestType);

        answersContainer.innerHTML = questions.map(q => {
            const value = result[q.id];
            if (!value) return '';

            // Try custom template first
            if (template && template.renderAnswer) {
                const customRender = template.renderAnswer(q, value);
                if (customRender) return customRender;
            }

            // Default rendering
            return `
                <div class="answer-item">
                    <div class="answer-label">${q.text}</div>
                    <div class="answer-value">${this.escapeHtml(value)}</div>
                </div>
            `;
        }).filter(Boolean).join('');
    },
    
    /**
     * Render annotation form
     */
    renderAnnotationForm(task, questions) {
        const form = document.getElementById('annotation-form');
        
        // Get existing annotation if available
        const existingAnnotation = task.annotations && task.annotations.length > 0
            ? task.annotations[0].result[0] || {}
            : {};
        
        form.innerHTML = questions.map(q => {
            return this.renderQuestion(q, existingAnnotation[q.id]);
        }).join('');
    },
    
    /**
     * Render a single question
     */
    renderQuestion(question, existingValue) {
        const value = existingValue || '';
        
        switch (question.type) {
            case 'choice':
            case 'rating':
            case 'boolean':
                return `
                    <div class="form-group">
                        <label for="q-${question.id}">
                            ${question.text}
                            ${question.required ? '<span style="color: var(--error);">*</span>' : ''}
                        </label>
                        ${question.helpText ? `<div class="help-text" style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem; white-space: pre-line;">${this.escapeHtml(question.helpText)}</div>` : ''}
                        <select id="q-${question.id}" name="${question.id}" class="form-control" ${question.required ? 'required' : ''}>
                            <option value="">Select...</option>
                            ${(question.options || []).map(opt => 
                                `<option value="${opt}" ${value === opt ? 'selected' : ''}>${opt}</option>`
                            ).join('')}
                        </select>
                    </div>
                `;
            
            case 'text':
                return `
                    <div class="form-group">
                        <label for="q-${question.id}">
                            ${question.text}
                            ${question.required ? '<span style="color: var(--error);">*</span>' : ''}
                        </label>
                        ${question.helpText ? `<div class="help-text" style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem;">${this.escapeHtml(question.helpText)}</div>` : ''}
                        <textarea id="q-${question.id}" name="${question.id}" class="form-control" rows="4" ${question.required ? 'required' : ''}>${this.escapeHtml(value)}</textarea>
                    </div>
                `;
            
            default:
                return `
                    <div class="form-group">
                        <label for="q-${question.id}">
                            ${question.text}
                            ${question.required ? '<span style="color: var(--error);">*</span>' : ''}
                        </label>
                        ${question.helpText ? `<div class="help-text" style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem;">${this.escapeHtml(question.helpText)}</div>` : ''}
                        <input type="text" id="q-${question.id}" name="${question.id}" class="form-control" value="${this.escapeHtml(value)}" ${question.required ? 'required' : ''}>
                    </div>
                `;
        }
    },
    
    /**
     * Get form data as object
     */
    getFormData() {
        const form = document.getElementById('annotation-form');
        const formData = new FormData(form);
        const data = {};
        
        for (const [key, value] of formData.entries()) {
            data[key] = value;
        }
        
        return data;
    },
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (typeof text !== 'string') {
            text = String(text);
        }
        
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

/**
 * Copy LLM answers to annotation form
 */
function copyLLMAnswers() {
    if (!currentTask || !currentTask.predictions || currentTask.predictions.length === 0) {
        showToast('No LLM prediction available', 'warning');
        return;
    }
    
    const prediction = currentTask.predictions[0].result || {};
    
    // Fill form with LLM answers
    for (const [key, value] of Object.entries(prediction)) {
        const input = document.getElementById(`q-${key}`);
        if (input) {
            input.value = value;
        }
    }
    
    showToast('Copied LLM answers', 'success');
}

/**
 * Submit annotation
 */
async function submitAnnotation(event) {
    event.preventDefault();
    
    if (!currentTask) {
        showToast('No task selected', 'error');
        return;
    }
    
    const formData = ConquestRenderer.getFormData();
    
    try {
        const annotation = await API.submitAnnotation(currentTask.id, formData);
        showToast('Annotation submitted!', 'success');
        
        // Move to next task
        if (currentTaskIndex < tasks.length - 1) {
            selectTask(currentTaskIndex + 1);
        } else {
            showToast('All tasks completed!', 'success');
        }
        
        // Refresh stats
        await loadStats();
    } catch (error) {
        showToast('Failed to submit annotation', 'error');
        console.error(error);
    }
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Make functions globally available
window.ConquestRenderer = ConquestRenderer;
window.copyLLMAnswers = copyLLMAnswers;
window.submitAnnotation = submitAnnotation;
window.showToast = showToast;

