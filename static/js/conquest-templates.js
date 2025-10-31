/**
 * Conquest Templates
 * 
 * Custom rendering templates for different conquest types.
 * Each template can override default rendering for specific conquest types.
 */

const ConquestTemplates = {
    /**
     * Candidate Evaluation Template
     */
    candidate_evaluation: {
        /**
         * Custom header rendering
         */
        renderHeader(task, schema) {
            const data = task.data;
            return `
                <div class="candidate-header">
                    <h1 style="color: white; font-size: 2rem; margin-bottom: 0.5rem;">
                        ${this.escapeHtml(data.name || 'Unknown Candidate')}
                    </h1>
                    <div style="display: flex; gap: 1rem; color: rgba(255,255,255,0.9); font-size: 1rem;">
                        <span>📍 ${this.escapeHtml(data.location || 'Unknown')}</span>
                        <span>💼 ${this.escapeHtml(data.role || 'Unknown Role')}</span>
                    </div>
                </div>
            `;
        },
        
        /**
         * Custom data source rendering
         */
        renderDataSource(dataSource, value) {
            if (dataSource.id === 'education') {
                return this.renderEducation(value);
            } else if (dataSource.id === 'work_history') {
                return this.renderWorkHistory(value);
            }
            return null; // Use default rendering
        },
        
        /**
         * Render education with timeline
         */
        renderEducation(education) {
            if (!Array.isArray(education)) return '';
            
            return `
                <div class="data-source">
                    <div class="data-source-label">🎓 Education</div>
                    <div class="timeline">
                        ${education.map(edu => `
                            <div class="timeline-item">
                                <div class="timeline-marker"></div>
                                <div class="timeline-content">
                                    <div style="font-weight: 600; color: var(--text-primary);">
                                        ${this.escapeHtml(edu.degree || edu.school)}
                                    </div>
                                    <div style="color: var(--text-secondary); font-size: 0.875rem;">
                                        ${this.escapeHtml(edu.school || '')}
                                    </div>
                                    <div style="color: var(--text-muted); font-size: 0.75rem;">
                                        ${this.escapeHtml(edu.years || edu.year || '')}
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        },
        
        /**
         * Render work history with timeline
         */
        renderWorkHistory(workHistory) {
            if (!Array.isArray(workHistory)) return '';
            
            return `
                <div class="data-source">
                    <div class="data-source-label">💼 Work History</div>
                    <div class="timeline">
                        ${workHistory.map(job => `
                            <div class="timeline-item">
                                <div class="timeline-marker"></div>
                                <div class="timeline-content">
                                    <div style="font-weight: 600; color: var(--text-primary);">
                                        ${this.escapeHtml(job.title || job.role)}
                                    </div>
                                    <div style="color: var(--text-secondary); font-size: 0.875rem;">
                                        ${this.escapeHtml(job.company || '')}
                                    </div>
                                    <div style="color: var(--text-muted); font-size: 0.75rem;">
                                        ${this.escapeHtml(job.duration || job.years || '')}
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        },
        
        /**
         * Custom answer rendering with colored badges
         */
        renderAnswer(question, value) {
            if (question.type === 'rating') {
                const ratingClass = `rating-${value.toLowerCase().replace(' ', '-')}`;
                return `
                    <div class="answer-item">
                        <div class="answer-label">${question.text}</div>
                        <div class="answer-value">
                            <span class="pedigree-rating ${ratingClass}">${this.escapeHtml(value)}</span>
                        </div>
                    </div>
                `;
            }
            return null; // Use default rendering
        },
        
        escapeHtml(text) {
            if (typeof text !== 'string') text = String(text);
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    },
    
    /**
     * Email Evaluation Template
     */
    email_evaluation: {
        renderHeader(task, schema) {
            const data = task.data;
            return `
                <div class="email-header" style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); padding: 1.5rem; border-radius: 0.75rem; margin-bottom: 1rem;">
                    <div style="color: rgba(255,255,255,0.8); font-size: 0.875rem; margin-bottom: 0.5rem;">
                        From: ${this.escapeHtml(data.from || 'Unknown')}
                    </div>
                    <h1 style="color: white; font-size: 1.5rem; margin-bottom: 0.5rem;">
                        ${this.escapeHtml(data.subject || 'No Subject')}
                    </h1>
                    <div style="color: rgba(255,255,255,0.8); font-size: 0.875rem;">
                        To: ${this.escapeHtml(data.to || 'Unknown')}
                    </div>
                </div>
            `;
        },
        
        renderDataSource(dataSource, value) {
            if (dataSource.id === 'email_body') {
                return `
                    <div class="data-source email-body-container">
                        <div class="data-source-label">📧 Email Content</div>
                        <div class="email-body" style="background: var(--bg-tertiary); padding: 1rem; border-radius: 0.5rem; white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 0.875rem; line-height: 1.6;">
                            ${this.escapeHtml(value)}
                        </div>
                    </div>
                `;
            }
            return null;
        },
        
        escapeHtml(text) {
            if (typeof text !== 'string') text = String(text);
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    },
    
    /**
     * Report Evaluation Template
     */
    report_evaluation: {
        renderHeader(task, schema) {
            const data = task.data;
            return `
                <div class="report-header" style="background: linear-gradient(135deg, #10b981, #059669); padding: 1.5rem; border-radius: 0.75rem; margin-bottom: 1rem;">
                    <div style="color: rgba(255,255,255,0.8); font-size: 0.875rem; margin-bottom: 0.5rem;">
                        ${this.escapeHtml(data.report_type || 'Report')} • ${this.escapeHtml(data.date || '')}
                    </div>
                    <h1 style="color: white; font-size: 1.75rem; margin-bottom: 0.5rem;">
                        ${this.escapeHtml(data.title || 'Untitled Report')}
                    </h1>
                    <div style="color: rgba(255,255,255,0.8); font-size: 0.875rem;">
                        Author: ${this.escapeHtml(data.author || 'Unknown')}
                    </div>
                </div>
            `;
        },
        
        renderDataSource(dataSource, value) {
            if (dataSource.id === 'executive_summary') {
                return `
                    <div class="data-source">
                        <div class="data-source-label">📊 Executive Summary</div>
                        <div style="background: var(--bg-tertiary); padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #10b981;">
                            ${this.escapeHtml(value)}
                        </div>
                    </div>
                `;
            } else if (dataSource.id === 'key_findings') {
                return this.renderKeyFindings(value);
            }
            return null;
        },
        
        renderKeyFindings(findings) {
            if (!Array.isArray(findings)) return '';
            
            return `
                <div class="data-source">
                    <div class="data-source-label">🔍 Key Findings</div>
                    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                        ${findings.map((finding, idx) => `
                            <div style="background: var(--bg-tertiary); padding: 0.75rem; border-radius: 0.5rem; display: flex; gap: 0.75rem;">
                                <div style="background: #10b981; color: white; width: 1.5rem; height: 1.5rem; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 0.75rem; flex-shrink: 0;">
                                    ${idx + 1}
                                </div>
                                <div style="color: var(--text-primary); font-size: 0.875rem;">
                                    ${this.escapeHtml(finding)}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        },
        
        escapeHtml(text) {
            if (typeof text !== 'string') text = String(text);
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    },
    
    /**
     * Get template for conquest type
     */
    getTemplate(conquestType) {
        return this[conquestType] || null;
    },
    
    /**
     * Check if template has custom method
     */
    hasCustomMethod(conquestType, methodName) {
        const template = this.getTemplate(conquestType);
        return template && typeof template[methodName] === 'function';
    }
};

// Make globally available
window.ConquestTemplates = ConquestTemplates;

