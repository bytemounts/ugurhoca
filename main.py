import asyncio
import json
import threading
import time
from datetime import datetime
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Callable
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import numpy as np
import csv
from bleak import BleakScanner, BleakClient
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration - Optimized for real-time performance
NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
MAX_DATA_POINTS = 100  # Reduced for better performance
ANIMATION_INTERVAL = 16  # ~60 FPS for smooth real-time display
PLOT_UPDATE_BATCH_SIZE = 1  # Process data immediately

@dataclass
class SensorData:
    """Sensor data structure"""
    unit: str
    timestamp: int
    mv: float
    value: int
    channel: int
    received_time: float

@dataclass
class TimingEntry:
    """Enhanced timing entry for LED control sequence"""
    state: bool = False  # LED state (ON/OFF)
    time_open_ms: int = 100  # LED on time in milliseconds
    time_delay_ms: int = 50  # Delay before measurement starts
    time_read_ms: int = 10   # ADC reading duration
    pin: int = 1  # LED pin number
    enabled: bool = False  # Timing entry enabled/disabled
    index: int = None  # Timing entry index
    
    @property
    def cycle_time_ms(self):
        """Total cycle time"""
        return self.time_open_ms + self.time_delay_ms + self.time_read_ms + 10  # Add buffer time
    
    @property
    def frequency_hz(self):
        """Frequency in Hz"""
        return 1000.0 / self.cycle_time_ms if self.cycle_time_ms > 0 else 0

@dataclass
class SensorConfig:
    """Configuration for each sensor"""
    sensor_id: int
    led_id: int
    detector_id: int
    molecule_name: str = ""
    unit: str = ""
    calibration_coeffs: Optional[tuple] = None
    calibration_points: List[tuple] = None
    timing_entries: List[TimingEntry] = None
    active_timing_index: int = 0

    def __post_init__(self):
        if self.timing_entries is None:
            self.timing_entries = [TimingEntry(on_time_ms=100, off_time_ms=900, enabled=False, index=1)]

