import tkinter as tk
from tkinter import ttk, messagebox
import PIL.Image
import PIL.ImageTk
import PIL.ImageChops
import pyautogui
import threading
import time
from plyer import notification
import io
import requests

class ScreenMonitor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Screen Section Monitor")
        self.root.geometry("400x350")
        
        # vars
        self.selection_coords = None
        self.reference_image = None
        self.monitoring = False
        self.monitor_thread = None
        self.sensitivity = tk.DoubleVar(value=5.0)  # im diff threshold percents
        self.check_interval = tk.DoubleVar(value=3.0)  # seconds between update
        self.notify_topic = tk.StringVar(value="")  # ntfy topic
        self.send_phone_notification = tk.BooleanVar(value=False)  # phone notification toggle
        
        self.setup_ui()
        
    def setup_ui(self):
        # Big box
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Selection section
        selection_frame = ttk.LabelFrame(main_frame, text="Screen Selection", padding="5")
        selection_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.select_btn = ttk.Button(selection_frame, text="Select Screen Area", 
                                   command=self.start_selection)
        self.select_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.coords_label = ttk.Label(selection_frame, text="No area selected")
        self.coords_label.grid(row=0, column=1)
        
        # Notification section
        notification_frame = ttk.LabelFrame(main_frame, text="Notification Settings", padding="5")
        notification_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Phone notification toggle
        self.phone_notify_check = ttk.Checkbutton(notification_frame, 
                                                text="Send phone notifications", 
                                                variable=self.send_phone_notification)
        self.phone_notify_check.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        
        ttk.Label(notification_frame, text="Ntfy Topic:").grid(row=1, column=0, sticky=tk.W)
        self.topic_entry = ttk.Entry(notification_frame, textvariable=self.notify_topic, width=30)
        self.topic_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        # Initially disable topic entry since checkbox is unchecked by default
        self.topic_entry.config(state=tk.DISABLED)
        
        # Bind checkbox to enable/disable topic entry
        self.send_phone_notification.trace('w', self.toggle_topic_entry)
        
        notification_frame.columnconfigure(1, weight=1)
        
        # Settings section
        settings_frame = ttk.LabelFrame(main_frame, text="Monitor Settings", padding="5")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(settings_frame, text="Sensitivity (%):").grid(row=0, column=0, sticky=tk.W)
        sensitivity_scale = ttk.Scale(settings_frame, from_=0.1, to=20.0, 
                                    variable=self.sensitivity, orient=tk.HORIZONTAL)
        sensitivity_scale.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        ttk.Label(settings_frame, text="Check Interval (s):").grid(row=1, column=0, sticky=tk.W)
        interval_scale = ttk.Scale(settings_frame, from_=0.1, to=10.0, 
                                 variable=self.check_interval, orient=tk.HORIZONTAL)
        interval_scale.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        settings_frame.columnconfigure(1, weight=1)
        
        # go time
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=3, column=0, columnspan=2, pady=(0, 10))
        
        self.start_btn = ttk.Button(control_frame, text="Start Monitoring", 
                                  command=self.start_monitoring, state=tk.DISABLED)
        self.start_btn.grid(row=0, column=0, padx=(0, 5))
        
        self.stop_btn = ttk.Button(control_frame, text="Stop Monitoring", 
                                 command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1)
        
        # what is happening
        self.status_label = ttk.Label(main_frame, text="Status: Ready")
        self.status_label.grid(row=4, column=0, columnspan=2, sticky=tk.W)
        
        # grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
    
    def toggle_topic_entry(self, *args):
        """Enable/disable topic entry based on phone notification checkbox"""
        if self.send_phone_notification.get():
            self.topic_entry.config(state=tk.NORMAL)
        else:
            self.topic_entry.config(state=tk.DISABLED)
        
    def start_selection(self):
        self.root.withdraw() 
        self.create_selection_overlay()
        
    def create_selection_overlay(self):
        # overlay window
        self.overlay = tk.Toplevel()
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-topmost', True)
        self.overlay.configure(bg='black')
        self.overlay.after(10, lambda: self.overlay.attributes('-alpha', 0.3))
        
        # box vars
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        
        # canvas
        self.canvas = tk.Canvas(self.overlay, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # mouse events
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        
        # how to
        instruction_label = tk.Label(self.overlay, 
                                   text="Click and drag to select area. Press ESC to cancel.",
                                   fg='white', bg='black', font=('Arial', 12))
        instruction_label.pack()
        
        # escape key functionality
        self.overlay.bind('<Escape>', self.cancel_selection)
        self.overlay.focus_set()
        
    def on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        
    def on_drag(self, event):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline='red', width=2, fill='')
            
    def on_release(self, event):
        if self.start_x and self.start_y:
            # store coords
            left = min(self.start_x, event.x)
            top = min(self.start_y, event.y)
            right = max(self.start_x, event.x)
            bottom = max(self.start_y, event.y)
            
            self.selection_coords = (left, top, right, bottom)
            self.finish_selection()
            
    def cancel_selection(self, event=None):
        self.overlay.destroy()
        self.root.deiconify()
        
    def finish_selection(self):
        self.overlay.destroy()
        self.root.deiconify()
        
        if self.selection_coords:
            width = self.selection_coords[2] - self.selection_coords[0]
            height = self.selection_coords[3] - self.selection_coords[1]
            
            # validate
            if width < 10 or height < 10:
                messagebox.showwarning("Selection Too Small", "Please select a larger area")
                self.selection_coords = None
                return
                
            self.coords_label.config(
                text=f"Selected: {width}x{height} at ({self.selection_coords[0]}, {self.selection_coords[1]})")
            
            # reference image
            self.capture_reference_image()
            
            # sanity protection
            if self.reference_image:
                self.start_btn.config(state=tk.NORMAL)
            
    def capture_reference_image(self):
        if self.selection_coords:
            try:
                # small delay
                time.sleep(0.1)
                screenshot = pyautogui.screenshot(region=self.selection_coords)
                self.reference_image = screenshot
                self.status_label.config(text="Status: Reference image captured - Ready to monitor")
                return True
            except Exception as e:
                messagebox.showerror("Capture Error", f"Failed to capture reference image: {e}")
                self.status_label.config(text="Status: Failed to capture reference image")
                self.selection_coords = None
                return False
        return False
            
    def start_monitoring(self):
        if not self.selection_coords or not self.reference_image:
            messagebox.showerror("Error", "Please select a screen area first")
            return
        
        # only check topic if phone notifications are enabled
        if self.send_phone_notification.get() and not self.notify_topic.get().strip():
            messagebox.showerror("Error", "Please enter a notification topic or disable phone notifications")
            return
            
        self.monitoring = True
        self.reference_image = pyautogui.screenshot(region=self.selection_coords)
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.select_btn.config(state=tk.DISABLED)
        self.phone_notify_check.config(state=tk.DISABLED)
        if self.send_phone_notification.get():
            self.topic_entry.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Monitoring active")
        
        # begin looking happens here
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        self.monitoring = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.select_btn.config(state=tk.NORMAL)
        self.phone_notify_check.config(state=tk.NORMAL)
        # re-enable topic entry based on checkbox state
        if self.send_phone_notification.get():
            self.topic_entry.config(state=tk.NORMAL)
        self.status_label.config(text="Status: Monitoring stopped")
        
    def monitor_loop(self):
        while self.monitoring:
            try:
                # get curr selection
                current_screenshot = pyautogui.screenshot(region=self.selection_coords)
                
                # compare to ref
                if self.images_different(self.reference_image, current_screenshot):
                    self.send_notifications()
                    # update ref
                    self.reference_image = current_screenshot
                    
                time.sleep(self.check_interval.get())
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                break
                
    def images_different(self, img1, img2):
        # mode match in case something went down
        if img1.mode != img2.mode:
            img2 = img2.convert(img1.mode)
            
        # size match in case something weird has happened
        if img1.size != img2.size:
            img2 = img2.resize(img1.size)
            
        # difference
        diff = PIL.ImageChops.difference(img1, img2)
        
        # grayscale (no worky)
        #if diff.mode != 'L':
        #    diff = diff.convert('L')
        
        # histogram
        histogram = diff.histogram()
        
        # pixels
        total_pixels = img1.size[0] * img1.size[1]
        
        # diff pixels
        unchanged_pixels = histogram[0]  # Pixels with 0 difference
        changed_pixels = total_pixels - unchanged_pixels
        
        # div by 0 is bad
        if total_pixels == 0:
            return False
            
        percentage_changed = (changed_pixels / total_pixels) * 100
        
        # debug
        #print(f"Changed pixels: {changed_pixels}/{total_pixels} = {percentage_changed:.2f}%")
        
        return percentage_changed > self.sensitivity.get()
        
    def send_notifications(self):
        """Send notifications to PC and optionally to phone"""
        message = "Screen change detected!"
        
        #PC notification
        try:
            notification.notify(
                title="Screen Monitor Alert",
                message=message,
                timeout=5
            )
            print("PC notification sent successfully!")
        except Exception as e:
            print(f"Error sending PC notification: {e}")
        
        #phone notification only if checkbox is checked
        if self.send_phone_notification.get():
            topic = self.notify_topic.get().strip()
            if topic:
                url = f"https://ntfy.sh/{topic}"
                try:
                    response = requests.post(url, data=message.encode("utf-8"))
                    if response.status_code == 200:
                        print("Phone notification sent successfully!")
                    else:
                        print("Failed to send phone notification:", response.status_code, response.text)
                except Exception as e:
                    print(f"Error sending phone notification: {e}")
            else:
                print("No topic specified for phone notification")
            
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    # dependencies
    try:
        import pyautogui
        import PIL.Image
        import PIL.ImageTk
        import PIL.ImageChops
        from plyer import notification
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        print("Please install required packages:")
        print("pip install pyautogui pillow plyer requests")
        exit(1)
        
    app = ScreenMonitor()
    app.run()