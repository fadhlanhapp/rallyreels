#!/usr/bin/env python3
"""
Sports Highlight Recorder
Records continuous video and saves 2-minute highlights when button is pressed
"""

import cv2
import threading
import time
import os
from datetime import datetime
from collections import deque
import RPi.GPIO as GPIO

class SportsHighlightRecorder:
    def __init__(self):
        # Configuration
        self.BUTTON_PIN = 2
        self.BUFFER_SECONDS = 120  # 2 minutes
        self.FPS = 15  # Lower FPS for testing (saves storage)
        self.RESOLUTION = (640, 480)  # Lower resolution for testing
        self.HIGHLIGHTS_DIR = "/home/enigma/sports-recorder/highlights"
        
        # Video buffer - stores frames
        self.frame_buffer = deque()
        self.max_buffer_size = self.BUFFER_SECONDS * self.FPS
        self.recording = False
        self.camera = None
        
        # Setup GPIO
        self.setup_gpio()
        
        # Create highlights directory
        os.makedirs(self.HIGHLIGHTS_DIR, exist_ok=True)
        
    def setup_gpio(self):
        """Initialize GPIO for button input"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # Add interrupt for button press
        GPIO.add_event_detect(self.BUTTON_PIN, GPIO.FALLING, 
                            callback=self.button_pressed, bouncetime=500)
        print("GPIO setup complete - Button ready on GPIO 2")
    
    def initialize_camera(self):
        """Initialize the USB camera"""
        print("Initializing camera...")
        
        # Try different backends and camera indices
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
        
        for backend in backends:
            backend_name = "V4L2" if backend == cv2.CAP_V4L2 else "ANY"
            print(f"Trying backend: {backend_name}")
            
            for i in range(3):
                print(f"  Trying camera index {i}...")
                try:
                    self.camera = cv2.VideoCapture(i, backend)
                    # Set a timeout by trying to read immediately
                    ret, _ = self.camera.read()
                    if ret:
                        print(f"Camera found at index {i} with {backend_name}")
                        return self.setup_camera_properties()
                    else:
                        print(f"  Camera index {i} opened but no frame")
                        self.camera.release()
                except Exception as e:
                    print(f"  Camera index {i} failed: {e}")
                    if self.camera:
                        self.camera.release()
        
        print("No working camera found!")
        return False
    
    def setup_camera_properties(self):
        """Configure camera properties"""
        # Set camera properties
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.RESOLUTION[0])
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.RESOLUTION[1])
        self.camera.set(cv2.CAP_PROP_FPS, self.FPS)
        
        print(f"Camera initialized: {self.RESOLUTION[0]}x{self.RESOLUTION[1]} @ {self.FPS}fps")
        return True
    
    def start_recording(self):
        """Start the continuous recording loop"""
        if not self.initialize_camera():
            return False
            
        self.recording = True
        
        # Start recording in separate thread
        self.record_thread = threading.Thread(target=self.recording_loop, daemon=True)
        self.record_thread.start()
        
        print("Recording started! Press the button to save highlights.")
        return True
    
    def recording_loop(self):
        """Main recording loop - runs continuously"""
        frame_count = 0
        
        while self.recording:
            ret, frame = self.camera.read()
            
            if not ret:
                print("WARNING: Failed to read frame")
                continue
            
            # Add timestamp to frame
            timestamp = time.time()
            
            # Store frame with timestamp in circular buffer
            self.frame_buffer.append((frame.copy(), timestamp))
            
            # Maintain buffer size limit
            if len(self.frame_buffer) > self.max_buffer_size:
                self.frame_buffer.popleft()
            
            frame_count += 1
            if frame_count % (self.FPS * 10) == 0:  # Every 10 seconds
                print(f"Recording... Buffer: {len(self.frame_buffer)} frames")
            
            # Small delay to control frame rate
            time.sleep(1.0 / self.FPS)
    
    def button_pressed(self, channel):
        """Callback when button is pressed"""
        print("\n🔴 BUTTON PRESSED! Saving highlight...")
        
        # Run save in separate thread to avoid blocking
        save_thread = threading.Thread(target=self.save_highlight, daemon=True)
        save_thread.start()
    
    def save_highlight(self):
        """Save the current buffer as a highlight video"""
        if len(self.frame_buffer) == 0:
            print("ERROR: No frames in buffer to save!")
            return
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"highlight_{timestamp}.avi"
        filepath = os.path.join(self.HIGHLIGHTS_DIR, filename)
        
        print(f"Saving {len(self.frame_buffer)} frames to {filename}...")
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(filepath, fourcc, self.FPS, self.RESOLUTION)
        
        if not out.isOpened():
            print("ERROR: Could not open video writer!")
            return
        
        # Write all frames from buffer
        frames_written = 0
        for frame, timestamp in list(self.frame_buffer):
            out.write(frame)
            frames_written += 1
        
        out.release()
        
        # Get file size
        file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
        duration = frames_written / self.FPS
        
        print(f"✅ Highlight saved!")
        print(f"   File: {filename}")
        print(f"   Duration: {duration:.1f} seconds")
        print(f"   Size: {file_size:.1f} MB")
        print(f"   Frames: {frames_written}")
        print("Ready for next highlight...\n")
    
    def stop_recording(self):
        """Stop recording and cleanup"""
        print("Stopping recording...")
        self.recording = False
        
        if self.camera:
            self.camera.release()
        
        GPIO.cleanup()
        print("Recording stopped and resources cleaned up.")
    
    def get_stats(self):
        """Print current system stats"""
        buffer_duration = len(self.frame_buffer) / self.FPS
        print(f"\n📊 Current Status:")
        print(f"   Buffer: {len(self.frame_buffer)} frames ({buffer_duration:.1f} seconds)")
        print(f"   Recording: {'Yes' if self.recording else 'No'}")
        print(f"   Highlights saved: {len(os.listdir(self.HIGHLIGHTS_DIR))} files")

def main():
    recorder = SportsHighlightRecorder()
    
    try:
        # Start recording
        if not recorder.start_recording():
            print("Failed to start recording!")
            return
        
        print("\n" + "="*50)
        print("🏆 SPORTS HIGHLIGHT RECORDER ACTIVE")
        print("="*50)
        print("📹 Recording continuously...")
        print("🔴 Press the physical button to save 2-minute highlight")
        print("💻 Press Ctrl+C to stop")
        print("="*50 + "\n")
        
        # Keep main thread alive and show periodic stats
        while True:
            time.sleep(30)  # Every 30 seconds
            recorder.get_stats()
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        recorder.stop_recording()
        print("Goodbye! 👋")

if __name__ == "__main__":
    main()