class BLEDataManager:
    """Manages BLE communication and data handling - Optimized for real-time"""
    
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.device = None
        self.is_connected = False
        self.is_scanning = False
        self.recv_buffer = ""
        
        # Data storage - separate deques for each channel with thread-safe access
        self.data_channels = {
            0: deque(maxlen=MAX_DATA_POINTS),
            1: deque(maxlen=MAX_DATA_POINTS),
            2: deque(maxlen=MAX_DATA_POINTS),
            3: deque(maxlen=MAX_DATA_POINTS)
        }
        
        # Thread locks for data safety
        self.data_lock = threading.Lock()
        
        # Session data storage
        self.session_data = []
        
        # Performance tracking
        self.last_data_time = time.time()
        self.data_receive_count = 0
        
        # Callbacks
        self.on_data_received: Optional[Callable] = None
        self.on_connection_changed: Optional[Callable] = None
        self.on_message: Optional[Callable] = None
        
    def notification_handler(self, sender, data: bytearray):
        """Handle incoming BLE notifications - Optimized for minimal latency"""
        receive_timestamp = time.time()  # Capture timestamp immediately
        
        try:
            chunk = data.decode('utf-8', errors='replace')
        except Exception as e:
            self._log_message(f"Decode error: {e}")
            return
            
        self.recv_buffer += chunk
        
        # Process complete JSON messages separated by \n - Immediate processing
        while '\n' in self.recv_buffer:
            line, self.recv_buffer = self.recv_buffer.split('\n', 1)
            line = line.strip()
            if not line:
                continue
                
            try:
                parsed = json.loads(line)
                self._handle_json_message(parsed, receive_timestamp)
            except json.JSONDecodeError as e:
                self._log_message(f"JSON decode error: {e}")
    
    def _handle_json_message(self, parsed, receive_timestamp):
        """Process parsed JSON message - Optimized for real-time"""
        if not isinstance(parsed, list):
            self._log_message(f"Warning: Expected list, got {type(parsed)}")
            return
            
        if len(parsed) != 4:
            self._log_message(f"Warning: Expected 4 channels, got {len(parsed)}")
        
        # Performance tracking
        self.data_receive_count += 1
        
        # Session data entry
        session_entry = {
            'timestamp': receive_timestamp,
            'datetime': datetime.now().isoformat(),
            'sensors': {}
        }
        
        # Process each channel with thread safety
        with self.data_lock:
            for channel, data in enumerate(parsed[:4]):  # Limit to 4 channels
                if isinstance(data, list) and len(data) >= 4:
                    sensor_data = SensorData(
                        unit=data[0],
                        timestamp=data[1],
                        mv=float(data[2]),
                        value=int(data[3]),
                        channel=channel,
                        received_time=receive_timestamp
                    )
                    
                    self.data_channels[channel].append(sensor_data)
                    
                    # Add to session data
                    session_entry['sensors'][channel] = {
                        'raw': sensor_data.value,
                        'real': sensor_data.mv
                    }
                    
                    # Immediate callback for real-time update
                    if self.on_data_received:
                        self.on_data_received(sensor_data)
        
        # Store session data
        self.session_data.append(session_entry)
        self.last_data_time = receive_timestamp
    
    def get_channel_data(self, channel):
        """Thread-safe data access"""
        with self.data_lock:
            return list(self.data_channels[channel])
    
    def _log_message(self, message: str):
        """Log message through callback"""
        if self.on_message:
            self.on_message(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}")
    
    async def scan_devices(self, timeout: float = 5.0):
        """Scan for BLE devices"""
        self.is_scanning = True
        self._log_message("Scanning for BLE devices...")
        
        try:
            devices = await BleakScanner.discover(timeout=timeout)
            found_devices = []
            
            for device in devices:
                name = (device.name or "").lower()
                uuids = []
                
                # Get UUIDs from metadata
                metadata = getattr(device, "metadata", None)
                if isinstance(metadata, dict):
                    try:
                        uuids = [u.lower() for u in (metadata.get("uuids") or [])]
                    except Exception:
                        pass
                
                # Check if device matches our criteria
                if (NUS_SERVICE in uuids or 
                    any(keyword in name for keyword in ["bluefruit", "feather", "json_sender", "nrf"])):
                    found_devices.append(device)
                    self._log_message(f"Found compatible device: {device.name} ({device.address})")
                    
            return found_devices
            
        except Exception as e:
            self._log_message(f"Scan error: {e}")
            return []
        finally:
            self.is_scanning = False
    
    async def connect(self, device):
        """Connect to BLE device with optimized settings"""
        try:
            self.device = device
            # Optimized connection parameters for real-time data
            self.client = BleakClient(device, timeout=10.0)
            await self.client.connect()
            
            if self.client.is_connected:
                self.is_connected = True
                # Start notifications immediately
                await self.client.start_notify(NUS_TX, self.notification_handler)
                self._log_message(f"Connected to {device.name} - Real-time mode enabled")
                
                if self.on_connection_changed:
                    self.on_connection_changed(True)
                
                return True
            else:
                self._log_message("Failed to connect")
                return False
                
        except Exception as e:
            self._log_message(f"Connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from BLE device"""
        try:
            if self.client and self.is_connected:
                await self.client.stop_notify(NUS_TX)
                await self.client.disconnect()
                self.is_connected = False
                
                if self.on_connection_changed:
                    self.on_connection_changed(False)
                
                self._log_message("Disconnected")
                
        except Exception as e:
            self._log_message(f"Disconnect error: {e}")
    
    def clear_data(self):
        """Clear all stored data"""
        with self.data_lock:
            for channel in self.data_channels.values():
                channel.clear()
        self.session_data.clear()
        self.data_receive_count = 0

class BLEDataAcquisitionGUI:
    """Professional GUI for BLE Data Acquisition - Optimized for Real-time Performance"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("BLE Data Acquisition System v2.0 - NRF52840 Express (Real-time Optimized)")
        self.root.geometry("1400x800")
        self.root.configure(bg='#2c3e50')
        
        # Data manager
        self.ble_manager = BLEDataManager()
        self.ble_manager.on_data_received = self.on_data_received
        self.ble_manager.on_connection_changed = self.on_connection_changed
        self.ble_manager.on_message = self.on_message
        
        # Initialize sensor configs
        self.sensor_configs = {}
        self.init_sensor_configs()
        
        # Channel visibility state
        self.channel_visibility = {0: True, 1: True, 2: True, 3: True}
        
        # Threading
        self.event_loop = None
        self.loop_thread = None
        self.is_running = False
        
        # Animation and real-time optimization
        self.animation = None
        self.is_recording = False
        self.plot_update_pending = False
        self.last_plot_update = 0
        
        # Performance tracking
        self.performance_counter = 0
        self.last_performance_update = time.time()
        
        # Available devices
        self.available_devices = []
        
        # Setup GUI
        self.setup_gui()
        self.setup_plot()
        
        # Start event loop
        self.start_event_loop()
        
        logger.info("BLE Data Acquisition System initialized - Real-time optimized")
    
    def init_sensor_configs(self):
        """Initialize default sensor configurations"""
        sensor_mappings = [
            (0, 0, 0, "Channel 0", "mV"),
            (1, 1, 1, "Channel 1", "mV"),
            (2, 2, 2, "Channel 2", "mV"),
            (3, 3, 3, "Channel 3", "mV")
        ]
        
        for sensor_id, led_id, detector_id, molecule_name, unit in sensor_mappings:
            self.sensor_configs[sensor_id] = SensorConfig(
                sensor_id=sensor_id,
                led_id=led_id,
                detector_id=detector_id,
                molecule_name=molecule_name,
                unit=unit,
                timing_entries=[TimingEntry(
                    state=False,
                    time_open_ms=100, 
                    time_delay_ms=50,
                    time_read_ms=10,
                    pin=1,
                    enabled=False, 
                    index=1
                )]
        )
        
        logger.debug(f"Sensor configurations initialized: {len(self.sensor_configs)} sensors")
    
    def setup_gui(self):
        """Setup the GUI components"""
        # Create main container
        main_container = tk.Frame(self.root, bg='#2c3e50')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create left side (main content)
        self.left_frame = tk.Frame(main_container, bg='#2c3e50')
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create right side (channel buttons)
        self.right_frame = tk.Frame(main_container, bg='#34495e', width=200)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=10)
        self.right_frame.pack_propagate(False)
        
        # Setup left side components
        self.create_header_frame()
        self.create_control_frame()
        self.create_main_content_frame()
        self.create_status_frame()
        
        # Setup right side components
        self.create_channel_buttons()
        
    def create_header_frame(self):
        """Create header with title and time"""
        header_frame = tk.Frame(self.left_frame, bg='#34495e', height=60)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="BLE Data Acquisition System - NRF52840 Express (Real-time)", 
                              font=('Arial', 18, 'bold'), fg='white', bg='#34495e')
        title_label.pack(side=tk.LEFT, padx=20, pady=15)
        
        # Performance indicator
        self.performance_label = tk.Label(header_frame, text="", font=('Arial', 10), fg='#1abc9c', bg='#34495e')
        self.performance_label.pack(side=tk.RIGHT, padx=5, pady=15)
        
        time_label = tk.Label(header_frame, text="", font=('Arial', 12), fg='#ecf0f1', bg='#34495e')
        time_label.pack(side=tk.RIGHT, padx=20, pady=15)
        
        def update_time():
            time_label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            # Update performance indicator
            current_time = time.time()
            if current_time - self.last_performance_update >= 1.0:
                data_rate = self.ble_manager.data_receive_count
                self.performance_label.config(text=f"Data Rate: {data_rate} samples/s")
                self.ble_manager.data_receive_count = 0
                self.last_performance_update = current_time
            
            self.root.after(1000, update_time)
        
        update_time()
    
    def create_control_frame(self):
        """Create control panel with buttons"""
        control_frame = tk.Frame(self.left_frame, bg='#ecf0f1', height=80)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        control_frame.pack_propagate(False)
        
        button_style = {'font': ('Arial', 11, 'bold'), 'width': 12, 'height': 2}
        
        # Connection controls
        self.scan_btn = tk.Button(control_frame, text="SCAN", bg='#9b59b6', fg='white',
                                 command=self.scan_devices, **button_style)
        self.scan_btn.pack(side=tk.LEFT, padx=10, pady=15)
        
        self.connect_btn = tk.Button(control_frame, text="CONNECT", bg='#3498db', fg='white',
                                   command=self.connect_device, **button_style)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_btn = tk.Button(control_frame, text="DISCONNECT", bg='#95a5a6', fg='white',
                                      command=self.disconnect_device, state=tk.DISABLED, **button_style)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        # Recording controls
        self.start_btn = tk.Button(control_frame, text="START", bg='#27ae60', fg='white',
                                 command=self.start_recording, state=tk.DISABLED, **button_style)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(control_frame, text="STOP", bg='#e74c3c', fg='white',
                                command=self.stop_recording, state=tk.DISABLED, **button_style)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Configuration controls
        self.timing_btn = tk.Button(control_frame, text="TIMING", bg='#f39c12', fg='white',
                                   command=self.open_timing_config, **button_style)
        self.timing_btn.pack(side=tk.LEFT, padx=5)
        
        self.export_btn = tk.Button(control_frame, text="EXPORT", bg='#8e44ad', fg='white',
                                  command=self.export_data, state=tk.DISABLED, **button_style)
        self.export_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = tk.Button(control_frame, text="CLEAR", bg='#e67e22', fg='white',
                                 command=self.clear_data, **button_style)
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Device selection
        ttk.Label(control_frame, text="Device:", font=('Arial', 10), background='#ecf0f1').pack(side=tk.RIGHT, padx=(10, 5), pady=15)
        
        self.device_combo = ttk.Combobox(control_frame, state="readonly", width=25, font=('Arial', 9))
        self.device_combo.pack(side=tk.RIGHT, padx=(0, 10), pady=15)
    
    def create_channel_buttons(self):
        """Create vertical channel control buttons on the right side"""
        # Title for channel controls
        title_label = tk.Label(self.right_frame, text="Channel Controls", 
                             font=('Arial', 14, 'bold'), fg='white', bg='#34495e')
        title_label.pack(pady=(10, 20))
        
        # Channel buttons
        self.channel_buttons = {}
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12']
        
        for i in range(4):
            # Container for each channel
            channel_frame = tk.Frame(self.right_frame, bg='#34495e')
            channel_frame.pack(fill=tk.X, pady=5, padx=10)
            
            # Channel button
            btn = tk.Button(channel_frame, 
                           text=f"Channel {i}\nENABLED", 
                           font=('Arial', 10, 'bold'),
                           bg=colors[i], 
                           fg='white',
                           width=15,
                           height=3,
                           command=lambda ch=i: self.toggle_channel(ch),
                           relief=tk.RAISED,
                           bd=3)
            btn.pack(fill=tk.X, pady=2)
            
            # Data display for this channel
            data_frame = tk.Frame(channel_frame, bg='#2c3e50', relief=tk.SUNKEN, bd=1)
            data_frame.pack(fill=tk.X, pady=2)
            
            # Value display
            value_label = tk.Label(data_frame, text="Value:", 
                                 font=('Arial', 8), fg='#bdc3c7', bg='#2c3e50')
            value_label.pack(anchor=tk.W, padx=5, pady=1)
            
            value_display = tk.Label(data_frame, text="0.00 mV", 
                                   font=('Arial', 10, 'bold'), fg='white', bg='#2c3e50')
            value_display.pack(padx=5, pady=1)
            
            # Raw display
            raw_label = tk.Label(data_frame, text="Raw:", 
                               font=('Arial', 8), fg='#bdc3c7', bg='#2c3e50')
            raw_label.pack(anchor=tk.W, padx=5, pady=1)
            
            raw_display = tk.Label(data_frame, text="0", 
                                 font=('Arial', 10, 'bold'), fg='#95a5a6', bg='#2c3e50')
            raw_display.pack(padx=5, pady=(1, 5))
            
            self.channel_buttons[i] = {
                'button': btn,
                'value_display': value_display,
                'raw_display': raw_display,
                'color': colors[i]
            }
    
    def toggle_channel(self, channel):
        """Toggle channel visibility on the graph"""
        self.channel_visibility[channel] = not self.channel_visibility[channel]
        
        # Update button appearance
        btn = self.channel_buttons[channel]['button']
        if self.channel_visibility[channel]:
            btn.config(text=f"Channel {channel}\nENABLED",
                      bg=self.channel_buttons[channel]['color'],
                      relief=tk.RAISED)
        else:
            btn.config(text=f"Channel {channel}\nDISABLED",
                      bg='#7f8c8d',
                      relief=tk.SUNKEN)
        
        self.on_message(f"Channel {channel} {'enabled' if self.channel_visibility[channel] else 'disabled'}")
    
    def create_main_content_frame(self):
        """Create main content area with notebook"""
        main_frame = tk.Frame(self.left_frame, bg='#ecf0f1')
        main_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create notebook for different views
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Graph tab
        self.graph_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.graph_frame, text="Real-time Graph")
        
        # Statistics tab
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="Statistics")
        
        # Log tab
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="Log")
        
        # Setup statistics
        self.setup_statistics(stats_frame)
        
        # Setup log
        self.setup_log(log_frame)
    
    def setup_plot(self):
        """Setup matplotlib plot - Combined view with toggle functionality"""
        plt.style.use('fast')  # Use fast rendering style
        
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.fig.patch.set_facecolor('#ecf0f1')
        
        self.ax.set_title('Combined Real-time mV Measurements', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Voltage (mV)')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_facecolor('#ffffff')
        
        # Initialize line plots for each channel with optimized settings
        self.lines = {}
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12']
        for i in range(4):
            line, = self.ax.plot([], [], color=colors[i], linewidth=2, 
                               label=f'Channel {i}', alpha=0.8,
                               marker=None, linestyle='-')  # Optimized for speed
            self.lines[i] = line
        
        self.ax.legend(loc='upper left')
        
        # Clear any existing canvas
        for widget in self.graph_frame.winfo_children():
            widget.destroy()
        
        # Embed plot in tkinter with optimized settings
        self.canvas = FigureCanvasTkAgg(self.fig, self.graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Disable toolbar for better performance
        self.canvas.get_tk_widget().configure(highlightthickness=0)
    
    def setup_statistics(self, parent):
        """Setup statistics view"""
        # Create treeview for statistics
        columns = ('Channel', 'Current (mV)', 'Min (mV)', 'Max (mV)', 'Avg (mV)', 'Count')
        self.stats_tree = ttk.Treeview(parent, columns=columns, show='headings')
        
        for col in columns:
            self.stats_tree.heading(col, text=col)
            self.stats_tree.column(col, width=100, anchor=tk.CENTER)
        
        # Add scrollbar
        stats_scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.stats_tree.yview)
        self.stats_tree.configure(yscrollcommand=stats_scrollbar.set)
        
        self.stats_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        stats_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Initialize rows
        for i in range(4):
            self.stats_tree.insert('', 'end', iid=f'ch{i}', 
                                 values=(f'Channel {i}', '-', '-', '-', '-', '0'))
    
    def setup_log(self, parent):
        """Setup log view"""
        self.log_text = scrolledtext.ScrolledText(parent, height=20, width=80)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def create_status_frame(self):
        """Create status bar"""
        status_frame = tk.Frame(self.left_frame, bg='#34495e', height=30)
        status_frame.pack(fill=tk.X)
        status_frame.pack_propagate(False)
        
        self.status_var = tk.StringVar(value="System Ready - Real-time Mode")
        status_label = tk.Label(status_frame, textvariable=self.status_var, 
                              font=('Arial', 10), fg='white', bg='#34495e')
        status_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.connection_var = tk.StringVar(value="Disconnected")
        self.connection_label = tk.Label(status_frame, textvariable=self.connection_var, 
                                       font=('Arial', 10), fg='#e74c3c', bg='#34495e')
        self.connection_label.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def start_event_loop(self):
        """Start asyncio event loop in separate thread"""
        def run_loop():
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            self.event_loop.run_forever()
        
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
    
    def run_async(self, coro):
        """Run coroutine in the event loop"""
        if self.event_loop:
            return asyncio.run_coroutine_threadsafe(coro, self.event_loop)
    
    def scan_devices(self):
        """Scan for BLE devices"""
        self.scan_btn.configure(state=tk.DISABLED, text="Scanning...")
        
        def on_scan_complete(future):
            try:
                devices = future.result()
                self.available_devices = devices
                device_names = [f"{d.name or 'Unknown'} ({d.address})" for d in devices]
                
                self.root.after(0, lambda: self.device_combo.configure(values=device_names))
                
                if devices:
                    self.root.after(0, lambda: self.device_combo.current(0))
                    message = f"Found {len(devices)} compatible device(s)"
                else:
                    message = "No compatible devices found"
                
                self.on_message(message)
                
            except Exception as e:
                self.on_message(f"Scan error: {e}")
            finally:
                self.root.after(0, lambda: self.scan_btn.configure(state=tk.NORMAL, text="SCAN"))
        
        future = self.run_async(self.ble_manager.scan_devices())
        future.add_done_callback(on_scan_complete)
    
    def connect_device(self):
        """Connect to selected device"""
        if not self.available_devices or self.device_combo.current() == -1:
            messagebox.showwarning("Warning", "Please scan and select a device first")
            return
        
        device = self.available_devices[self.device_combo.current()]
        self.connect_btn.configure(state=tk.DISABLED, text="Connecting...")
        
        def on_connect_complete(future):
            try:
                success = future.result()
                if success:
                    self.root.after(0, self.update_connection_ui)
                else:
                    messagebox.showerror("Error", "Failed to connect to device")
            except Exception as e:
                messagebox.showerror("Error", f"Connection error: {e}")
            finally:
                self.root.after(0, lambda: self.connect_btn.configure(state=tk.NORMAL, text="CONNECT"))
        
        future = self.run_async(self.ble_manager.connect(device))
        future.add_done_callback(on_connect_complete)
    
    def disconnect_device(self):
        """Disconnect from device"""
        self.run_async(self.ble_manager.disconnect())
    
    def start_recording(self):
        """Start data recording and visualization"""
        self.is_recording = True
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.export_btn.configure(state=tk.DISABLED)
        
        # Start animation
        self.animation = FuncAnimation(self.fig, self.update_plot, interval=100, blit=False)
        self.canvas.draw()
        
        self.on_message("Recording started")
        self.status_var.set("Recording in progress...")
    
    def stop_recording(self):
        """Stop data recording"""
        self.is_recording = False
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.export_btn.configure(state=tk.NORMAL)
        
        # Stop animation
        if self.animation:
            self.animation.event_source.stop()
        
        self.on_message("Recording stopped")
        self.status_var.set("Recording stopped")
    
    def clear_data(self):
        """Clear all data"""
        self.ble_manager.clear_data()
        
        # Clear plot
        for line in self.lines.values():
            line.set_data([], [])
        self.canvas.draw()
        
        # Clear statistics
        for i in range(4):
            self.stats_tree.item(f'ch{i}', values=(f'Channel {i}', '-', '-', '-', '-', '0'))
        
        self.on_message("Data cleared")
        self.status_var.set("Data cleared")
    
    def open_timing_config(self):
        """Open professional timing configuration window - Version modifiée"""
        timing_window = tk.Toplevel(self.root)
        timing_window.title("LED Sequential Timing Configuration - Professional")
        timing_window.geometry("1000x750")
        timing_window.configure(bg='#2c3e50')
        timing_window.transient(self.root)
        timing_window.grab_set()
        
        # Make window non-resizable for professional look
        timing_window.resizable(False, False)
        
        # Center the window
        timing_window.update_idletasks()
        x = (timing_window.winfo_screenwidth() // 2) - (500)
        y = (timing_window.winfo_screenheight() // 2) - (375)
        timing_window.geometry(f"1000x750+{x}+{y}")
        
        # Header
        header_frame = tk.Frame(timing_window, bg='#34495e', height=70)
        header_frame.pack(fill=tk.X, padx=15, pady=15)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="LED Sequential Timing Configuration", 
                            font=('Arial', 18, 'bold'), fg='white', bg='#34495e')
        title_label.pack(side=tk.LEFT, padx=25, pady=20)
        
        # Info label with professional styling
        info_label = tk.Label(header_frame, text="Configure up to 4 timing sequences per sensor", 
                            font=('Arial', 11), fg='#bdc3c7', bg='#34495e')
        info_label.pack(side=tk.RIGHT, padx=25, pady=20)
        
        # Main content frame with professional styling
        main_frame = tk.Frame(timing_window, bg='#ecf0f1', relief=tk.RAISED, bd=1)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # Configuration frame with enhanced styling
        config_frame = tk.LabelFrame(main_frame, text="Timing Sequences Configuration", 
                                    font=('Arial', 14, 'bold'), bg='#ecf0f1', fg='#2c3e50',
                                    relief=tk.GROOVE, bd=2)
        config_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Create timing entries table with professional layout
        timing_entries_frame = tk.Frame(config_frame, bg='#ecf0f1')
        timing_entries_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Professional headers with enhanced styling
        headers = ["Enable", "Time Open (ms)", "Time Delay (ms)", "Time Read (ms)", "Target Sensor", "Actions"]
        header_frame = tk.Frame(timing_entries_frame, bg='#34495e', relief=tk.RAISED, bd=1)
        header_frame.pack(fill=tk.X, pady=(0, 8))
        
        header_widths = [10, 15, 15, 15, 15, 12]
        for i, (header, width) in enumerate(zip(headers, header_widths)):
            label = tk.Label(header_frame, text=header, font=('Arial', 11, 'bold'), 
                            fg='white', bg='#34495e', width=width, pady=8)
            label.pack(side=tk.LEFT, padx=3, pady=8)
        
        # Scrollable frame for timing entries with professional styling
        canvas = tk.Canvas(timing_entries_frame, bg='#ecf0f1', height=320, 
                        highlightthickness=1, highlightbackground='#bdc3c7')
        scrollbar = ttk.Scrollbar(timing_entries_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#ecf0f1')
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Storage for entry widgets and timing counter
        timing_widgets = []
        timing_count = 0
        MAX_TIMING_ENTRIES = 4
        
        def create_timing_entry_row(parent, entry_data=None):
            """Create a professional row for timing entry configuration"""
            nonlocal timing_count
            
            if timing_count >= MAX_TIMING_ENTRIES:
                messagebox.showwarning("Limite atteinte", 
                                    f"Maximum {MAX_TIMING_ENTRIES} séquences de timing autorisées")
                return None
            
            # Professional row styling with alternating colors
            row_color = '#ffffff' if timing_count % 2 == 0 else '#f8f9fa'
            row_frame = tk.Frame(parent, bg=row_color, relief=tk.SOLID, bd=1)
            row_frame.pack(fill=tk.X, pady=3, padx=2)
            
            widgets = {}
            
            # Enable checkbox with professional styling
            enable_var = tk.BooleanVar(value=entry_data.enabled if entry_data else False)
            enable_check = tk.Checkbutton(row_frame, variable=enable_var, bg=row_color, 
                                        font=('Arial', 10), activebackground=row_color)
            enable_check.pack(side=tk.LEFT, padx=(15, 5), pady=12)
            widgets['enabled'] = enable_var
            
            # Time Open with professional validation
            time_open_var = tk.StringVar(value=str(entry_data.time_open_ms if entry_data else 100))
            time_open_entry = tk.Entry(row_frame, textvariable=time_open_var, width=12, 
                                    font=('Arial', 10), justify=tk.CENTER, relief=tk.SOLID, bd=1)
            time_open_entry.pack(side=tk.LEFT, padx=15, pady=10)
            widgets['time_open'] = time_open_var
            
            # Time Delay with professional validation
            time_delay_var = tk.StringVar(value=str(entry_data.time_delay_ms if entry_data else 50))
            time_delay_entry = tk.Entry(row_frame, textvariable=time_delay_var, width=12, 
                                    font=('Arial', 10), justify=tk.CENTER, relief=tk.SOLID, bd=1)
            time_delay_entry.pack(side=tk.LEFT, padx=15, pady=10)
            widgets['time_delay'] = time_delay_var
            
            # Time Read with professional validation
            time_read_var = tk.StringVar(value=str(entry_data.time_read_ms if entry_data else 10))
            time_read_entry = tk.Entry(row_frame, textvariable=time_read_var, width=12, 
                                    font=('Arial', 10), justify=tk.CENTER, relief=tk.SOLID, bd=1)
            time_read_entry.pack(side=tk.LEFT, padx=15, pady=10)
            widgets['time_read'] = time_read_var
            
            # Target Sensor Selection (Professional Combobox)
            sensor_var = tk.StringVar(value=f"Sensor {entry_data.pin - 1}" if entry_data else "Sensor 0")
            sensor_combo = ttk.Combobox(row_frame, textvariable=sensor_var, 
                                    values=[f"Sensor {i}" for i in range(4)], 
                                    state="readonly", width=12, font=('Arial', 10))
            sensor_combo.pack(side=tk.LEFT, padx=15, pady=10)
            widgets['target_sensor'] = sensor_var
            
            # Professional Actions frame
            action_frame = tk.Frame(row_frame, bg=row_color)
            action_frame.pack(side=tk.LEFT, padx=15, pady=10)
            
            def remove_entry():
                nonlocal timing_count
                row_frame.destroy()
                timing_widgets.remove(widgets)
                timing_count -= 1
                update_preview()
                update_add_button_state()
            
            # Professional Remove button
            remove_btn = tk.Button(action_frame, text="Remove", bg='#e74c3c', fg='white', 
                                font=('Arial', 9, 'bold'), command=remove_entry, width=10,
                                relief=tk.FLAT, cursor='hand2')
            remove_btn.pack(side=tk.LEFT, padx=2)
            
            # Professional validation bindings
            for var in [time_open_var, time_delay_var, time_read_var]:
                var.trace('w', lambda *args: validate_and_update())
            enable_var.trace('w', lambda *args: update_preview())
            sensor_var.trace('w', lambda *args: update_preview())
            
            def validate_and_update():
                """Professional input validation"""
                try:
                    # Validate numeric inputs
                    for var_name, var in [('Time Open', time_open_var), 
                                        ('Time Delay', time_delay_var), 
                                        ('Time Read', time_read_var)]:
                        value = var.get()
                        if value and not value.isdigit():
                            var.set(''.join(filter(str.isdigit, value)))
                        elif value and (int(value) < 1 or int(value) > 10000):
                            # Professional range validation
                            if int(value) < 1:
                                var.set('1')
                            elif int(value) > 10000:
                                var.set('10000')
                    update_preview()
                except ValueError:
                    pass
            
            timing_widgets.append(widgets)
            timing_count += 1
            return widgets
        
        def update_add_button_state():
            """Update add button state based on timing count"""
            if timing_count >= MAX_TIMING_ENTRIES:
                add_btn.config(state=tk.DISABLED, text=f"Maximum {MAX_TIMING_ENTRIES} Timings", 
                            bg='#95a5a6')
            else:
                add_btn.config(state=tk.NORMAL, text=f"+ Add Timing Entry ({timing_count}/{MAX_TIMING_ENTRIES})", 
                            bg='#27ae60')
        
        def add_timing_entry():
            """Add new timing entry with professional validation"""
            if timing_count < MAX_TIMING_ENTRIES:
                create_timing_entry_row(scrollable_frame)
                canvas.configure(scrollregion=canvas.bbox("all"))
                update_preview()
                update_add_button_state()
        
        def update_preview():
            """Update timing preview with professional calculations"""
            try:
                total_time = 0
                active_entries = 0
                sensor_distribution = {f"Sensor {i}": 0 for i in range(4)}
                
                for widget_set in timing_widgets:
                    if widget_set['enabled'].get():
                        time_open = int(widget_set['time_open'].get() or 0)
                        time_delay = int(widget_set['time_delay'].get() or 0)
                        time_read = int(widget_set['time_read'].get() or 0)
                        
                        cycle_time = time_open + time_delay + time_read + 10  # Buffer
                        total_time += cycle_time
                        active_entries += 1
                        
                        # Count sensor distribution
                        target_sensor = widget_set['target_sensor'].get()
                        sensor_distribution[target_sensor] += 1
                
                frequency = 1000.0 / total_time if total_time > 0 else 0
                
                # Professional preview display
                preview_text = f"Configuration Summary:\n"
                preview_text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                preview_text += f"Active Sequences: {active_entries}/{MAX_TIMING_ENTRIES}\n"
                preview_text += f"Total Cycle Time: {total_time} ms\n"
                preview_text += f"System Frequency: {frequency:.2f} Hz\n"
                preview_text += f"Samples/Second: {frequency * active_entries:.1f}\n\n"
                
                # Sensor distribution
                preview_text += "Sensor Distribution:\n"
                for sensor, count in sensor_distribution.items():
                    if count > 0:
                        preview_text += f"  • {sensor}: {count} sequence(s)\n"
                
                if active_entries == 0:
                    preview_text = "No active timing sequences configured"
                
                preview_label.config(text=preview_text)
                
            except ValueError:
                preview_label.config(text="⚠ Invalid configuration detected")
        
        # Professional Add entry button frame
        add_btn_frame = tk.Frame(timing_entries_frame, bg='#ecf0f1')
        add_btn_frame.pack(fill=tk.X, pady=12)
        
        add_btn = tk.Button(add_btn_frame, text=f"+ Add Timing Entry (0/{MAX_TIMING_ENTRIES})", 
                        bg='#27ae60', fg='white', font=('Arial', 12, 'bold'), 
                        command=add_timing_entry, width=35, height=1,
                        relief=tk.FLAT, cursor='hand2')
        add_btn.pack(side=tk.LEFT, padx=15)
        
        # Professional Preview frame
        preview_frame = tk.LabelFrame(main_frame, text="Configuration Preview", 
                                    font=('Arial', 12, 'bold'), bg='#ecf0f1', fg='#2c3e50',
                                    relief=tk.GROOVE, bd=2)
        preview_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        preview_label = tk.Label(preview_frame, text="No timing sequences configured", 
                            font=('Courier', 10), bg='#ecf0f1', fg='#34495e',
                            justify=tk.LEFT, anchor="nw")
        preview_label.pack(fill=tk.BOTH, padx=20, pady=15)
        
        # Load existing configuration (simplified without channel selector)
        def load_initial_config():
            """Load default configuration"""
            # Create one default entry
            create_timing_entry_row(scrollable_frame)
            canvas.configure(scrollregion=canvas.bbox("all"))
            update_preview()
            update_add_button_state()
        
        # Professional Bottom buttons frame
        button_frame = tk.Frame(timing_window, bg='#2c3e50', height=70)
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        button_frame.pack_propagate(False)
        
        def apply_settings():
            """Apply timing settings with professional validation"""
            try:
                # Validate that at least one timing is enabled
                enabled_count = sum(1 for widget_set in timing_widgets 
                                if widget_set['enabled'].get())
                
                if enabled_count == 0:
                    messagebox.showwarning("Configuration vide", 
                                        "Veuillez activer au moins une séquence de timing")
                    return
                
                # Apply to all sensor configurations
                for channel_idx in range(4):
                    config = self.sensor_configs[channel_idx]
                    
                    # Create new timing entries
                    new_entries = []
                    for i, widget_set in enumerate(timing_widgets):
                        # Extract sensor number from "Sensor X" format
                        target_sensor_str = widget_set['target_sensor'].get()
                        sensor_num = int(target_sensor_str.split()[-1])
                        
                        entry = TimingEntry(
                            state=widget_set['enabled'].get(),
                            time_open_ms=int(widget_set['time_open'].get() or 100),
                            time_delay_ms=int(widget_set['time_delay'].get() or 50),
                            time_read_ms=int(widget_set['time_read'].get() or 10),
                            pin=sensor_num + 1,  # Convert to 1-based pin numbering
                            enabled=widget_set['enabled'].get(),
                            index=i + 1
                        )
                        new_entries.append(entry)
                    
                    config.timing_entries = new_entries
                
                # Update UI
                self.update_timing_status_display()
                
                messagebox.showinfo("Configuration appliquée", 
                                f"Configuration de timing appliquée avec succès.\n"
                                f"{enabled_count} séquence(s) active(s) configurée(s).")
                timing_window.destroy()
                
            except ValueError as e:
                messagebox.showerror("Erreur de validation", 
                                f"Valeurs d'entrée invalides: {str(e)}")
            except Exception as e:
                messagebox.showerror("Erreur", 
                                f"Échec de l'application des paramètres: {str(e)}")
        
        def reset_to_defaults():
            """Reset to default timing values with confirmation"""
            if messagebox.askyesno("Confirmer la réinitialisation", 
                                "Réinitialiser toutes les séquences aux valeurs par défaut?"):
                # Clear existing widgets
                for widget in scrollable_frame.winfo_children():
                    widget.destroy()
                timing_widgets.clear()
                global timing_count
                timing_count = 0
                
                load_initial_config()
        
        # Professional styled buttons
        button_style = {'font': ('Arial', 12, 'bold'), 'width': 14, 'height': 1, 
                    'relief': tk.FLAT, 'cursor': 'hand2'}
        
        tk.Button(button_frame, text="Apply Configuration", bg='#27ae60', fg='white', 
                command=apply_settings, **button_style).pack(side=tk.RIGHT, padx=15, pady=20)
        
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white', 
                command=timing_window.destroy, **button_style).pack(side=tk.RIGHT, padx=8, pady=20)
        
        tk.Button(button_frame, text="Reset Defaults", bg='#e67e22', fg='white', 
                command=reset_to_defaults, **button_style).pack(side=tk.LEFT, padx=15, pady=20)
        
        # Status indicator
        status_label = tk.Label(button_frame, text="Professional Timing Configuration System v2.0", 
                            font=('Arial', 9), fg='#bdc3c7', bg='#2c3e50')
        status_label.pack(side=tk.LEFT, padx=50, pady=20)
        
        # Load initial configuration
        load_initial_config()
    def export_data(self):
        """Export recorded data"""
        if not self.ble_manager.session_data:
            messagebox.showwarning("Warning", "No data to export.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Data"
        )
        
        if filename:
            try:
                if filename.endswith('.json'):
                    self.export_json(filename)
                else:
                    self.export_csv(filename)
                
                messagebox.showinfo("Success", f"Data exported successfully to {filename}")
                logger.info(f"Data exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")
                logger.error(f"Export failed: {e}")
    
    def export_csv(self, filename):
        """Export data to CSV format"""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['timestamp', 'datetime']
            for i in range(4):
                config = self.sensor_configs.get(i)
                real_header = f"{config.molecule_name}_({config.unit})"
                raw_header = f"{config.molecule_name}_raw"
                fieldnames.extend([real_header, raw_header])
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            
            for entry in self.ble_manager.session_data:
                row = {
                    'timestamp': str(entry['timestamp']).replace('.', ','),
                    'datetime': entry['datetime']
                }
                
                for sensor_id in range(4):
                    config = self.sensor_configs.get(sensor_id)
                    real_header = f"{config.molecule_name}_({config.unit})"
                    raw_header = f"{config.molecule_name}_raw"
                    
                    if sensor_id in entry['sensors']:
                        sensor_data = entry['sensors'][sensor_id]
                        row[real_header] = str(sensor_data['real']).replace('.', ',')
                        row[raw_header] = str(sensor_data['raw']).replace('.', ',')
                    else:
                        row[real_header] = ''
                        row[raw_header] = ''
                
                writer.writerow(row)
            logger.debug(f"Data exported to CSV: {filename}")
    
    def export_json(self, filename):
        """Export data to JSON format"""
        # Timing summary
        timing_summary = {}
        for sensor_id, config in self.sensor_configs.items():
            timing_summary[f"sensor_{sensor_id}"] = {
                "name": config.molecule_name,
                "unit": config.unit,
                "active_timing_index": config.active_timing_index,
                "timing_entries": [
                    {
                        "index": t.index,
                        "state": t.state,
                        "time_open_ms": t.time_open_ms,
                        "time_delay_ms": t.time_delay_ms,
                        "time_read_ms": t.time_read_ms,
                        "pin": t.pin,
                        "enabled": t.enabled,
                        "cycle_time_ms": t.cycle_time_ms,
                        "frequency_hz": round(t.frequency_hz, 2)
                    } for t in config.timing_entries
                ]
            }
        
        export_data = {
            'session_info': {
                'export_time': datetime.now().isoformat(),
                'total_records': len(self.ble_manager.session_data),
                'duration_seconds': self.ble_manager.session_data[-1]['timestamp'] - self.ble_manager.session_data[0]['timestamp'] if len(self.ble_manager.session_data) > 1 else 0
            },
            'timing_configurations': timing_summary,
            'sensor_data': self.ble_manager.session_data
        }
        
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
        logger.debug(f"Data exported to JSON: {filename}")
    
    def update_plot(self, frame):
        """Update plot with new data - Combined view with channel visibility"""
        if not self.is_recording:
            return self.lines.values()
        
        current_time = time.time()
        
        # Clear and redraw the combined plot
        self.ax.clear()
        self.ax.set_title('Combined Real-time mV Measurements', fontweight='bold')
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Voltage (mV)')
        self.ax.grid(True, alpha=0.3)
        self.ax.set_facecolor('#ffffff')
        
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12']
        
        # Plot only visible channels
        for channel in range(4):
            if self.channel_visibility[channel]:  # Only plot if channel is enabled
                data = self.ble_manager.data_channels[channel]
                if data:
                    times = [(d.received_time - current_time) for d in data]
                    voltages = [d.mv for d in data]
                    self.ax.plot(times, voltages, color=colors[channel], linewidth=2, 
                               label=f'Channel {channel}', alpha=0.8)
        
        # Update legend to show only visible channels
        visible_channels = [f'Channel {i}' for i in range(4) if self.channel_visibility[i]]
        if visible_channels:
            self.ax.legend(loc='upper left')
        
        return self.lines.values()
    
    def update_connection_ui(self):
        """Update UI when connection state changes"""
        if self.ble_manager.is_connected:
            self.connect_btn.configure(state=tk.DISABLED)
            self.disconnect_btn.configure(state=tk.NORMAL)
            self.start_btn.configure(state=tk.NORMAL)
            self.connection_var.set("Connected")
            self.connection_label.configure(foreground="#27ae60")
        else:
            self.connect_btn.configure(state=tk.NORMAL)
            self.disconnect_btn.configure(state=tk.DISABLED)
            self.start_btn.configure(state=tk.DISABLED)
            self.stop_btn.configure(state=tk.DISABLED)
            self.connection_var.set("Disconnected")
            self.connection_label.configure(foreground="#e74c3c")
            self.is_recording = False
    
    def on_data_received(self, sensor_data: SensorData):
        """Handle new sensor data"""
        # Update statistics in UI thread
        self.root.after(0, self.update_statistics, sensor_data)
        self.root.after(0, self.update_channel_display, sensor_data)


    def update_channel_display(self, sensor_data: SensorData):
        """Update channel button display with current values"""
        channel = sensor_data.channel
        if channel in self.channel_buttons:
            config = self.sensor_configs.get(channel)
            unit = config.unit if config else "mV"
            
            self.channel_buttons[channel]['value_display'].config(
                text=f"{sensor_data.mv:.2f} {unit}")
            self.channel_buttons[channel]['raw_display'].config(
                text=f"{sensor_data.value}")
    
    def update_statistics(self, sensor_data: SensorData):
        """Update statistics display"""
        channel = sensor_data.channel
        data = self.ble_manager.data_channels[channel]
        
        if data:
            voltages = [d.mv for d in data]
            current = sensor_data.mv
            min_val = min(voltages)
            max_val = max(voltages)
            avg_val = sum(voltages) / len(voltages)
            count = len(voltages)
            
            self.stats_tree.item(f'ch{channel}', 
                               values=(f'Channel {channel}', 
                                     f'{current:.2f}', 
                                     f'{min_val:.2f}', 
                                     f'{max_val:.2f}', 
                                     f'{avg_val:.2f}', 
                                     count))
    
    def on_connection_changed(self, connected: bool):
        """Handle connection state change"""
        self.root.after(0, self.update_connection_ui)
    
    def on_message(self, message: str):
        """Handle log message"""
        self.root.after(0, self.append_log, message)
    
    def append_log(self, message: str):
        """Append message to log"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
    
    def run(self):
        """Run the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Center window on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        self.root.mainloop()
    
    def on_closing(self):
        """Handle application closing"""
        if self.is_recording:
            if messagebox.askyesno("Confirm Exit", 
                                 "Recording is still in progress. Stop and exit?"):
                self.is_recording = False
                if self.animation:
                    self.animation.event_source.stop()
            else:
                return
        
        if self.ble_manager.is_connected:
            self.run_async(self.ble_manager.disconnect())
            time.sleep(0.5)  # Give time for disconnection
        
        if self.event_loop:
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)
        
        logger.info("Application shutting down")
        self.root.destroy()

def main():
    try:
        app = BLEDataAcquisitionGUI()
        app.run()
        
    except Exception as e:
        logger.critical(f"Application failed to start: {e}", exc_info=True)
        messagebox.showerror("Critical Error", 
                           f"Application failed to start:\n{str(e)}")

if __name__ == "__main__":
    main()