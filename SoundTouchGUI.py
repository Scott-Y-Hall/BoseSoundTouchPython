import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import traceback
import logging
import io
import urllib.request
from PIL import Image, ImageTk
from bosesoundtouchapi import *
from bosesoundtouchapi.models import *

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
        self.root.geometry("600x700")  # Increased size to accommodate artwork
        
        # Initialize devices and client
        self.devices = {}
        self.saved_devices = {}
        self.selected_device = None
        self.selected_client = None  # Initialize client
        self._updating_volume = False  # Flag to prevent update loops
        self.current_artwork_url = None
        self.artwork_label = None
        self.photo = None  # Keep a reference to prevent garbage collection
        
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
        
        # Artwork display
        self.artwork_frame = ttk.Frame(self.root)
        self.artwork_frame.pack(pady=10)
        self.artwork_label = ttk.Label(self.artwork_frame)
        self.artwork_label.pack()
        
        # Status display
        self.status_var = tk.StringVar()
        self.status_var.set("Select a device to begin")
        ttk.Label(self.root, textvariable=self.status_var, wraplength=550).pack(pady=10)
        
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
                device_key = None
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
                            'mac': getattr(device_obj, 'DeviceID', '')
                        }
                    else:
                        # Original object handling with proper attribute access
                        host = getattr(device, 'Host', 'unknown')
                        name = getattr(device, 'DeviceName', 'Unknown Device')
                        port = getattr(device, 'Port', 8090)  # Default port if not available
                        device_id = getattr(device, 'DeviceID', '')
                        
                        device_key = f"{name} ({host})"
                        self.devices[device_key] = {
                            'host': host,
                            'name': name,
                            'port': port,
                            'mac': device_id
                        }
                    
                    if device_key:  # Only log if we successfully created a device key
                        logger.info(f"Discovered device: {device_key}")
                        
                except Exception as e:
                    logger.error(f"Error processing device {device}: {str(e)}", exc_info=True)
                    if device_key:  # Log the device key if we have it
                        logger.error(f"Error with device: {device_key}")
            
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
                    logger.info(f"Connecting to device from list: {device_name}")
                    
                    # Clean up any previous instances
                    if hasattr(self, 'selected_client'):
                        del self.selected_client
                    if hasattr(self, 'selected_device'):
                        del self.selected_device
                    
                    # Initialize the device and client
                    host = device_info['host']
                    port = device_info.get('port', 8090)  # Default port if not specified
                    logger.debug(f"Creating device with host: {host}, port: {port}")
                    
                    self.selected_device = SoundTouchDevice(host, port=port)
                    logger.debug("Creating SoundTouchClient")
                    self.selected_client = SoundTouchClient(self.selected_device)
                    
                    # Update the UI
                    if device_name in self.device_dropdown['values']:
                        self.device_var.set(device_name)
                    self.update_device_status()
                    
                except Exception as e:
                    error_msg = f"Error connecting to device: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    self.status_var.set(error_msg)
    
    def remove_device(self):
        """Remove the selected device from saved devices."""
        selection = self.device_listbox.curselection()
        if selection:
            device_name = list(self.saved_devices.keys())[selection[0]]
            del self.saved_devices[device_name]
            self.save_devices()
            self.status_var.set(f"Removed device: {device_name}")
    
    def start_status_updates(self):
        """Start the periodic status update loop."""
        if hasattr(self, '_status_update_job'):
            # Cancel any existing update job
            self.root.after_cancel(self._status_update_job)
        
        # Schedule the next update
        self._status_update_job = self.root.after(3000, self._update_status_loop)
    
    def _update_status_loop(self):
        """Internal method to handle the status update loop."""
        if hasattr(self, 'selected_client') and self.selected_client:
            try:
                self.update_device_status()
            except Exception as e:
                logger.error(f"Error in status update loop: {str(e)}", exc_info=True)
        
        # Schedule the next update
        self.start_status_updates()

    def on_device_select(self, event=None):
        selection = self.device_var.get()
        if selection in self.devices:
            device_info = self.devices[selection]
            try:
                logger.info(f"Connecting to device: {selection}")
                
                # Clean up any previous instances
                if hasattr(self, 'selected_client'):
                    if hasattr(self, '_status_update_job'):
                        self.root.after_cancel(self._status_update_job)
                    del self.selected_client
                if hasattr(self, 'selected_device'):
                    del self.selected_device
                
                # Create new device instance
                host = device_info['host']
                port = device_info.get('port', 8090)  # Default port if not specified
                logger.debug(f"Creating device with host: {host}, port: {port}")
                
                try:
                    # Initialize the device and client
                    self.selected_device = SoundTouchDevice(host, port=port)
                    logger.debug("Creating SoundTouchClient")
                    self.selected_client = SoundTouchClient(self.selected_device)
                    
                    # Test the connection
                    logger.debug("Testing connection...")
                    now_playing = self.selected_client.GetNowPlayingStatus(True)
                    logger.info(f"Successfully connected to {host}. Now playing: {getattr(now_playing, 'ContentItem', 'N/A')}")
                    
                    # Add to saved devices if not already there
                    if selection not in self.saved_devices:
                        logger.info(f"Adding new device to saved devices: {selection}")
                        self.saved_devices[selection] = device_info
                        self.save_devices()
                    
                    # Update UI with device status and start periodic updates
                    self.update_device_status()
                    self.start_status_updates()
                    
                except Exception as e:
                    logger.error(f"Failed to connect to device {host}: {str(e)}", exc_info=True)
                    self.status_var.set(f"Failed to connect: {str(e)}")
                    # Clean up on failure
                    if hasattr(self, 'selected_client'):
                        if hasattr(self, '_status_update_job'):
                            self.root.after_cancel(self._status_update_job)
                        del self.selected_client
                        self.selected_client = None
                    if hasattr(self, 'selected_device'):
                        del self.selected_device
                        self.selected_device = None
                    
            except Exception as e:
                self.log_error(f"Error in device selection: {str(e)}", exc_info=True)
                self.status_var.set(f"Error: {str(e)}")
    
    def update_artwork(self, image_url):
        """Update the artwork display with the image from the given URL."""
        def load_image():
            try:
                with urllib.request.urlopen(image_url) as url:
                    image_data = url.read()
                    image = Image.open(io.BytesIO(image_data))
                    
                    # Resize image to fit in the UI (max 400x400)
                    max_size = (400, 400)
                    image.thumbnail(max_size, Image.Resampling.LANCZOS)
                    
                    # Convert to PhotoImage
                    self.photo = ImageTk.PhotoImage(image)
                    
                    # Update the label in the main thread
                    self.root.after(0, lambda: self.artwork_label.configure(image=self.photo))
                    
            except Exception as e:
                logger.error(f"Error loading artwork from {image_url}: {str(e)}")
                # Clear the artwork if there was an error
                self.root.after(0, lambda: self.artwork_label.configure(image=''))
        
        # Run the image loading in a separate thread to avoid freezing the UI
        import threading
        threading.Thread(target=load_image, daemon=True).start()
    
    def update_device_status(self):
        """Update the device status display with current information."""
        logger.debug(f"update_device_status - selected_device: {getattr(self, 'selected_device', None)}")
        
        if not hasattr(self, 'selected_device') or not self.selected_device:
            logger.warning("No device selected in update_device_status")
            self.status_var.set("No device selected")
            return
            
        try:
            status_parts = []
            
            # Get basic device info
            if hasattr(self.selected_device, 'DeviceName'):
                status_parts.append(self.selected_device.DeviceName)
            
            # Get fresh status from the client if available
            if hasattr(self, 'selected_client') and self.selected_client:
                try:
                    now_playing = self.selected_client.GetNowPlayingStatus(True)
                    if now_playing:
                        # Update power state
                        if hasattr(now_playing, 'PowerState'):
                            status_parts.append(f"Power: {now_playing.PowerState}")
                        
                        # Update volume if available
                        if not self._updating_volume:
                            volume_info = self.selected_client.GetVolume(True)
                            self.volume_slider.set(volume_info.Actual)
                            status_parts.append(f"Volume: {volume_info.Actual}%")
                        
                        # Update content info if available
                        if hasattr(now_playing, 'ContentItem'):
                            content = now_playing.ContentItem
                            if hasattr(content, 'Name') and content.Name:
                                status_parts.append(f"Playing: {content.Name}")
                            if hasattr(content, 'Source') and content.Source:
                                status_parts.append(f"Source: {content.Source}")
                        if hasattr(now_playing, 'Artist') and now_playing.Artist:
                            status_parts.append(f"Artist: {now_playing.Artist}")
                        if hasattr(now_playing, 'Album') and now_playing.Album:
                            status_parts.append(f"Album: {now_playing.Album}")
                        if hasattr(now_playing, 'Track') and now_playing.Track:
                            status_parts.append(f"Track: {now_playing.Track}")
                        if hasattr(now_playing, 'Duration') and now_playing.Duration:
                            status_parts.append(f"Position: {now_playing.Position} of {now_playing.Duration}")
                        if hasattr(now_playing, 'ArtUrl') and now_playing.ArtUrl:
                            if now_playing.ArtUrl != self.current_artwork_url:
                                self.current_artwork_url = now_playing.ArtUrl
                                self.update_artwork(now_playing.ArtUrl)
                except Exception as e:
                    self.log_error(f"Error getting device status: {str(e)}")
                    status_parts.append("Status: Error")
            else:
                status_parts.append("Status: Not connected")
            
            # Update the status display
            if status_parts:
                self.status_var.set("\n".join(status_parts))
            else:
                self.status_var.set("No status available")
                
        except Exception as e:
            self.log_error(f"Error in update_device_status: {str(e)}")
            self.status_var.set(f"Error: {str(e)}")
            
            if hasattr(self.selected_device, 'ContentItem'):
                if hasattr(self.selected_device.ContentItem, 'Source'):
                    status_parts.append(f"Source: {self.selected_device.ContentItem.Source}")
                if hasattr(self.selected_device.ContentItem, 'Name') and self.selected_device.ContentItem.Name:
                    status_parts.append(f"Now Playing: {self.selected_device.ContentItem.Name}")
            
            status = '\n'.join(status_parts)
            self.status_var.set(status)
            logger.debug("Device status updated: %s", status.replace('\n', ', '))
            
        except Exception as e:
            self.log_error(f"Failed to update device status: {str(e)}", exc_info=True)
    
    def on_volume_change(self, value):
        if hasattr(self, 'selected_client') and self.selected_client and not self._updating_volume:
            try:
                self._updating_volume = True
                volume_level = int(float(value))
                logger.debug(f"Setting volume to {volume_level}")
                
                # Update status immediately for better responsiveness
                current_status = self.status_var.get()
                if 'Volume:' in current_status:
                    # Update the volume in the status text
                    lines = current_status.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith('Volume:'):
                            lines[i] = f"Volume: {volume_level}%"
                            break
                    self.status_var.set('\n'.join(lines))
                
                # Set the volume on the device
                self.selected_client.SetVolumeLevel(volume_level)
                
            except Exception as e:
                self.log_error(f"Failed to set volume: {str(e)}", exc_info=True)
            finally:
                self._updating_volume = False
    
    def toggle_power(self):
        logger.debug(f"toggle_power called - has selected_client: {hasattr(self, 'selected_client')}, selected_client: {getattr(self, 'selected_client', None)}")
        logger.debug(f"selected_device: {getattr(self, 'selected_device', None)}")
        
        if not hasattr(self, 'selected_client') or not self.selected_client:
            error_msg = "No device client available. "
            if hasattr(self, 'selected_device'):
                error_msg += f"Device: {self.selected_device}"
            self.status_var.set(error_msg)
            logger.error(error_msg)
            return
            
        try:
            # Get current power state first
            now_playing = self.selected_client.GetNowPlayingStatus(True)
            print("\nCurrent Now Playing Status:\n%s" % now_playing.ToString())
            if now_playing and hasattr(now_playing, 'PowerState'):
                # Toggle power based on current state
                if now_playing.PowerState == 'ON':
                    self.selected_client.PowerOff()
                else:
                    self.selected_client.PowerOn()
                
                # Update UI after a short delay to allow the device to process the command
                self.root.after(1000, self.update_device_status)
            else:
                # Fallback to toggle if we can't determine current state
                self.selected_client.Power()
                self.root.after(1000, self.update_device_status)
                
        except Exception as e:
            self.log_error(f"Error toggling power: {str(e)}", exc_info=True)
            self.status_var.set(f"Error toggling power: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SoundTouchApp(root)
    root.mainloop()
