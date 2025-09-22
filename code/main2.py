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
NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Characteristic UUID for writing data


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
    brightness: int = 40
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

    # Calibration metadata
    is_calibrated: bool = False
    calibration_function_formula: str = ""
    calibration_r_squared: float = 0.0
    calibration_date: str = ""

    def __post_init__(self):
        if self.timing_entries is None:
            self.timing_entries = [TimingEntry(on_time_ms=100, off_time_ms=900, enabled=False, index=1)]
        if self.calibration_points is None:
            self.calibration_points = []

    def apply_calibration(self, raw_value: float) -> float:
        """Apply calibration function to convert raw value to real concentration"""
        if not self.is_calibrated or not self.calibration_coeffs:
            return raw_value
        
        try:
            # Polynomial calibration: y = a*x^2 + b*x + c
            if len(self.calibration_coeffs) >= 2:
                a, b = self.calibration_coeffs[:2]
                c = self.calibration_coeffs[2] if len(self.calibration_coeffs) > 2 else 0
                return a * raw_value * raw_value + b * raw_value + c
            return raw_value
        except Exception:
            return raw_value

class BLEDataManager:
    """Manages BLE communication and data handling - Optimized for real-time"""
    
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.device = None
        self.is_connected = False
        self.is_scanning = False
        self.recv_buffer = ""
        self.led_isolation_mode = False
        self.current_active_led = None  # Track currently active LED for isolation
        self.system_state = True 
        self.last_applied_timing_config = None
        self.calibration_callback: Optional[Callable] = None


        # Initialize message sending variables (add this before setup_gui())
        self.message_entry = None
        self.send_message_btn = None
        self.send_status_var = None
        self.send_status_label = None

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
        """Process parsed JSON message with LED-specific data isolation"""
        if not isinstance(parsed, list):
            self._log_message(f"Warning: Expected list, got {type(parsed)}")
            return
            
        # NOUVEAU: Détecter le format calibration [channel, value]
        if isinstance(parsed, list) and len(parsed) == 2 and all(isinstance(x, (int, float)) for x in parsed):
            # Format calibration: [channel, raw_value]
            channel = int(parsed[0])
            raw_value = int(parsed[1])
            
            # Créer un SensorData pour le mode calibration
            sensor_data = SensorData(
                unit="mV",
                timestamp=int(receive_timestamp * 1000),
                mv=float(raw_value),  # En mode calibration, utiliser raw_value comme mv
                value=raw_value,
                channel=channel,
                received_time=receive_timestamp
            )
            
            # Traitement spécial pour la calibration
            with self.data_lock:
                self.data_channels[channel].append(sensor_data)
            
            # Callbacks
            if self.on_data_received:
                self.on_data_received(sensor_data)
            
            if self.calibration_callback:
                self.calibration_callback(sensor_data)
                
            return
        
        if len(parsed) != 4:
            self._log_message(f"Warning: Expected 4 channels, got {len(parsed)}")
        
        # Performance tracking
        self.data_receive_count += 1
        
        # Check if this is LED-isolated data
        led_isolation_enabled = hasattr(self, 'led_isolation_mode') and self.led_isolation_mode
        current_active_led = getattr(self, 'current_active_led', None)
        
        # Session data entry with LED isolation support
        session_entry = {
            'timestamp': receive_timestamp,
            'datetime': datetime.now().isoformat(),
            'sensors': {},
            'active_led': current_active_led,  # Track which LED was active
            'isolation_mode': led_isolation_enabled
        }
        
        # Process each channel with LED-specific filtering
        with self.data_lock:
            for channel, data in enumerate(parsed[:4]):
                if isinstance(data, list) and len(data) >= 4:
                    
                    # LED isolation logic - only process data if from correct LED
                    # if led_isolation_enabled and current_active_led is not None:
                    #     # Only process data if it matches the currently active LED
                    #     expected_led_pin = current_active_led
                    #     sensor_config = getattr(self, 'sensor_configs', {}).get(channel)
                        
                    #     if sensor_config:
                    #         # Check if this channel's timing entries match the active LED
                    #         channel_led_pins = [t.pin for t in sensor_config.timing_entries if t.enabled]
                    #         if expected_led_pin not in channel_led_pins:
                    #             continue  # Skip data from non-active LEDs
                    
                    sensor_data = SensorData(
                        unit=data[0],
                        timestamp=data[1],
                        mv=float(data[2]),
                        value=int(data[3]),
                        channel=channel,
                        received_time=receive_timestamp
                    )
                    
                    # # Add LED isolation metadata
                    # if led_isolation_enabled:
                    #     sensor_data.source_led = current_active_led
                    #     sensor_data.isolated = True
                    
                    self.data_channels[channel].append(sensor_data)
                    
                    # Add to session data
                    session_entry['sensors'][channel] = {
                        'raw': sensor_data.value,
                        'real': sensor_data.mv,
                        'source_led': getattr(sensor_data, 'source_led', None),
                        'isolated': getattr(sensor_data, 'isolated', False)
                    }
                    
                    # Immediate callback for real-time update
                    if self.on_data_received:
                        self.on_data_received(sensor_data)

                    if self.calibration_callback:
                        self.calibration_callback(sensor_data)
        
        # Store session data only if there's actual sensor data
        if session_entry['sensors']:
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
                    any(keyword in name for keyword in ["bluefruit", "feather", "json_sender", "nrf", "genc"])):
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
    
    async def send_timing_config(self, config_data):
        """Send timing configuration to nRF52840 with professional sequencing"""
        if not self.client or not self.is_connected:
            raise Exception("Device not connected")
        
        try:
            # Add professional timing control for sequential LED operation
            simplified_config = {
               
                "sequences": config_data.get("sequences", []),
                # "timing_control": {
                #     "inter_led_delay_ms": 5000,  # 5 seconds between different LEDs
                #     "sequence_mode": "sequential",  # Sequential operation mode
                #     "led_isolation": True,  # Each LED operates independently
                #     "data_filtering": True  # Filter data by active LED only
                # }
            }
            
            # Sort sequences by LED pin for consistent ordering
            # try:
            #     enhanced_config["sequences"] = sorted(
            #         enhanced_config["sequences"], 
            #         key=lambda x: int(x.get("pin", 0))  # Convertir explicitement en int
            #     )
            #     logger.debug(f"Sequences sorted by LED pin: {[seq.get('pin') for seq in enhanced_config['sequences']]}")
            # except (ValueError, TypeError) as e:
            #     logger.warning(f"Could not sort sequences by LED pin: {e}")
            
            # # Add sequence timing metadata
            # for i, sequence in enumerate(enhanced_config["sequences"]):
            #     sequence["sequence_index"] = i
            #     sequence["delay_before_ms"] = i * 5000  # 5s delay between LEDs
            #     sequence["data_isolation"] = True  # Only show data for this LED

            # Format the simplified configuration as JSON
            config_json = json.dumps(simplified_config, separators=(',', ':'))
            config_message = config_json + '\n'  # Ajouter newline à la fin
            config_bytes = config_message.encode('utf-8')

            # Professional chunked transmission with acknowledgment
            max_chunk_size = 20
            total_chunks = (len(config_bytes) + max_chunk_size - 1) // max_chunk_size
            
            self._log_message(f"Sending timing config: {total_chunks} chunks, {len(config_bytes)} bytes")
            
            for i in range(0, len(config_bytes), max_chunk_size):
                chunk = config_bytes[i:i + max_chunk_size]
               # chunk_num = (i // max_chunk_size) + 1
                
                await self.client.write_gatt_char(NUS_RX, chunk)
                await asyncio.sleep(0.05)  # Increased delay for reliability
                
                # Progress indication for large configs
                # if total_chunks > 5:
                #     self._log_message(f"Progress: {chunk_num}/{total_chunks} chunks sent")
            
            # Send end marker with timing control flag
            # CORRECTION CRITIQUE : Envoyer un newline pour terminer le JSON
            # CORRECTION CRITIQUE : Envoyer un newline pour terminer le JSON
            newline_bytes = b'\n'
            await self.client.write_gatt_char(NUS_RX, newline_bytes)
            await asyncio.sleep(0.2)  # Ensure processing time

            # Optionnel : envoyer un marqueur de fin explicite
            end_marker = b'END_CONFIG\n'
            await self.client.write_gatt_char(NUS_RX, end_marker)
            await asyncio.sleep(0.05)
            
            self._log_message("Enhanced timing configuration sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send enhanced timing config: {e}")
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
    
    async def send_message(self, message: str):
        """Send a text message to the nRF52840 device"""
        if not self.client or not self.is_connected:
            raise Exception("Device not connected")
        
        try:
            # Prepare message with timestamp
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            formatted_message = f"[{timestamp}] {message}"
            
            # Convert to bytes
            message_bytes = formatted_message.encode('utf-8')
            
            # Send in chunks if message is too long
            max_chunk_size = 20
            total_chunks = (len(message_bytes) + max_chunk_size - 1) // max_chunk_size
            
            self._log_message(f"Sending message: '{message}' ({len(message_bytes)} bytes)")
            
            for i in range(0, len(message_bytes), max_chunk_size):
                chunk = message_bytes[i:i + max_chunk_size]
                await self.client.write_gatt_char(NUS_RX, chunk)
                await asyncio.sleep(0.02)  # Small delay between chunks
            
            # Send end marker
            await self.client.write_gatt_char(NUS_RX, b'\n')
            await asyncio.sleep(0.05)
            
            self._log_message(f"Message sent successfully to nRF52840")
            return True
            
        except Exception as e:
            self._log_message(f"Failed to send message: {e}")
            return False

    async def send_state_update(self, state: bool):
        """Send system state update to nRF52840"""
        if not self.client or not self.is_connected:
            raise Exception("Device not connected")
        
        try:
            state_data = {
                "state": state,
            }
            
            config_json = json.dumps(state_data, separators=(',', ':'))
            config_message = config_json + '\n'
            config_bytes = config_message.encode('utf-8')
            
            # send in chunks
            max_chunk_size = 20
            for i in range(0, len(config_bytes), max_chunk_size):
                chunk = config_bytes[i:i + max_chunk_size]
                await self.client.write_gatt_char(NUS_RX, chunk)
                await asyncio.sleep(0.02)

            # End marker
            await self.client.write_gatt_char(NUS_RX, b'\n')
            await asyncio.sleep(0.05)
            
            self._log_message(f"System state sent: {'ON' if state else 'OFF'}")
            return True
            
        except Exception as e:
            self._log_message(f"Failed to send state: {e}")
            return False

    async def send_calibration_config(self, config_data):
        """Send calibration configuration to nRF52840"""
        if not self.client or not self.is_connected:
            raise Exception("Device not connected")
        
        try:
            # Format the calibration configuration as JSON
            config_json = json.dumps(config_data, separators=(',', ':'))
            config_message = config_json + '\n'
            config_bytes = config_message.encode('utf-8')

            # Send in chunks if needed
            max_chunk_size = 20
            total_chunks = (len(config_bytes) + max_chunk_size - 1) // max_chunk_size
            
            self._log_message(f"Sending calibration config: {total_chunks} chunks, {len(config_bytes)} bytes")
            
            for i in range(0, len(config_bytes), max_chunk_size):
                chunk = config_bytes[i:i + max_chunk_size]
                await self.client.write_gatt_char(NUS_RX, chunk)
                await asyncio.sleep(0.05)
            
            # Send end marker
            newline_bytes = b'\n'
            await self.client.write_gatt_char(NUS_RX, newline_bytes)
            await asyncio.sleep(0.1)
            
            self._log_message("Calibration configuration sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send calibration config: {e}")
            return False

    def clear_data(self):
        """Clear all stored data"""
        with self.data_lock:
            for channel in self.data_channels.values():
                channel.clear()
        self.session_data.clear()
        self.data_receive_count = 0

    def update_led_isolation_mode(self, led_pin, enabled=True):
        """Update LED isolation mode for data filtering"""
        self.led_isolation_mode = enabled
        self.current_active_led = led_pin if enabled else None
        
        if enabled:
            self._log_message(f"LED isolation enabled: Only LED {led_pin} data will be processed")
        else:
            self._log_message("LED isolation disabled: All LED data will be processed")

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
        
        # Stop button
        self.stop_btn = tk.Button(control_frame, text="STOP", bg='#e74c3c', fg='white',
                                command=self.stop_recording, state=tk.DISABLED, **button_style)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Configuration controls
        self.timing_btn = tk.Button(control_frame, text="TIMING", bg='#f39c12', fg='white',
                                   command=self.open_timing_config, **button_style)
        self.timing_btn.pack(side=tk.LEFT, padx=5)
        
        # Calibration controls
        self.calibration_btn = tk.Button(control_frame, text="CALIBRATION", bg='#16a085', fg='white',
                                   command=self.open_calibration_panel, **button_style)
        self.calibration_btn.pack(side=tk.LEFT, padx=5)

        # Data export and clear  
        self.export_btn = tk.Button(control_frame, text="EXPORT", bg='#8e44ad', fg='white',
                                  command=self.export_data, state=tk.DISABLED, **button_style)
        self.export_btn.pack(side=tk.LEFT, padx=5)
        
        # Clear button
        self.clear_btn = tk.Button(control_frame, text="CLEAR", bg='#e67e22', fg='white',
                                 command=self.clear_data, **button_style)
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        # State control
        self.state_btn = tk.Button(control_frame, text="STATE ON", bg='#1abc9c', fg='white',
                             command=self.toggle_state, state=tk.DISABLED, **button_style)
        self.state_btn.pack(side=tk.LEFT, padx=5)
        
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
        # Create main frame for log
        log_main_frame = tk.Frame(parent, bg='#ecf0f1')
        log_main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Log display area
        log_display_frame = tk.Frame(log_main_frame, bg='#ecf0f1')
        log_display_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.log_text = scrolledtext.ScrolledText(
            log_display_frame, 
            height=15, 
            width=80,
            font=('Consolas', 9),
            bg='#2c3e50',
            fg='#ecf0f1',
            insertbackground='#3498db',
            selectbackground='#34495e'
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Message sending frame
        send_frame = tk.LabelFrame(
            log_main_frame, 
            text="Send Message to nRF52840", 
            font=('Arial', 10, 'bold'),
            bg='#ecf0f1',
            fg='#2c3e50'
        )
        send_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Input frame
        input_frame = tk.Frame(send_frame, bg='#ecf0f1')
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Message entry
        tk.Label(input_frame, text="Message:", font=('Arial', 10), 
                bg='#ecf0f1', fg='#2c3e50').pack(side=tk.LEFT, padx=(0, 5))
        
        self.message_entry = tk.Entry(
            input_frame, 
            font=('Arial', 10), 
            width=60,
            bg='white',
            fg='#2c3e50'
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Send button
        self.send_message_btn = tk.Button(
            input_frame,
            text="SEND",
            font=('Arial', 10, 'bold'),
            bg='#3498db',
            fg='white',
            width=10,
            command=self.send_message_to_device,
            state=tk.DISABLED  # Initially disabled
        )
        self.send_message_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Bind Enter key to send message
        self.message_entry.bind('<Return>', lambda event: self.send_message_to_device())
        
        # Status indicator
        status_frame = tk.Frame(send_frame, bg='#ecf0f1')
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.send_status_var = tk.StringVar(value="Ready to send messages (device must be connected)")
        self.send_status_label = tk.Label(
            status_frame,
            textvariable=self.send_status_var,
            font=('Arial', 9, 'italic'),
            bg='#ecf0f1',
            fg='#7f8c8d'
        )
        self.send_status_label.pack(anchor=tk.W)
    
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
        """Open professional timing configuration window """
        timing_window = tk.Toplevel(self.root)
        timing_window.title("LED Sequential Timing Configuration - Professional")
        timing_window.geometry("1200x900")
        timing_window.configure(bg='#2c3e50')
        timing_window.transient(self.root)
        timing_window.grab_set()
        
        # Center window
        timing_window.update_idletasks()
        x = (timing_window.winfo_screenwidth() // 2) - 600
        y = (timing_window.winfo_screenheight() // 2) - 450
        timing_window.geometry(f"1200x900+{x}+{y}")

        # VARIABLES DÉFINIES EN PREMIER
        timing_widgets = []
        timing_count = [0]
        MAX_TIMING_ENTRIES = 4

        # Header avec bouton Add Timing intégré
        header_frame = tk.Frame(timing_window, bg='#34495e', height=70)
        header_frame.pack(fill=tk.X, padx=15, pady=15)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="LED Sequential Timing Configuration", 
                            font=('Arial', 18, 'bold'), fg='white', bg='#34495e')
        title_label.pack(side=tk.LEFT, padx=25, pady=20)
        
        # NOUVEAU: Bouton Add Timing dans le header (côté gauche)
        add_btn = tk.Button(header_frame, text=f"+ Add Timing (0/{MAX_TIMING_ENTRIES})", 
                        bg='#27ae60', fg='white', font=('Arial', 12, 'bold'), 
                        width=25, height=1)
        add_btn.pack(side=tk.LEFT, padx=50, pady=20)
        
        # Main content
        main_frame = tk.Frame(timing_window, bg='#ecf0f1', relief=tk.RAISED, bd=1)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        config_frame = tk.LabelFrame(main_frame, text="Timing Sequences Configuration", 
                                    font=('Arial', 14, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        config_frame.pack(fill=tk.X, expand=True, padx=15, pady=15)
        
        # Create timing entries table - ÉTENDU POUR PRENDRE TOUTE LA PLACE
        timing_entries_frame = tk.Frame(config_frame, bg='#ecf0f1')
        timing_entries_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Headers avec largeurs adaptées à la fenêtre complète
        headers = ["Enable", "Time Open (ms)", "Time Delay (ms)", "Time Read (ms)", "Target LED", "Brightness", "Actions"]
        header_frame = tk.Frame(timing_entries_frame, bg='#34495e', relief=tk.RAISED, bd=1)
        header_frame.pack(fill=tk.BOTH, pady=(0, 6))

        # Créer chaque header dans un frame proportionnel
        for header in headers:
            header_label_frame = tk.Frame(header_frame, bg='#34495e')
            header_label_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            
            label = tk.Label(header_label_frame, text=header, font=('Arial', 11, 'bold'), 
                            fg='white', bg='#34495e', pady=8)
            label.pack(fill=tk.BOTH, expand=True)
        
        # Scrollable frame - HAUTEUR ÉTENDUE
        canvas = tk.Canvas(timing_entries_frame, bg='#ecf0f1')
        scrollbar = ttk.Scrollbar(timing_entries_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#ecf0f1')
        
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Variables et fonctions (reste du code existant...)
        timing_widgets = []
        timing_count = [0]
        MAX_TIMING_ENTRIES = 4

        def create_timing_entry_row(parent, entry_data=None):
            """Création de ligne avec widgets proportionnels aux headers"""
            if timing_count[0] >= MAX_TIMING_ENTRIES:
                messagebox.showwarning("Limite atteinte", 
                                    f"Maximum {MAX_TIMING_ENTRIES} séquences autorisées")
                return None
            
            row_color = '#ffffff' if timing_count[0] % 2 == 0 else '#f8f9fa'
            row_frame = tk.Frame(parent, bg=row_color, relief=tk.SOLID, bd=1)
            row_frame.pack(fill=tk.X, pady=3, padx=2)
            
            widgets = {
                'row_frame': row_frame,
                'entry_index': timing_count[0]
            }
            
            # 1. Enable - Frame proportionnel
            enable_frame = tk.Frame(row_frame, bg=row_color)
            enable_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            enable_var = tk.BooleanVar(value=entry_data.enabled if entry_data else True)
            enable_check = tk.Checkbutton(enable_frame, variable=enable_var, bg=row_color, 
                                        font=('Arial', 10), activebackground=row_color)
            enable_check.pack(anchor=tk.CENTER, pady=12)
            widgets['enabled'] = enable_var
            
            # 2. Time Open - Frame proportionnel
            time_open_frame = tk.Frame(row_frame, bg=row_color)
            time_open_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            time_open_var = tk.StringVar(value=str(entry_data.time_open_ms if entry_data else 100))
            time_open_entry = tk.Entry(time_open_frame, textvariable=time_open_var, 
                                    font=('Arial', 10), justify=tk.CENTER)
            time_open_entry.pack(fill=tk.X, pady=10, padx=3)
            widgets['time_open_ms'] = time_open_var
            
            # 3. Time Delay - Frame proportionnel
            time_delay_frame = tk.Frame(row_frame, bg=row_color)
            time_delay_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            time_delay_var = tk.StringVar(value=str(entry_data.time_delay_ms if entry_data else 50))
            time_delay_entry = tk.Entry(time_delay_frame, textvariable=time_delay_var, 
                                    font=('Arial', 10), justify=tk.CENTER)
            time_delay_entry.pack(fill=tk.X, pady=10, padx=3)
            widgets['time_delay_ms'] = time_delay_var
            
            # 4. Time Read - Frame proportionnel
            time_read_frame = tk.Frame(row_frame, bg=row_color)
            time_read_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            time_read_var = tk.StringVar(value=str(entry_data.time_read_ms if entry_data else 10))
            time_read_entry = tk.Entry(time_read_frame, textvariable=time_read_var, 
                                    font=('Arial', 10), justify=tk.CENTER)
            time_read_entry.pack(fill=tk.X, pady=10, padx=3)
            widgets['time_read_ms'] = time_read_var
            
            # 5. LED Selection - Frame proportionnel
            led_frame = tk.Frame(row_frame, bg=row_color)
            led_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            led_pin_var = tk.IntVar(value=entry_data.pin if entry_data else 1)
            led_combo = ttk.Combobox(led_frame, values=[1, 2, 3, 4], state="readonly", 
                                    font=('Arial', 10))
            led_combo.set(str(led_pin_var.get()))
            led_combo.pack(fill=tk.X, pady=10, padx=3)
            widgets['pin'] = led_pin_var

            # 6. Brightness - Frame proportionnel
            brightness_frame = tk.Frame(row_frame, bg=row_color)
            brightness_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            brightness_var = tk.IntVar(value=entry_data.brightness if entry_data else 100)
            brightness_entry = tk.Spinbox(brightness_frame, from_=0, to=100,
                                textvariable=brightness_var, font=('Arial', 10), justify=tk.CENTER)
            brightness_entry.pack(fill=tk.X, pady=10, padx=3)
            widgets['brightness'] = brightness_var

            # 7. Actions - Frame proportionnel
            action_frame = tk.Frame(row_frame, bg=row_color)
            action_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1)
            
            def remove_entry():
                row_frame.destroy()
                timing_widgets.remove(widgets)
                timing_count[0] -= 1
                update_preview()
                update_add_button_state()
            
            remove_btn = tk.Button(action_frame, text="Remove", bg='#e74c3c', fg='white', 
                                font=('Arial', 9, 'bold'), command=remove_entry)
            remove_btn.pack(fill=tk.X, pady=10, padx=3)
            
            
            # Synchronisation LED combo avec variable
            def on_led_change(event=None):
                try:
                    selected = int(led_combo.get())
                    led_pin_var.set(selected)
                    update_preview()
                except ValueError:
                    led_pin_var.set(1)

            led_combo.bind('<<ComboboxSelected>>', on_led_change)
            
            # Validation functions (reste identique...)
            def validate_and_update(*args):
                try:
                    for key in ['time_open_ms', 'time_delay_ms', 'time_read_ms']:
                        var = widgets[key]
                        value = var.get()
                        if value and not value.isdigit():
                            var.set(''.join(filter(str.isdigit, value)))
                        elif value:
                            val = int(value)
                            if val < 1: var.set('1')
                            elif val > 10000: var.set('10000')
                    update_preview()
                except Exception as e:
                    print(f"Validation error: {e}")
            
            # Attacher les validations
            for key in ['time_open_ms', 'time_delay_ms', 'time_read_ms']:
                widgets[key].trace('w', validate_and_update)
            enable_var.trace('w', lambda *args: update_preview())
            led_pin_var.trace('w', lambda *args: update_preview())
            brightness_var.trace('w', lambda *args: update_preview())
            
            timing_widgets.append(widgets)
            timing_count[0] += 1
            update_add_button_state()
            return widgets

        def update_add_button_state():
            """Mise à jour état bouton Add dans le header"""
            if timing_count[0] >= MAX_TIMING_ENTRIES:
                add_btn.config(state=tk.DISABLED, text=f"Maximum {MAX_TIMING_ENTRIES} Timings", bg='#95a5a6')
            else:
                add_btn.config(state=tk.NORMAL, text=f"+ Add Timing ({timing_count[0]}/{MAX_TIMING_ENTRIES})", bg='#27ae60')

        def add_timing_entry():
            """Ajouter nouvelle entrée timing"""
            if timing_count[0] < MAX_TIMING_ENTRIES:
                create_timing_entry_row(scrollable_frame)
                canvas.configure(scrollregion=canvas.bbox("all"))
                update_preview()


        add_btn.config(command=add_timing_entry)

        # Preview frame - TAILLE RÉDUITE pour compenser l'extension de la liste
        preview_frame = tk.LabelFrame(main_frame, text="Configuration Preview", 
                                    font=('Arial', 12, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        preview_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        preview_label = tk.Label(preview_frame, text="No timing sequences configured", 
                            font=('Courier', 9), bg='#ecf0f1', fg='#34495e',  # Police réduite
                            justify=tk.LEFT, anchor="nw")
        preview_label.pack(fill=tk.BOTH, padx=15, pady=10)

        # Bouton Add Entry
        add_btn_frame = tk.Frame(timing_entries_frame, bg='#ecf0f1')
        add_btn_frame.pack(fill=tk.X, pady=12)
        

        def update_preview():
            """Mise à jour aperçu avec calculs professionnels"""
            try:
                total_time = 0
                active_entries = 0
                led_distribution = {f"LED {i}": 0 for i in range(1, 5)}
                
                for widget_set in timing_widgets:
                    if widget_set['enabled'].get():
                        time_open = int(widget_set['time_open_ms'].get() or 0)
                        time_delay = int(widget_set['time_delay_ms'].get() or 0)
                        time_read = int(widget_set['time_read_ms'].get() or 0)
                        led_pin = widget_set['pin'].get()
                        
                        cycle_time = time_open + time_delay + time_read + 10
                        total_time += cycle_time
                        active_entries += 1
                        led_distribution[f"LED {led_pin}"] += 1
                
                frequency = 1000.0 / total_time if total_time > 0 else 0
                
                preview_text = f"Configuration Summary:\n"
                preview_text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                preview_text += f"Active Sequences: {active_entries}/{MAX_TIMING_ENTRIES}\n"
                preview_text += f"Total Cycle Time: {total_time} ms\n"
                preview_text += f"System Frequency: {frequency:.2f} Hz\n\n"
                
                preview_text += "LED Distribution:\n"
                for led, count in led_distribution.items():
                    if count > 0:
                        preview_text += f"  • {led}: {count} sequence(s)\n"
                
                if active_entries == 0:
                    preview_text = "No active timing sequences configured"
                
                preview_label.config(text=preview_text)
                
            except Exception as e:
                preview_label.config(text=f"⚠ Configuration Error: {e}")
                print(f"Preview update error: {e}")

        def load_initial_config():
            """Charger configuration initiale avec priorités"""
            loaded_any = False

            """Charger configuration par défaut"""
            if hasattr(self, 'last_applied_timing_config') and self.last_applied_timing_config:
                self.on_message("Loading last applied timing configuration...")
                for timing_entry in self.last_applied_timing_config:
                    create_timing_entry_row(scrollable_frame, timing_entry)
                    loaded_any = True
            
            # PRIORITÉ 2: Charger depuis les sensor_configs existants
            elif any(config.timing_entries for config in self.sensor_configs.values()):
                # Collecter toutes les entrées uniques
                unique_entries = {}
                for sensor_id, config in self.sensor_configs.items():
                    if config.timing_entries:
                        for timing_entry in config.timing_entries:
                            entry_key = (timing_entry.pin, timing_entry.time_open_ms, 
                                        timing_entry.time_delay_ms, timing_entry.time_read_ms, 
                                        timing_entry.brightness, timing_entry.enabled)
                            if entry_key not in unique_entries:
                                unique_entries[entry_key] = timing_entry
                
                for timing_entry in unique_entries.values():
                    create_timing_entry_row(scrollable_frame, timing_entry)
                    loaded_any = True
            
            # PRIORITÉ 3: Configuration par défaut si rien n'existe
            if not loaded_any:
                self.on_message("Loading default timing configuration...")
                default_entry = TimingEntry(
                    state=True,
                    time_open_ms=100,
                    time_delay_ms=50, 
                    time_read_ms=10,
                    brightness=100,
                    pin=1,
                    enabled=True,
                    index=1
                )
                create_timing_entry_row(scrollable_frame, default_entry)
            
            canvas.configure(scrollregion=canvas.bbox("all"))
            update_preview()
            update_add_button_state()

        # SOLUTION PROFESSIONNELLE: Fonction apply_settings corrigée
        # def debug_widget_structure(widgets_dict, entry_index):
        #     """Fonction de debug professionnelle pour identifier la structure des données"""
        #     print(f"\n=== DEBUG WIDGET STRUCTURE - Entry {entry_index} ===")
        #     print(f"Keys available: {list(widgets_dict.keys())}")
        #     for key, value in widgets_dict.items():
        #         try:
        #             if hasattr(value, 'get'):
        #                 print(f"{key}: {value.get()}")
        #             else:
        #                 print(f"{key}: {value}")
        #         except Exception as e:
        #             print(f"{key}: ERROR - {e}")
        #     print("=" * 50)

        def apply_settings():
            """FONCTION CORRIGÉE PROFESSIONNELLEMENT"""
            try:
                print("\n=== DÉBUT DEBUG APPLY_SETTINGS ===")
                
                enabled_count = sum(1 for widget_set in timing_widgets if widget_set['enabled'].get())
                
                if enabled_count == 0:
                    messagebox.showwarning("Empty Configuration", 
                                        "Please enable at least one timing sequence")
                    return
                
                # NOUVEAU: Sauvegarder dans une structure globale pour persistence
                saved_timing_entries = []
                
                # Apply to sensor configurations ET sauvegarder globalement
                for channel_idx in range(4):
                    config = self.sensor_configs[channel_idx]
                    new_entries = []
                    
                    for i, widget_set in enumerate(timing_widgets):
                        try:
                            enabled = widget_set['enabled'].get()
                            time_open = int(widget_set['time_open_ms'].get() or 100)
                            time_delay = int(widget_set['time_delay_ms'].get() or 50) 
                            time_read = int(widget_set['time_read_ms'].get() or 10)
                            led_pin = int(widget_set['pin'].get())
                            brightness = int(widget_set['brightness'].get())
                            
                            entry = TimingEntry(
                                state=enabled,
                                time_open_ms=time_open,
                                time_delay_ms=time_delay,
                                time_read_ms=time_read,
                                brightness=brightness,
                                pin=led_pin,
                                enabled=enabled,
                                index=i + 1
                            )
                            new_entries.append(entry)
                            
                            # NOUVEAU: Ajouter à la sauvegarde globale (éviter les doublons)
                            entry_key = (led_pin, time_open, time_delay, time_read, brightness, enabled)
                            if entry_key not in [
                                (e.pin, e.time_open_ms, e.time_delay_ms, e.time_read_ms, e.brightness, e.enabled) 
                                for e in saved_timing_entries
                            ]:
                                saved_timing_entries.append(entry)
                            
                        except Exception as e:
                            print(f"Error entry {i}: {e}")
                            raise
                    
                    config.timing_entries = new_entries
                
                # NOUVEAU: Sauvegarder dans une variable de classe pour la persistence
                self.last_applied_timing_config = saved_timing_entries
                
                self.update_timing_status_display()
                
                messagebox.showinfo("Configuration Applied", 
                                f"Timing configuration applied successfully.\n"
                                f"{enabled_count} active sequence(s) configured.")
                
                if messagebox.askyesno("Send to device?", 
                        "Configuration applied locally. Do you want to send it to the nRF52840?"):
                    self.send_timing_to_device()

                timing_window.destroy()
                
            except Exception as e:
                print(f"Erreur apply_settings: {e}")
                import traceback
                traceback.print_exc()
                messagebox.showerror("Error", f"Failed to apply settings: {str(e)}")

        def reset_to_defaults():
            """Reset to default values"""
            if messagebox.askyesno("Confirm Reset", 
                                "Reset all sequences to default values?"):
                for widget in scrollable_frame.winfo_children():
                    widget.destroy()
                timing_widgets.clear()
                timing_count[0] = 0
                load_initial_config()
                update_add_button_state()

        # Boutons
        button_frame = tk.Frame(timing_window, bg='#2c3e50', height=70)
        button_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        button_frame.pack_propagate(False)
        
        button_style = {'font': ('Arial', 12, 'bold'), 'width': 14, 'height': 1}
        
        tk.Button(button_frame, text="Apply Configuration", bg='#27ae60', fg='white', 
                command=apply_settings, **button_style).pack(side=tk.RIGHT, padx=15, pady=20)
        
        tk.Button(button_frame, text="Cancel", bg='#95a5a6', fg='white', 
                command=timing_window.destroy, **button_style).pack(side=tk.RIGHT, padx=8, pady=20)
        
        tk.Button(button_frame, text="Reset Defaults", bg='#e67e22', fg='white', 
                command=reset_to_defaults, **button_style).pack(side=tk.LEFT, padx=15, pady=20)
        
        status_label = tk.Label(button_frame, text="Professional Timing Configuration System v2.0", 
                            font=('Arial', 9), fg='#bdc3c7', bg='#2c3e50')
        status_label.pack(side=tk.LEFT, padx=50, pady=20)
        
        # Charger configuration initiale
        load_initial_config()

    def open_calibration_panel(self):
        """Open professional calibration panel for all sensors"""
        cal_window = tk.Toplevel(self.root)
        cal_window.title("Professional Calibration System")
        cal_window.geometry("1400x900")
        cal_window.configure(bg='#ecf0f1')
        cal_window.transient(self.root)
        cal_window.grab_set()
        
        # Center window
        cal_window.update_idletasks()
        x = (cal_window.winfo_screenwidth() // 2) - 700
        y = (cal_window.winfo_screenheight() // 2) - 450
        cal_window.geometry(f"1400x900+{x}+{y}")
        
        # Variables for calibration state
        selected_sensor = tk.IntVar(value=0)
        current_calibration_points = {i: [] for i in range(4)}
        current_reading_var = tk.StringVar(value="0.00")

        self._current_reading_var = current_reading_var
        concentration_entry_var = tk.StringVar()
        molecule_name_var = tk.StringVar()
        unit_var = tk.StringVar()
        calibration_status = tk.StringVar(value="Ready for calibration")
        
        # Header
        header_frame = tk.Frame(cal_window, bg='#2c3e50', height=80)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(header_frame, text="Professional Calibration Panel", 
                            font=('Arial', 24, 'bold'), fg='white', bg='#2c3e50')
        title_label.pack(pady=20)
        
        # Main container
        main_container = tk.Frame(cal_window, bg='#ecf0f1')
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Left panel - Sensor selection and configuration
        left_panel = tk.LabelFrame(main_container, text="Sensor Selection & Configuration", 
                                font=('Arial', 14, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Sensor selection
        sensor_frame = tk.LabelFrame(left_panel, text="Choose Sensor:", 
                                    font=('Arial', 12, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        sensor_frame.pack(fill=tk.X, padx=15, pady=15)
        
        sensor_checkboxes = {}
        sensor_status_labels = {}
        
        def on_sensor_select(sensor_id):
            """Handle sensor selection and activate calibration mode"""
            selected_sensor.set(sensor_id)
            
            # Send calibration configuration to nRF52840
            if self.ble_manager.is_connected:
                self.activate_sensor_led(sensor_id)
            
            # Update molecule name and unit from existing config
            config = self.sensor_configs.get(sensor_id)
            if config:
                molecule_name_var.set(config.molecule_name or f"Channel {sensor_id}")
                unit_var.set(config.unit or "mV")
            
            calibration_status.set(f"Sensor {sensor_id} selected - Calibration mode activated")
            update_current_reading()
        
        colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12']
        for i in range(4):
            sensor_row = tk.Frame(sensor_frame, bg='#ecf0f1')
            sensor_row.pack(fill=tk.X, pady=5)
            
            checkbox = tk.Radiobutton(sensor_row, text=f"Sensor {i}", 
                                    variable=selected_sensor, value=i,
                                    command=lambda s=i: on_sensor_select(s),
                                    font=('Arial', 11, 'bold'), bg='#ecf0f1',
                                    activebackground='#ecf0f1', fg=colors[i])
            checkbox.pack(side=tk.LEFT, padx=10)
            
            # Status indicator
            status_label = tk.Label(sensor_row, text="Not calibrated", 
                                font=('Arial', 10), bg='#ecf0f1', fg='#e74c3c')
            status_label.pack(side=tk.RIGHT, padx=10)
            
            sensor_checkboxes[i] = checkbox
            sensor_status_labels[i] = status_label
        
        # Molecule configuration
        config_frame = tk.LabelFrame(left_panel, text="Molecule Configuration", 
                                    font=('Arial', 12, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        config_frame.pack(fill=tk.X, padx=15, pady=15)
        
        tk.Label(config_frame, text="Molecule Name:", font=('Arial', 11), bg='#ecf0f1').pack(anchor=tk.W, padx=10, pady=5)
        molecule_entry = tk.Entry(config_frame, textvariable=molecule_name_var, font=('Arial', 11))
        molecule_entry.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(config_frame, text="Unit (Concentration):", font=('Arial', 11), bg='#ecf0f1').pack(anchor=tk.W, padx=10, pady=5)
        unit_entry = tk.Entry(config_frame, textvariable=unit_var, font=('Arial', 11))
        unit_entry.pack(fill=tk.X, padx=10, pady=5)
        
        # Current reading display
        reading_frame = tk.LabelFrame(left_panel, text="Current Reading", 
                                    font=('Arial', 12, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        reading_frame.pack(fill=tk.X, padx=15, pady=15)
        
        current_reading_label = tk.Label(reading_frame, textvariable=current_reading_var, 
                                    font=('Arial', 18, 'bold'), fg='#27ae60', bg='#ecf0f1')
        current_reading_label.pack(pady=15)
        
        tk.Label(reading_frame, text="Raw Sensor Value", font=('Arial', 10), 
                fg='#7f8c8d', bg='#ecf0f1').pack()
        
        # Middle panel - Calibration points
        middle_panel = tk.LabelFrame(main_container, text="Calibration Points (6 solutions required)", 
                                    font=('Arial', 14, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        middle_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Concentration input
        input_frame = tk.Frame(middle_panel, bg='#ecf0f1')
        input_frame.pack(fill=tk.X, padx=15, pady=15)
        
        tk.Label(input_frame, text="Solution Concentration:", font=('Arial', 12, 'bold'), bg='#ecf0f1').pack(anchor=tk.W)
        
        concentration_input_frame = tk.Frame(input_frame, bg='#ecf0f1')
        concentration_input_frame.pack(fill=tk.X, pady=10)
        
        concentration_entry = tk.Entry(concentration_input_frame, textvariable=concentration_entry_var, 
                                    font=('Arial', 14), width=15)
        concentration_entry.pack(side=tk.LEFT)
        
        def add_calibration_point():
            """Add current reading as calibration point"""
            try:
                sensor_id = selected_sensor.get()
                concentration = float(concentration_entry_var.get())
                
                # Utiliser la valeur actuelle affichée
                raw_reading = float(current_reading_var.get())
                
                current_calibration_points[sensor_id].append((concentration, raw_reading))
                concentration_entry_var.set("")
                
                update_calibration_table()
                calibration_status.set(f"Point {len(current_calibration_points[sensor_id])}/6 added for Sensor {sensor_id}")
                
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid concentration value")
        
        add_point_btn = tk.Button(concentration_input_frame, text="Add Point ✓", 
                                bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
                                command=add_calibration_point)
        add_point_btn.pack(side=tk.LEFT, padx=10)
        
        # Calibration points table
        table_frame = tk.Frame(middle_panel, bg='#ecf0f1')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        columns = ('Point', 'Concentration', 'Raw Value')
        cal_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            cal_tree.heading(col, text=col)
            cal_tree.column(col, width=120, anchor=tk.CENTER)
        
        cal_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=cal_tree.yview)
        cal_tree.configure(yscrollcommand=cal_scrollbar.set)
        
        cal_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cal_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def update_calibration_table():
            """Update calibration points table"""
            # Clear existing items
            for item in cal_tree.get_children():
                cal_tree.delete(item)
            
            # Add points for selected sensor
            sensor_id = selected_sensor.get()
            points = current_calibration_points[sensor_id]
            
            for i, (conc, raw) in enumerate(points, 1):
                cal_tree.insert('', 'end', values=(f'Point {i}', f'{conc:.3f}', f'{raw:.2f}'))
        
        # Clear points button
        clear_btn = tk.Button(middle_panel, text="Clear Points", bg='#e74c3c', fg='white',
                            font=('Arial', 11, 'bold'), 
                            command=lambda: clear_calibration_points())
        clear_btn.pack(pady=10)
        
        def clear_calibration_points():
            """Clear calibration points for selected sensor"""
            sensor_id = selected_sensor.get()
            current_calibration_points[sensor_id] = []
            update_calibration_table()
            calibration_status.set(f"Calibration points cleared for Sensor {sensor_id}")
        
        # Right panel - Results and functions
        right_panel = tk.LabelFrame(main_container, text="Calibration Results", 
                                font=('Arial', 14, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Function display
        function_frame = tk.LabelFrame(right_panel, text="Calibration Function", 
                                    font=('Arial', 12, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        function_frame.pack(fill=tk.X, padx=15, pady=15)
        
        function_text = scrolledtext.ScrolledText(function_frame, width=35, height=8, 
                                                font=('Courier', 10), bg='#2c3e50', fg='#ecf0f1')
        function_text.pack(padx=10, pady=10)
        
        # Calibrate button
        calibrate_btn = tk.Button(right_panel, text="CALIBRATE SENSOR", 
                                bg='#8e44ad', fg='white', font=('Arial', 14, 'bold'),
                                command=lambda: perform_calibration())
        calibrate_btn.pack(pady=20)
        
        # Status display
        status_frame = tk.LabelFrame(right_panel, text="Status", 
                                    font=('Arial', 12, 'bold'), bg='#ecf0f1', fg='#2c3e50')
        status_frame.pack(fill=tk.X, padx=15, pady=15)
        
        status_label = tk.Label(status_frame, textvariable=calibration_status, 
                            font=('Arial', 11), bg='#ecf0f1', fg='#2c3e50',
                            wraplength=300, justify=tk.LEFT)
        status_label.pack(padx=10, pady=10)
        
        def perform_calibration():
            """Perform calibration calculation and save"""
            try:
                sensor_id = selected_sensor.get()
                points = current_calibration_points[sensor_id]
                
                if len(points) < 2:
                    messagebox.showwarning("Warning", "At least 2 calibration points required")
                    return
                
                # Extract data for calibration
                concentrations = [p[0] for p in points]
                raw_values = [p[1] for p in points]
                
                # Perform polynomial fit (quadratic)
                import numpy as np
                coeffs = np.polyfit(raw_values, concentrations, min(len(points)-1, 2))
                
                # Calculate R-squared
                y_pred = np.polyval(coeffs, raw_values)
                ss_res = np.sum((concentrations - y_pred) ** 2)
                ss_tot = np.sum((concentrations - np.mean(concentrations)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
                
                # Create function formula
                if len(coeffs) == 3:
                    formula = f"y = {coeffs[0]:.6f}x² + {coeffs[1]:.6f}x + {coeffs[2]:.6f}"
                elif len(coeffs) == 2:
                    formula = f"y = {coeffs[0]:.6f}x + {coeffs[1]:.6f}"
                else:
                    formula = f"y = {coeffs[0]:.6f}x"
                
                # Update sensor configuration
                config = self.sensor_configs[sensor_id]
                config.calibration_coeffs = tuple(coeffs)
                config.calibration_points = points.copy()
                config.is_calibrated = True
                config.calibration_function_formula = formula
                config.calibration_r_squared = r_squared
                config.calibration_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                config.molecule_name = molecule_name_var.get()
                config.unit = unit_var.get()
                
                # Display results
                result_text = f"Calibration Completed!\n\n"
                result_text += f"Sensor: {sensor_id}\n"
                result_text += f"Molecule: {config.molecule_name}\n"
                result_text += f"Unit: {config.unit}\n\n"
                result_text += f"Function:\n{formula}\n\n"
                result_text += f"R² = {r_squared:.4f}\n"
                result_text += f"Points used: {len(points)}\n"
                result_text += f"Date: {config.calibration_date}"
                
                function_text.delete(1.0, tk.END)
                function_text.insert(tk.END, result_text)
                
                # Update status indicator
                sensor_status_labels[sensor_id].config(text="Calibrated ✓", fg='#27ae60')
                
                calibration_status.set(f"Sensor {sensor_id} calibrated successfully!")
                
                self.on_message(f"Sensor {sensor_id} calibrated: {formula} (R²={r_squared:.4f})")
                
            except Exception as e:
                messagebox.showerror("Calibration Error", f"Failed to calibrate sensor: {str(e)}")
                calibration_status.set(f"Calibration failed: {str(e)}")
        
        def update_current_reading():
            """Update current sensor reading"""
            try:
                sensor_id = selected_sensor.get()
                data = self.ble_manager.data_channels[sensor_id]
                if data:
                    # Prendre la dernière donnée reçue
                    latest_data = data[-1]
                    current_reading_var.set(f"{latest_data.mv:.2f}")
                else:
                    current_reading_var.set("0.00")
            except Exception as e:
                current_reading_var.set("0.00")
                print(f"Update reading error: {e}")  # Debug

            
            # Schedule next update plus fréquemment pour le mode calibration
            cal_window.after(500, update_current_reading)  # Mise à jour toutes les 500ms
        
        def calibration_data_callback(sensor_data):
            """Callback spécifique pour recevoir les données en mode calibration"""
            if sensor_data.channel == selected_sensor.get():
                # Mettre à jour l'affichage en temps réel dans le thread UI
                cal_window.after(0, lambda: current_reading_var.set(f"{sensor_data.mv:.2f}"))
        
        # Load existing calibration data
        def load_existing_calibrations():
            """Load existing calibration configurations"""
            for sensor_id, config in self.sensor_configs.items():
                if config.is_calibrated:
                    sensor_status_labels[sensor_id].config(text="Calibrated ✓", fg='#27ae60')
                    if config.calibration_points:
                        current_calibration_points[sensor_id] = config.calibration_points.copy()

        
        # Bottom panel - Navigation
        bottom_panel = tk.Frame(cal_window, bg='#2c3e50', height=70)
        bottom_panel.pack(fill=tk.X)
        bottom_panel.pack_propagate(False)
        
        # Main menu and Exit buttons
        tk.Button(bottom_panel, text="Main Menu", bg='#34495e', fg='white', 
                font=('Arial', 14, 'bold'), width=15, height=1,
                command=cal_window.destroy).pack(side=tk.LEFT, padx=50, pady=20)
        
        tk.Button(bottom_panel, text="Exit", bg='#e74c3c', fg='white', 
                font=('Arial', 14, 'bold'), width=15, height=1,
                command=cal_window.destroy).pack(side=tk.RIGHT, padx=50, pady=20)
        
        # Initialize
        load_existing_calibrations()
        on_sensor_select(0)  # Select first sensor by default
        update_current_reading()  # Start reading updates

    def activate_sensor_led(self, sensor_id):
        """Send calibration configuration for specific sensor"""
        if not self.ble_manager.is_connected:
            return
        
        calibration_config = {
            "state": True,
            "clb": True,
            "index": sensor_id
        }

        def calibration_data_callback(sensor_data):
            """Callback spécifique pour recevoir les données en mode calibration"""
            if sensor_data.channel == sensor_id:
                # CORRECTION : Utiliser la référence correcte
                if hasattr(self, '_current_reading_var'):
                    self.root.after(0, lambda: self._current_reading_var.set(f"{sensor_data.mv:.2f}"))
        
        # Activer le callback de calibration
        self.ble_manager.calibration_callback = calibration_data_callback
        
        # Send calibration mode configuration
        future = self.run_async(self.ble_manager.send_calibration_config(calibration_config))
        
        def on_calibration_activate_complete(future):
            try:
                success = future.result()
                if success:
                    self.on_message(f"Calibration mode activated for sensor {sensor_id}")
                else:
                    self.on_message(f"Failed to activate calibration mode for sensor {sensor_id}")
                    self.ble_manager.calibration_callback = None
            except Exception as e:
                self.on_message(f"Calibration activation error: {e}")
                self.ble_manager.calibration_callback = None
        
        future.add_done_callback(on_calibration_activate_complete)

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
    
    def deactivate_calibration_mode(self):
        """Désactiver le mode calibration"""
        if self.ble_manager:
            self.ble_manager.calibration_callback = None
        
        # Optionnel: envoyer un signal au nRF52840 pour arrêter le mode calibration
        if self.ble_manager.is_connected:
            stop_calibration_config = {
                "state": True,
                "clb": False,
                "index": 0
            }
            self.run_async(self.ble_manager.send_calibration_config(stop_calibration_config))

    def toggle_state(self):
        """Toggle system state and send to device"""
        # inverse state locally
        self.ble_manager.system_state = not self.ble_manager.system_state
        new_state = self.ble_manager.system_state

        # Update button UI
        if new_state:
            self.state_btn.config(text="STATE ON", bg='#1abc9c')
        else:
            self.state_btn.config(text="STATE OFF", bg='#e74c3c')
        
        # Log local
        self.on_message(f"System state changed to: {'ON' if new_state else 'OFF'}")

        # Send to device
        def on_state_send_complete(future):
            try:
                success = future.result()
                if success:
                    self.on_message(f"✓ State {'ON' if new_state else 'OFF'} sent to nRF52840")
                else:
                    self.on_message(f"✗ Failed to send state to nRF52840")
                    # Comeback to previous state
                    self.ble_manager.system_state = not new_state
                    if not new_state:
                        self.state_btn.config(text="STATE ON", bg='#1abc9c')
                    else:
                        self.state_btn.config(text="STATE OFF", bg='#e74c3c')
            except Exception as e:
                self.on_message(f"✗ State send error: {e}")
        
        future = self.run_async(self.ble_manager.send_state_update(new_state))
        future.add_done_callback(on_state_send_complete)

    def update_connection_ui(self):
        """Update UI when connection state changes"""
        if self.ble_manager.is_connected:
            self.connect_btn.configure(state=tk.DISABLED)
            self.disconnect_btn.configure(state=tk.NORMAL)
            self.start_btn.configure(state=tk.NORMAL)
            self.send_message_btn.configure(state=tk.NORMAL)  # Enable send button
            self.connection_var.set("Connected")
            self.connection_label.configure(foreground="#27ae60")
            self.send_status_var.set("Ready to send messages")
            self.state_btn.configure(state=tk.NORMAL)
        else:
            self.connect_btn.configure(state=tk.NORMAL)
            self.disconnect_btn.configure(state=tk.DISABLED)
            self.start_btn.configure(state=tk.DISABLED)
            self.stop_btn.configure(state=tk.DISABLED)
            self.send_message_btn.configure(state=tk.DISABLED)  # Disable send button
            self.connection_var.set("Disconnected")
            self.connection_label.configure(foreground="#e74c3c")
            self.send_status_var.set("Device must be connected to send messages")
            self.is_recording = False
            self.state_btn.configure(state=tk.DISABLED) 
            self.state_btn.config(text="STATE OFF", bg='#95a5a6')
    
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
    
    def update_timing_status_display(self):
        """Update timing status display in the main interface"""
        try:
            # Count active timing entries across all sensors
            total_active_timings = 0
            total_configured_timings = 0
            
            for sensor_id, config in self.sensor_configs.items():
                if config.timing_entries:
                    total_configured_timings += len(config.timing_entries)
                    active_timings = sum(1 for t in config.timing_entries if t.enabled)
                    total_active_timings += active_timings
            
            # Calculate total cycle time and frequency
            total_cycle_time = 0
            for sensor_id, config in self.sensor_configs.items():
                for timing in config.timing_entries:
                    if timing.enabled:
                        total_cycle_time += timing.cycle_time_ms
            
            system_frequency = 1000.0 / total_cycle_time if total_cycle_time > 0 else 0
            
            # Update status message
            if total_active_timings > 0:
                status_message = (f"Timing: {total_active_timings} active sequences | "
                                f"Cycle: {total_cycle_time}ms | "
                                f"Freq: {system_frequency:.2f}Hz")
            else:
                status_message = "Timing: No active sequences configured"
            
            # Update the status bar or create a timing info label if needed
            self.status_var.set(status_message)
            
            # Log the configuration update
            self.on_message(f"Timing configuration updated: {total_active_timings} active sequences")
            
        except Exception as e:
            logger.error(f"Failed to update timing status display: {e}")
            self.on_message(f"Warning: Timing status update failed: {e}")

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
    
    def send_message_to_device(self):
        """Send message from log interface to nRF52840"""
        message = self.message_entry.get().strip()
        
        if not message:
            messagebox.showwarning("Warning", "Please enter a message to send")
            return
        
        if not self.ble_manager.is_connected:
            messagebox.showwarning("Warning", "Device not connected")
            return
        
        # Clear the input
        self.message_entry.delete(0, tk.END)
        
        # Update status
        self.send_status_var.set("Sending message...")
        self.send_message_btn.configure(state=tk.DISABLED, text="SENDING...")
        
        # Log the outgoing message
        self.on_message(f">>> SENDING: {message}")
        
        def on_send_complete(future):
            try:
                success = future.result()
                if success:
                    self.root.after(0, lambda: self.send_status_var.set("Message sent successfully"))
                    self.root.after(0, lambda: self.on_message(">>> Message sent to nRF52840"))
                else:
                    self.root.after(0, lambda: self.send_status_var.set("Failed to send message"))
                    self.root.after(0, lambda: self.on_message(">>> ERROR: Failed to send message"))
            except Exception as e:
                self.root.after(0, lambda: self.send_status_var.set(f"Send error: {e}"))
                self.root.after(0, lambda: self.on_message(f">>> ERROR: {e}"))
            finally:
                self.root.after(0, lambda: self.send_message_btn.configure(state=tk.NORMAL, text="SEND"))
                # Reset status after 3 seconds
                self.root.after(3000, lambda: self.send_status_var.set("Ready to send messages"))
        
        # Send message asynchronously
        future = self.run_async(self.ble_manager.send_message(message))
        future.add_done_callback(on_send_complete)

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

    def send_timing_to_device(self):
        """Send current timing configuration to nRF52840 in simplified format"""
        if not self.ble_manager.is_connected:
            messagebox.showwarning("Warning", "Device not connected")
            return
            
        # Prepare timing configuration data in Arduino format
        config_data = {
            "sequences": []
        }
            
        # collect unique timing sequences
        unique_sequences = {}
        
        #track unique (pin, time_open, time_delay, time_read, enabled) combinations
        for sensor_id, config in self.sensor_configs.items():
            for timing in config.timing_entries:
                
                # create a unique key for the timing entry
                timing_key = (timing.pin, timing.time_open_ms, 
                            timing.time_delay_ms, timing.time_read_ms, timing.brightness,timing.enabled)

                # Only add if this combination doesn't already exist
                if timing_key not in unique_sequences:
                    # Create arduino-style keys
                    sequence = {
                        "led_pin": timing.pin,           # use 'pin' as 'led_pin'
                        "time_open_ms": timing.time_open_ms,
                        "time_delay_ms": timing.time_delay_ms,
                        "time_read_ms": timing.time_read_ms,
                        "enabled": timing.enabled,
                        "lpo": timing.brightness
                    }
                    unique_sequences[timing_key] = sequence
        
        # Convert to list
        config_data["sequences"] = list(unique_sequences.values())
        
        # Sort sequences by led_pin for consistency
        config_data["sequences"] = sorted(
            config_data["sequences"], 
            key=lambda x: x["led_pin"]
        )
        
        total_sequences = len(config_data["sequences"])
        enabled_sequences = len([seq for seq in config_data["sequences"] if seq["enabled"]])
        unique_leds = len(set(seq["led_pin"] for seq in config_data["sequences"] if seq["enabled"]))

        self.on_message(f"Sending timing config:")
        self.on_message(f"  • {unique_leds} active LEDs")
        self.on_message(f"  • {enabled_sequences} / {total_sequences} enabled sequences")

        # Send to device
        def on_send_complete(future):
            try:
                success = future.result()
                if success:
                    self.on_message("✓ Timing configuration sent to nRF52840")
                    messagebox.showinfo("Configuration Sent", 
                                    f"Timing configuration sent successfully!\n\n"
                                    f"Configuration:\n"
                                    f"• {unique_leds} LEDs configured\n"
                                    f"• {total_sequences} total sequences")
                else:
                    self.on_message("✗ Failed to send timing configuration")
                    messagebox.showerror("Error", "Failed to send configuration to device")
            except Exception as e:
                self.on_message(f"✗ Send error: {e}")
                messagebox.showerror("Error", f"Configuration send error: {e}")

        future = self.run_async(self.ble_manager.send_timing_config(config_data))
        future.add_done_callback(on_send_complete)    

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