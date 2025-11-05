import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import traceback
import logging
from bosesoundtouchapi import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Constants
DEVICES_FILE = "soundtouch_devices.json"

class SoundTouchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bose SoundTouch Controller")
        self.root.geometry("400x500")
        
        # Initialize devices
        self.devices = {}
        self.saved_devices = {}
        self.selected_device = None
        
        # Create UI
        self.setup_ui()
        
        # Load saved devices and discover
        self.load_devices()
        if not self.saved_devices:
            self.discover_devices()
    
    def setup_ui(self):
        # Device selection
        ttk.Label(self.root, text="Select Device:").pack(pady=5)
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(self.root, textvariable=self.device_var, state='readonly')
        self.device_dropdown.pack(pady=5, padx=10, fill='x')
        self.device_dropdown.bind('<<ComboboxSelected>>', self.on_device_select)
        
        # Volume control
        ttk.Label(self.root, text="Volume:").pack(pady=5)
        self.volume_slider = ttk.Scale(self.root, from_=0, to=100, orient='horizontal', 
                                     command=self.on_volume_change)
        self.volume_slider.pack(pady=5, padx=10, fill='x')
        
        # Power button
        self.power_btn = ttk.Button(self.root, text="Power On/Off", command=self.toggle_power)
        self.power_btn.pack(pady=10)
        
        # Status display
        self.status_var = tk.StringVar()
        self.status_var.set("Select a device to begin")
        ttk.Label(self.root, textvariable=self.status_var, wraplength=350).pack(pady=10)
        
        # Button frame
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Discover & Save", command=self.discover_and_save).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh Devices", command=self.refresh_devices).pack(side='left', padx=5)
        
        # Saved devices listbox
        ttk.Label(self.root, text="Saved Devices:").pack(pady=(10, 5))
        self.device_listbox = tk.Listbox(self.root, height=5)
        self.device_listbox.pack(padx=10, pady=5, fill='x')
        self.device_listbox.bind('<<ListboxSelect>>', self.on_listbox_select)
        
        # Remove button for saved devices
        ttk.Button(self.root, text="Remove Selected", command=self.remove_device).pack(pady=5)
    
    def log_error(self, message, exc_info=None):
        """Log error to both console and update status."""
        error_msg = f"Error: {message}"
        logger.error(error_msg, exc_info=exc_info)
        self.status_var.set(error_msg)
        
        # Also print full traceback to console if available
        if exc_info:
            traceback.print_exc()
    
    def discover_devices(self):
        self.status_var.set("Discovering devices...")
        self.root.update()
        
        try:
            logger.info("Starting device discovery...")
            discovery = SoundTouchDiscovery(False)
            devices = discovery.DiscoverDevices(timeout=5)
            
            self.devices = {}
            for device in devices:
                try:
                    # Handle case where device might be a string (hostname:port) or object
                    if isinstance(device, str):
                        # If it's a string, parse host and port
                        if ':' in device:
                            host, port = device.split(':', 1)
                            port = int(port)  # Convert port to int if needed
                        else:
                            host = device
                            port = 8090  # Default port for SoundTouch
                        
                        # Create device object with explicit host and port
                        device_obj = SoundTouchDevice(host, port=port)
                        device_key = f"{device_obj.DeviceName} ({host}:{port})"
                        self.devices[device_key] = {
                            'host': host,
                            'name': device_obj.DeviceName,
                            'port': port,  # Use the port we parsed earlier
                            'mac': device_obj.DeviceID if hasattr(device_obj, 'DeviceID') else ''
                        }
                    else:
                        # Original object handling
                        device_key = f"{device.DeviceName} ({device.Host})"
                        self.devices[device_key] = {
                            'host': device.Host,
                            'name': device.DeviceName,
                            'port': device.DevicePort,
                            'mac': device.DeviceID
                        }
                    logger.info(f"Discovered device: {device_key}")
                except Exception as e:
                    self.log_error(f"Error processing device {device}: {str(e)}", exc_info=True)
            
            self.update_device_dropdown()
            if self.devices:
                self.device_dropdown.current(0)
                self.on_device_select()
                status_msg = f"Found {len(self.devices)} device(s)"
                logger.info(status_msg)
                self.status_var.set(status_msg)
            else:
                status_msg = "No devices found. Check your network connection."
                logger.warning(status_msg)
                self.status_var.set(status_msg)
                
        except Exception as e:
            self.log_error(f"Discovery failed: {str(e)}", exc_info=True)
    
    def load_devices(self):
        """Load saved devices from JSON file."""
        try:
            if os.path.exists(DEVICES_FILE):
                with open(DEVICES_FILE, 'r') as f:
                    self.saved_devices = json.load(f)
                self.update_device_listbox()
                if self.saved_devices:
                    self.status_var.set(f"Loaded {len(self.saved_devices)} saved devices")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load devices: {str(e)}")
    
    def save_devices(self):
        """Save current devices to JSON file."""
        try:
            with open(DEVICES_FILE, 'w') as f:
                json.dump(self.saved_devices, f, indent=2)
            self.update_device_listbox()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save devices: {str(e)}")
    
    def update_device_dropdown(self):
        """Update the dropdown with discovered devices."""
        self.device_dropdown['values'] = list(self.devices.keys())
    
    def update_device_listbox(self):
        """Update the listbox with saved devices."""
        self.device_listbox.delete(0, tk.END)
        for name, device in self.saved_devices.items():
            self.device_listbox.insert(tk.END, f"{device.get('name', 'Unknown')} ({device.get('host', 'Unknown')})")
    
    def discover_and_save(self):
        """Discover devices and add them to saved devices."""
        self.discover_devices()
        if self.devices:
            # Add newly discovered devices to saved devices
            for name, device in self.devices.items():
                if name not in self.saved_devices:
                    self.saved_devices[name] = device
            self.save_devices()
            messagebox.showinfo("Success", f"Added {len(self.devices)} device(s) to saved devices")
    
    def refresh_devices(self):
        """Refresh the list of discovered devices."""
        self.discover_devices()
    
    def on_listbox_select(self, event):
        """Handle selection from the saved devices listbox."""
        selection = self.device_listbox.curselection()
        if selection:
            device_name = list(self.saved_devices.keys())[selection[0]]
            if device_name in self.saved_devices:
                device_info = self.saved_devices[device_name]
                try:
                    self.selected_device = SoundTouchDevice(device_info['host'])
                    self.update_device_status()
                except Exception as e:
                    self.status_var.set(f"Error connecting to device: {str(e)}")
    
    def remove_device(self):
        """Remove the selected device from saved devices."""
        selection = self.device_listbox.curselection()
        if selection:
            device_name = list(self.saved_devices.keys())[selection[0]]
            del self.saved_devices[device_name]
            self.save_devices()
            self.status_var.set(f"Removed device: {device_name}")
    
    def on_device_select(self, event=None):
        selection = self.device_var.get()
        if selection in self.devices:
            device_info = self.devices[selection]
            try:
                logger.info(f"Connecting to device: {selection}")
                self.selected_device = SoundTouchDevice(device_info['host'])
                self.update_device_status()
                
                # Add to saved devices if not already there
                if selection not in self.saved_devices:
                    logger.info(f"Adding new device to saved devices: {selection}")
                    self.saved_devices[selection] = device_info
                    self.save_devices()
            except Exception as e:
                self.log_error(f"Failed to connect to device: {str(e)}", exc_info=True)
    
    def update_device_status(self):
        if not self.selected_device:
            return
            
        try:
            # Refresh device status - use lowercase 'refresh' method
            if hasattr(self.selected_device, 'refresh'):
                self.selected_device.refresh()
            
            # Update volume slider if available
            if hasattr(self.selected_device, 'Volume') and hasattr(self.selected_device.Volume, 'Level'):
                self.volume_slider.set(self.selected_device.Volume.Level)
            
            # Build status string
            status_parts = []
            
            if hasattr(self.selected_device, 'DeviceName'):
                status_parts.append(self.selected_device.DeviceName)
            
            if hasattr(self.selected_device, 'PowerOn'):
                status_parts.append(f"Power: {'On' if self.selected_device.PowerOn else 'Off'}")
            
            if hasattr(self.selected_device, 'ContentItem'):
                if hasattr(self.selected_device.ContentItem, 'Source'):
                    status_parts.append(f"Source: {self.selected_device.ContentItem.Source}")
                if hasattr(self.selected_device.ContentItem, 'ItemName') and self.selected_device.ContentItem.ItemName:
                    status_parts.append(f"Now Playing: {self.selected_device.ContentItem.ItemName}")
            
            status = '\n'.join(status_parts)
            self.status_var.set(status)
            logger.debug("Device status updated: %s", status.replace('\n', ', '))
            
        except Exception as e:
            self.log_error(f"Failed to update device status: {str(e)}", exc_info=True)
    
    def on_volume_change(self, value):
        if self.selected_device:
            try:
                volume_level = int(float(value))
                logger.debug(f"Setting volume to {volume_level}")
                self.selected_device.Volume = volume_level
            except Exception as e:
                self.log_error(f"Failed to set volume: {str(e)}", exc_info=True)
    
    def toggle_power(self):
        if self.selected_device:
            try:
                if self.selected_device.PowerOn:
                    self.selected_device.PowerOff()
                else:
                    self.selected_device.PowerOn()
                self.update_device_status()
            except Exception as e:
                self.status_var.set(f"Error toggling power: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SoundTouchApp(root)
    root.mainloop()
