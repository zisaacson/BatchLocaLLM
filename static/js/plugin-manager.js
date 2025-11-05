/**
 * Plugin Manager - Client-side plugin system integration
 * 
 * Provides utilities for:
 * - Loading and discovering plugins
 * - Dynamically injecting plugin UI components
 * - Managing plugin state (enable/disable)
 * - Accessing plugin capabilities
 */

class PluginManager {
    constructor() {
        this.plugins = [];
        this.loadedComponents = new Map();
        this.apiBase = '';  // Use relative URLs
    }

    /**
     * Initialize plugin manager and load all plugins
     */
    async init() {
        try {
            const response = await fetch('/api/plugins');
            const data = await response.json();
            this.plugins = data.plugins;
            console.log(`✅ Loaded ${this.plugins.length} plugins`);
            return this.plugins;
        } catch (error) {
            console.error('Failed to load plugins:', error);
            return [];
        }
    }

    /**
     * Get all plugins
     */
    getPlugins() {
        return this.plugins;
    }

    /**
     * Get enabled plugins only
     */
    getEnabledPlugins() {
        return this.plugins.filter(p => p.enabled);
    }

    /**
     * Get plugins by type
     */
    async getPluginsByType(type) {
        try {
            const response = await fetch(`/api/plugins/by-type/${type}`);
            const data = await response.json();
            return data.plugins;
        } catch (error) {
            console.error(`Failed to get ${type} plugins:`, error);
            return [];
        }
    }

    /**
     * Get plugin details
     */
    async getPluginDetails(pluginId) {
        try {
            const response = await fetch(`/api/plugins/${pluginId}`);
            return await response.json();
        } catch (error) {
            console.error(`Failed to get plugin ${pluginId}:`, error);
            return null;
        }
    }

    /**
     * Enable a plugin
     */
    async enablePlugin(pluginId) {
        try {
            const response = await fetch(`/api/plugins/${pluginId}/enable`, {
                method: 'POST'
            });
            const data = await response.json();
            
            // Update local state
            const plugin = this.plugins.find(p => p.id === pluginId);
            if (plugin) {
                plugin.enabled = true;
            }
            
            return data;
        } catch (error) {
            console.error(`Failed to enable plugin ${pluginId}:`, error);
            throw error;
        }
    }

    /**
     * Disable a plugin
     */
    async disablePlugin(pluginId) {
        try {
            const response = await fetch(`/api/plugins/${pluginId}/disable`, {
                method: 'POST'
            });
            const data = await response.json();
            
            // Update local state
            const plugin = this.plugins.find(p => p.id === pluginId);
            if (plugin) {
                plugin.enabled = false;
            }
            
            return data;
        } catch (error) {
            console.error(`Failed to disable plugin ${pluginId}:`, error);
            throw error;
        }
    }

    /**
     * Get UI components from a plugin
     */
    async getUIComponents(pluginId) {
        try {
            const response = await fetch(`/api/plugins/${pluginId}/ui-components`);
            const data = await response.json();
            return data.components || [];
        } catch (error) {
            console.error(`Failed to get UI components for ${pluginId}:`, error);
            return [];
        }
    }

    /**
     * Load and inject a plugin UI component into the DOM
     * 
     * @param {string} pluginId - Plugin identifier
     * @param {string} componentId - Component identifier
     * @param {string} targetSelector - CSS selector for target element
     * @param {object} options - Component options
     */
    async loadComponent(pluginId, componentId, targetSelector, options = {}) {
        const cacheKey = `${pluginId}:${componentId}`;
        
        // Check if already loaded
        if (this.loadedComponents.has(cacheKey)) {
            console.log(`Component ${cacheKey} already loaded`);
            return this.loadedComponents.get(cacheKey);
        }

        try {
            // Get component metadata
            const components = await this.getUIComponents(pluginId);
            const component = components.find(c => c.id === componentId);
            
            if (!component) {
                throw new Error(`Component ${componentId} not found in plugin ${pluginId}`);
            }

            // Load component template
            const templatePath = component.template;
            const response = await fetch(`/${templatePath}`);
            const html = await response.text();

            // Inject into DOM
            const target = document.querySelector(targetSelector);
            if (!target) {
                throw new Error(`Target element not found: ${targetSelector}`);
            }

            target.innerHTML = html;

            // Cache the component
            this.loadedComponents.set(cacheKey, {
                pluginId,
                componentId,
                template: html,
                target: targetSelector
            });

            console.log(`✅ Loaded component ${cacheKey} into ${targetSelector}`);
            
            return { success: true, component };
        } catch (error) {
            console.error(`Failed to load component ${cacheKey}:`, error);
            throw error;
        }
    }

