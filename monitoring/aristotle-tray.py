#!/usr/bin/python3
"""
Aristotle Inference Endpoint - System Tray Monitor

Shows GPU stats, batch job status, and quick links in the system tray.
"""

import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='gi.repository')

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, GLib
from gi.repository import AyatanaAppIndicator3 as AppIndicator3
import subprocess
import requests
import json
import os
from pathlib import Path

class AristotleIndicator:
    def __init__(self):
        self.indicator = AppIndicator3.Indicator.new(
            "aristotle-inference",
            "nvidia-settings",  # Use nvidia icon
            AppIndicator3.IndicatorCategory.SYSTEM_SERVICES
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.build_menu())
        
        # State
        self.gpu_temp = "N/A"
        self.gpu_mem = "N/A"
        self.gpu_util = "N/A"
        self.active_jobs = 0
        self.api_status = "Unknown"
        
        # Update every 5 seconds
        GLib.timeout_add_seconds(5, self.update_stats)
        self.update_stats()  # Initial update

    def build_menu(self):
        menu = Gtk.Menu()
        
        # Header
        self.header_item = Gtk.MenuItem(label="🚀 Aristotle Inference Endpoint")
        self.header_item.set_sensitive(False)
        menu.append(self.header_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # GPU Stats
        self.gpu_temp_item = Gtk.MenuItem(label="🌡️  GPU Temp: Loading...")
        self.gpu_temp_item.set_sensitive(False)
        menu.append(self.gpu_temp_item)
        
        self.gpu_mem_item = Gtk.MenuItem(label="💾 GPU Memory: Loading...")
        self.gpu_mem_item.set_sensitive(False)
        menu.append(self.gpu_mem_item)
        
        self.gpu_util_item = Gtk.MenuItem(label="⚡ GPU Util: Loading...")
        self.gpu_util_item.set_sensitive(False)
        menu.append(self.gpu_util_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Batch Job Status
        self.jobs_item = Gtk.MenuItem(label="📊 Active Jobs: Loading...")
        self.jobs_item.set_sensitive(False)
        menu.append(self.jobs_item)
        
        self.api_item = Gtk.MenuItem(label="🔌 API: Loading...")
        self.api_item.set_sensitive(False)
        menu.append(self.api_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Quick Links
        grafana_item = Gtk.MenuItem(label="📈 Open Grafana")
        grafana_item.connect("activate", self.open_grafana)
        menu.append(grafana_item)
        
        label_studio_item = Gtk.MenuItem(label="🏷️  Open Label Studio")
        label_studio_item.connect("activate", self.open_label_studio)
        menu.append(label_studio_item)
        
        api_item = Gtk.MenuItem(label="🔧 Open API Docs")
        api_item.connect("activate", self.open_api)
        menu.append(api_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Service Controls
        restart_item = Gtk.MenuItem(label="🔄 Restart Services")
        restart_item.connect("activate", self.restart_services)
        menu.append(restart_item)
        
        logs_item = Gtk.MenuItem(label="📋 View Logs")
        logs_item.connect("activate", self.view_logs)
        menu.append(logs_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Quit
        quit_item = Gtk.MenuItem(label="❌ Quit Monitor")
        quit_item.connect("activate", self.quit)
        menu.append(quit_item)
        
        menu.show_all()
        return menu

    def update_stats(self):
        """Update GPU and API stats"""
        # Get GPU stats
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                temp, mem_used, mem_total, util = result.stdout.strip().split(', ')
                self.gpu_temp = f"{temp}°C"
                self.gpu_mem = f"{mem_used}/{mem_total} MB"
                self.gpu_util = f"{util}%"
        except Exception as e:
            self.gpu_temp = "Error"
            self.gpu_mem = "Error"
            self.gpu_util = "Error"
        
        # Get API stats
        try:
            response = requests.get('http://localhost:4080/health', timeout=2)
            if response.status_code == 200:
                data = response.json()
                self.active_jobs = data.get('active_jobs', 0)
                self.api_status = "✅ Online"
            else:
                self.api_status = "⚠️  Error"
                self.active_jobs = 0
        except Exception:
            self.api_status = "❌ Offline"
            self.active_jobs = 0
        
        # Update menu items
        self.gpu_temp_item.set_label(f"🌡️  GPU Temp: {self.gpu_temp}")
        self.gpu_mem_item.set_label(f"💾 GPU Memory: {self.gpu_mem}")
        self.gpu_util_item.set_label(f"⚡ GPU Util: {self.gpu_util}")
        self.jobs_item.set_label(f"📊 Active Jobs: {self.active_jobs}")
        self.api_item.set_label(f"🔌 API: {self.api_status}")
        
        # Update indicator label (shows in tray)
        if self.active_jobs > 0:
            self.indicator.set_label(f"🔥 {self.active_jobs}", "")
        else:
            self.indicator.set_label("", "")
        
        return True  # Continue updating

    def open_grafana(self, widget):
        subprocess.Popen(['xdg-open', 'http://localhost:4020'])

    def open_label_studio(self, widget):
        subprocess.Popen(['xdg-open', 'http://localhost:4015'])

    def open_api(self, widget):
        subprocess.Popen(['xdg-open', 'http://localhost:4080/docs'])

    def restart_services(self, widget):
        """Restart all Aristotle services"""
        subprocess.Popen([
            'gnome-terminal', '--',
            'bash', '-c',
            'sudo systemctl restart aristotle-batch-api aristotle-batch-worker && '
            'docker compose restart && '
            'echo "Services restarted!" && '
            'sleep 2'
        ])

    def view_logs(self, widget):
        """Open logs in terminal"""
        subprocess.Popen([
            'gnome-terminal', '--',
            'bash', '-c',
            'journalctl -u aristotle-batch-api -u aristotle-batch-worker -f'
        ])

    def quit(self, widget):
        Gtk.main_quit()

def main():
    indicator = AristotleIndicator()
    Gtk.main()

if __name__ == "__main__":
    main()

