import time
import random
import threading
import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TrafficAI")

# Try importing real AI libraries
try:
    from ultralytics import YOLO
    import cv2
    import numpy as np
    AI_AVAILABLE = True
    logger.info("YOLOv8 and OpenCV detected. Real-time AI mode available.")
except ImportError:
    AI_AVAILABLE = False
    logger.warning("YOLOv8/OpenCV not found. Running in MOCK/SIMULATION mode.")

class TrafficAnalyzer:
    def __init__(self, mode="auto"):
        self.lock = threading.Lock()
        self.data = []
        # UPDATED LOCATION: 10°01'22.4"N 76°18'34.2"E -> 10.0229, 76.3095
        self.camera_config = [
            {"id": "CAM_002", "lat": 10.0229, "lng": 76.3095, "name": "Seaport-Airport Rd", "file": "traffic_cam2.mp4", "source_type": "live_cctv", "lanes": 8}
        ]
        self.unique_ids = set() # Store unique vehicle track IDs
        self.vehicle_types = ["car", "bike", "bus", "truck"]
        self.running = True
        self.current_frames = {} # Store latest JPG bytes for each camera
        
        # Decide mode
        if mode == "real" and not AI_AVAILABLE:
            logger.error("Real mode requested but libraries missing. Fallback to mock.")
            self.mode = "mock"
        elif mode == "auto":
            self.mode = "real" if AI_AVAILABLE else "mock"
        else:
            self.mode = mode
            
        logger.info(f"Traffic Analyzer starting in {self.mode.upper()} mode.")

        # Initialize Dummy Nodes (Simulated Data)
        # Initialize Dummy Nodes (Simulated Data on Roads)
        self.dummy_nodes = []
        
        # Hardcoded coordinates to align with actual roads near 10.025, 76.312
        # Roughly representing a North-South and East-West intersection pattern
        # Try to fetch REAL road geometry from OpenStreetMap
        # Try to fetch REAL road geometry from OpenStreetMap around the NEW location
        road_points = self.fetch_road_geometry(10.0229, 76.3095)
        
        if not road_points:
             # Fallback to Hardcoded coordinates if API fails
            logger.warning("OSM Fetch failed, using fallback coordinates.")
            road_points = [
                # --- Seaport-Airport Road (Main Artery) ---
                (10.0300, 76.3115), (10.0290, 76.3116), (10.0280, 76.3117),
                (10.0270, 76.3118), (10.0260, 76.3119), (10.0250, 76.3120),
                (10.0240, 76.3121), (10.0230, 76.3122), (10.0220, 76.3123),
                (10.0210, 76.3124),
                (10.0250, 76.3090), (10.0250, 76.3100), (10.0250, 76.3110),
                (10.0252, 76.3130), (10.0253, 76.3140), (10.0255, 76.3150)
            ]

        for i, (r_lat, r_lng) in enumerate(road_points):
            self.dummy_nodes.append({
                "lat": r_lat,
                "lng": r_lng,
                "id": f"DUMMY_{i}",
                "name": f"Sensor Node #{i+1}",
                "source_type": "simulated_cctv"
            })

        # Initialize AI
        self.model = None
        if self.mode == "real":
            try:
                self.model = YOLO('yolov8n.pt') 
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")
                self.mode = "mock"

        self.thread = threading.Thread(target=self._run_pipeline)
        self.thread.daemon = True
        self.thread.start()
    
    def fetch_road_geometry(self, lat, lng, radius=200):
        """
        Fetches road coordinates from OpenStreetMap using Overpass API.
        Returns a list of (lat, lng) tuples.
        """
        import requests
        try:
            # Query for driving roads (highway) around the point
            overpass_url = "http://overpass-api.de/api/interpreter"
            overpass_query = f"""
                [out:json];
                way["highway"](around:{radius},{lat},{lng});
                (._;>;);
                out body;
            """
            response = requests.get(overpass_url, params={'data': overpass_query}, timeout=5)
            data = response.json()
            
            nodes = {n['id']: (n['lat'], n['lon']) for n in data['elements'] if n['type'] == 'node'}
            ways = [x for x in data['elements'] if x['type'] == 'way']
            
            points = []
            for way in ways:
                # Get all nodes in the way
                way_nodes = way['nodes']
                # Sample every Nth node to avoid too many dots
                for nid in way_nodes[::2]: 
                    if nid in nodes:
                        points.append(nodes[nid])
            
            logger.info(f"Fetched {len(points)} road points from OSM.")
            return points
        except Exception as e:
            logger.error(f"Failed to fetch OSM data: {e}")
            return []

    def _run_pipeline(self):
        if self.mode == "real":
            self._process_cameras()
        else:
            self._generate_mock_stream()

    def _process_cameras(self):
        """
        Multi-Camera Real AI Pipeline.
        Round-robin processing of all configured video files.
        """
        import os
        import cv2 # Ensure cv2 is available in this scope

        caps = {}
        for cam in self.camera_config:
            src = cam["file"]
            
            # Check file existence and perform smart fallback
            if not os.path.exists(src):
                logger.warning(f"Video source '{src}' for {cam['id']} not found.")
                if os.path.exists("traffic.mov"): 
                     logger.warning("Falling back to default 'traffic.mov'.")
                     src = "traffic.mov"
                else:
                     logger.error(f"No valid video source found for {cam['id']} (and no fallback). Skipping.")
                     continue 
            
            cap = cv2.VideoCapture(src)
            if cap.isOpened():
                caps[cam["id"]] = cap
                logger.info(f"Initialized {cam['id']} with source {src}")
            else:
                logger.warning(f"Failed to open source for {cam['id']}")

        frame_interval = 3 # Process every Nth frame to save CPU
        frame_count = 0
        cached_annotated_frames = {}  # Store last annotated frame per camera

        while self.running:
            keys = list(caps.keys())
            for cam_id in keys:
                cap = caps[cam_id]
                ret, frame = cap.read()
                
                if not ret:
                    # Loop video
                    logger.debug(f"Looping {cam_id}")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                # Resize for speed (optional, but good for CPU)
                # Increased to 1024x576 for better detection of small vehicles
                frame = cv2.resize(frame, (1024, 576))

                # Frame Skipping Logic
                frame_count += 1
                should_run_ai = (frame_count % frame_interval == 0)

                # Use cached annotated frame by default (keeps boxes visible)
                annotated_frame = cached_annotated_frames.get(cam_id, frame)

                if should_run_ai:
                    # Run Tracking with lowered confidence to catch more vehicles
                    results = self.model.track(frame, persist=True, verbose=False, conf=0.15)
                    annotated_frame = results[0].plot()
                    # Cache this annotated frame
                    cached_annotated_frames[cam_id] = annotated_frame

                    # Count Logic
                    current_counts = {v: 0 for v in self.vehicle_types}
                    current_ids = {v: [] for v in self.vehicle_types} # Store list of IDs per type
                    
                    if results[0].boxes.id is not None:
                        boxes = results[0].boxes
                        track_ids = boxes.id.int().cpu().tolist()
                        clss = boxes.cls.int().cpu().tolist()

                        for track_id, cls_id in zip(track_ids, clss):
                            # Add to unique set (global)
                            self.unique_ids.add(track_id)
                            
                            label = self.model.names[cls_id].lower()
                            if label in ['car', 'motorcycle', 'bus', 'truck']:
                                type_key = label if label != 'motorcycle' else 'bike'
                                current_counts[type_key] += 1
                                current_ids[type_key].append(track_id) # Store ID
                    
                    # Update Data Store
                    with self.lock:
                        timestamp = datetime.datetime.now().isoformat()
                        if sum(current_counts.values()) > 0:
                            for v_type, count in current_counts.items():
                                if count > 0:
                                    self.data.append({
                                        "camera_id": cam_id,
                                        "camera_name": next(c['name'] for c in self.camera_config if c['id'] == cam_id),
                                        "lat": next(c['lat'] for c in self.camera_config if c['id'] == cam_id),
                                        "lng": next(c['lng'] for c in self.camera_config if c['id'] == cam_id),
                                        "vehicle_type": v_type,
                                        "count": count,
                                        "track_ids": current_ids[v_type], # Save the IDs!
                                        "timestamp": timestamp
                                    })
                        # Prune Data
                        if len(self.data) > 2000: self.data.pop(0)

                # Overlay Timestamp
                cv2.putText(annotated_frame, datetime.datetime.now().strftime("%H:%M:%S"), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    
                # Store Frame for Streaming (Always update this to keep feed smooth)
                ret, buffer = cv2.imencode('.jpg', annotated_frame)
                with self.lock:
                    self.current_frames[cam_id] = buffer.tobytes()
                    
                    # Prune Data
                    if len(self.data) > 2000: self.data.pop(0)

            time.sleep(0.016) # Yield CPU and limit to ~60 FPS

    def generate_frames(self, camera_id):
        """Yields latest frame for specific camera."""
        while True:
            with self.lock:
                frame = self.current_frames.get(camera_id)
            
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                # If no frame yet, yield empty or waiting logic
                pass
                
            time.sleep(0.05)
    
    # ... mock stream methods below can remain or be ignored if we always run real ...
    def _generate_mock_stream(self):
        """Generates continuous traffic data for demo purposes."""
        while self.running:
            with self.lock:
                self._generate_mock_data_for_other_cams([c["id"] for c in self.camera_config])
                # Prune
                if len(self.data) > 1000: self.data.pop(0)
            
            time.sleep(2) # Update every 2 seconds

    def _generate_mock_data_for_other_cams(self, cam_ids):
        timestamp = datetime.datetime.now().isoformat()
        # Use camera_config instead of camera_locations
        for cam in self.camera_config:
            if cam["id"] not in cam_ids: continue
            
            # Randomly detect vehicles
            if random.random() > 0.3: # 70% chance of detection per tick
                v_type = random.choice(self.vehicle_types)
                count = random.randint(1, 3)
                
                entry = {
                    "camera_id": cam["id"],
                    "camera_name": cam["name"],
                    "lat": cam["lat"],
                    "lng": cam["lng"],
                    "vehicle_type": v_type,
                    "count": count,
                    "timestamp": timestamp
                }
                self.data.append(entry)

    def get_latest_data(self):
        with self.lock:
            # Return a summary for the dashboard
            total_vehicles = len(self.unique_ids)
            
            # Aggregation by vehicle type
            by_type = {v: 0 for v in self.vehicle_types}
            for d in self.data:
                by_type[d['vehicle_type']] += d['count']
                
            # Aggregation by camera (for map)
            by_camera = {}
            for cam in self.camera_config:
                cam_data = [d for d in self.data if d['camera_id'] == cam['id']]
                
                # Get current "live" count (Unique Track IDs in last 5 seconds)
                # This is the most robust method. It counts how many UNIQUE vehicles (by ID)
                # have been seen in the recent window.
                
                now = datetime.datetime.now()
                recent_window = datetime.timedelta(seconds=5)
                
                # Filter data for this camera from the last 5 seconds
                recent_data = [d for d in self.data if d['camera_id'] == cam['id'] and (now - datetime.datetime.fromisoformat(d['timestamp'])) < recent_window]
                
                current_load = 0
                if recent_data:
                    # Collect all unique track IDs seen in this window
                    unique_ids_in_window = set()
                    for d in recent_data:
                        # Handle both old format (count only) and new format (track_ids list)
                        # Ideally we updated _process_cameras to save track_ids.
                        # For now, let's assume we update _process_cameras below or have done so.
                        # Wait, I need to update _process_cameras first? 
                        # I will assume I update storing logic in the same file edit or previous.
                        # Actually, looking at previous edit, I didn't update storage yet.
                        # So I must update _process_cameras to store 'track_ids'.
                        ids = d.get('track_ids', [])
                        unique_ids_in_window.update(ids)
                    
                    # If we have IDs, use them. If not (old data/simulated), fall back to max logic?
                    # The goal is ID counting. I will update _process_cameras to ensure IDs are stored.
                    current_load = len(unique_ids_in_window)
                    
                    # Fallback if no IDs found (e.g. simulated data or if tracking failed to assign IDs)
                    if current_load == 0 and recent_data:
                         # Fallback to Max logic just in case
                        frame_counts = []
                        timestamps = set(d['timestamp'] for d in recent_data)
                        for ts in timestamps:
                            count_in_frame = sum(d['count'] for d in recent_data if d['timestamp'] == ts)
                            frame_counts.append(count_in_frame)
                        current_load = max(frame_counts) if frame_counts else 0
                
                by_camera[cam['id']] = {
                    "lat": cam['lat'],
                    "lng": cam['lng'],
                    "name": cam['name'],
                    "total": current_load, # Use calculated MAX load
                    "lanes": cam.get("lanes", 2), # Default to 2 if missing
                    "breakdown": {v: sum(d['count'] for d in cam_data if d['vehicle_type'] == v) for v in self.vehicle_types} 
                    # Note: Breakdown is still cumulative from buffer, which is fine for charts, but 'total' is live load
                }

            # Generate Simulated Data (with Source Type)
            current_dummy_data = []
            for node in self.dummy_nodes:
                # Random traffic intensity
                count = random.randint(5, 50) 
                
                heading = node.copy()
                heading.update({
                    "total": count,
                     "lanes": 2, # Assume 2 lanes for dummy roads
                    "breakdown": {"car": count, "bike": 0, "bus": 0, "truck": 0},
                    "source_type": "simulated_cctv"
                })
                current_dummy_data.append(heading)

            # Combine real and simulated data
            # Ensure real camera data has source_type derived from config
            real_locations = list(by_camera.values())
            for loc in real_locations:
                 loc['source_type'] = next((c['source_type'] for c in self.camera_config if c['name'] == loc['name']), 'live_cctv')

            all_locations = real_locations + current_dummy_data
            
            if not all_locations:
                return {"total_vehicles": total_vehicles, "distribution": by_type, "locations": []}

            # --- Logic: Lane-Based Congestion ---
            # Green (free flow): total_vehicles <= lanes * 2
            # Yellow (moderate): lanes * 2 < total_vehicles <= lanes * 4
            # Red (congested): total_vehicles > lanes * 4
            
            for loc in all_locations:
                val = loc['total']
                lanes = loc.get('lanes', 2)
                
                threshold_green = lanes * 2
                threshold_yellow = lanes * 4
                
                if val <= threshold_green:
                    loc['intensity'] = 'low'
                    loc['weighted_intensity'] = 0.2
                elif val <= threshold_yellow:
                    loc['intensity'] = 'moderate'
                    loc['weighted_intensity'] = 0.5
                else:
                    loc['intensity'] = 'congestion' # Using 'congestion' map to Red
                    loc['weighted_intensity'] = 1.0

            # Set dashboard total to the specific live camera count (CAM_002)
            # This replaces the cumulative total with the "Current Vehicles in Frame"
            live_cam_data = by_camera.get("CAM_002")
            dashboard_total = live_cam_data['total'] if live_cam_data else 0

            return {
                "total_vehicles": dashboard_total,
                "distribution": by_type,
                "locations": all_locations
            }

traffic_system = TrafficAnalyzer(mode="auto")