    /**
     * Render plugin selector UI
     * 
     * @param {string} targetSelector - CSS selector for target element
     * @param {object} options - Rendering options
     */
    renderPluginSelector(targetSelector, options = {}) {
        const target = document.querySelector(targetSelector);
        if (!target) {
            console.error(`Target element not found: ${targetSelector}`);
            return;
        }

        const enabledPlugins = this.getEnabledPlugins();
        
        const html = `
            <div class="plugin-selector">
                <h3>Active Plugins (${enabledPlugins.length})</h3>
                <div class="plugin-list">
                    ${enabledPlugins.map(plugin => `
                        <div class="plugin-item" data-plugin-id="${plugin.id}">
                            <div class="plugin-info">
                                <strong>${plugin.name}</strong>
                                <span class="plugin-version">v${plugin.version}</span>
                            </div>
                            <div class="plugin-description">${plugin.description || ''}</div>
                            <button class="btn-disable" onclick="pluginManager.disablePlugin('${plugin.id}')">
                                Disable
                            </button>
                        </div>
                    `).join('')}
                </div>
                
                ${this.plugins.filter(p => !p.enabled).length > 0 ? `
                    <h3>Available Plugins</h3>
                    <div class="plugin-list">
                        ${this.plugins.filter(p => !p.enabled).map(plugin => `
                            <div class="plugin-item disabled" data-plugin-id="${plugin.id}">
                                <div class="plugin-info">
                                    <strong>${plugin.name}</strong>
                                    <span class="plugin-version">v${plugin.version}</span>
                                </div>
                                <div class="plugin-description">${plugin.description || ''}</div>
                                <button class="btn-enable" onclick="pluginManager.enablePlugin('${plugin.id}')">
                                    Enable
                                </button>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;

        target.innerHTML = html;
    }

    /**
     * Get rating categories from rating plugins
     */
    async getRatingCategories() {
        const ratingPlugins = await this.getPluginsByType('rating');
        const categories = {};
        
        for (const plugin of ratingPlugins) {
            if (plugin.enabled) {
                const details = await this.getPluginDetails(plugin.id);
                if (details && details.manifest && details.manifest.config) {
                    const config = details.manifest.config;
                    if (config.rating_categories) {
                        categories[plugin.id] = config.rating_categories;
                    } else if (config.rating_scales) {
                        categories[plugin.id] = config.rating_scales;
                    }
                }
            }
        }
        
        return categories;
    }

    /**
     * Get export formats from export plugins
     */
    async getExportFormats() {
        const exportPlugins = await this.getPluginsByType('export');
        const formats = [];
        
        for (const plugin of exportPlugins) {
            if (plugin.enabled) {
                const details = await this.getPluginDetails(plugin.id);
                if (details && details.manifest && details.manifest.provides) {
                    const exportFormats = details.manifest.provides.export_formats || [];
                    formats.push(...exportFormats.map(format => ({
                        plugin: plugin.id,
                        format,
                        label: `${format} (${plugin.name})`
                    })));
                }
            }
        }
        
        return formats;
    }
}

// Global plugin manager instance
const pluginManager = new PluginManager();

// Auto-initialize on page load
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', async () => {
        await pluginManager.init();
        console.log('Plugin manager initialized');
    });
}

