import tkinter as tk
from tkinter import ttk
from bosesoundtouchapi import *

class SoundTouchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bose SoundTouch Controller")
        self.root.geometry("400x500")
        
        # Discover devices
        self.devices = {}
        self.selected_device = None
        
        # Create UI
        self.setup_ui()
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
        
        # Refresh button
        ttk.Button(self.root, text="Refresh Devices", command=self.discover_devices).pack(pady=10)
    
    def discover_devices(self):
        self.status_var.set("Discovering devices...")
        self.root.update()
        
        try:
            discovery = SoundTouchDiscovery(False)
            discovery.DiscoverDevices(timeout=5)
            
            self.devices = {f"{device.DeviceName} ({device.Host})": device 
                          for device in discovery.Devices}
            
            self.device_dropdown['values'] = list(self.devices.keys())
            if self.devices:
                self.device_dropdown.current(0)
                self.on_device_select()
                self.status_var.set(f"Found {len(self.devices)} device(s)")
            else:
                self.status_var.set("No devices found. Check your network connection.")
                
        except Exception as e:
            self.status_var.set(f"Error: {str(e)}")
    
    def on_device_select(self, event=None):
        selection = self.device_var.get()
        if selection in self.devices:
            self.selected_device = self.devices[selection]
            self.update_device_status()
    
    def update_device_status(self):
        if not self.selected_device:
            return
            
        try:
            # Refresh device status
            self.selected_device.Refresh()
            
            # Update volume slider
            self.volume_slider.set(self.selected_device.Volume.Level)
            
            # Update status
            status = f"{self.selected_device.DeviceName}\n"
            status += f"Power: {'On' if self.selected_device.PowerOn else 'Off'}\n"
            status += f"Source: {self.selected_device.ContentItem.Source}\n"
            if self.selected_device.ContentItem.ItemName:
                status += f"Now Playing: {self.selected_device.ContentItem.ItemName}"
                
            self.status_var.set(status)
            
        except Exception as e:
            self.status_var.set(f"Error updating device status: {str(e)}")
    
    def on_volume_change(self, value):
        if self.selected_device:
            try:
                volume_level = int(float(value))
                self.selected_device.Volume = volume_level
            except Exception as e:
                self.status_var.set(f"Error setting volume: {str(e)}")
    
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
