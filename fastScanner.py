import cv2
import numpy as np
import mss
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Dict, List, Tuple, Optional

class FastTemplateScanner:
    def __init__(self, template_paths: Dict[str, str], confidence_threshold: float = 0.8):
        """
        Initialize the template scanner.
        
        Args:
            template_paths: Dict mapping template names to file paths
            confidence_threshold: Minimum confidence for matches
        """
        self.confidence_threshold = confidence_threshold
        self.templates = {}
        self.template_info = {}
        
        # Load and preprocess templates
        self._load_templates(template_paths)
        
    def _load_templates(self, template_paths: Dict[str, str]):
        """Load and preprocess templates for faster matching."""
        for name, path in template_paths.items():
            try:
                # Load template
                if 'gray' in name.lower():
                    template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                else:
                    template = cv2.imread(path, cv2.IMREAD_COLOR)
                
                if template is None:
                    print(f"Warning: Could not load template {path}")
                    continue
                
                # Ensure template is uint8
                template = template.astype(np.uint8)
                
                # Store original template
                self.templates[name] = template
                
                # Store template info for result positioning
                h, w = template.shape[:2]
                self.template_info[name] = {'width': w, 'height': h}
                
                print(f"Loaded template {name}: shape={template.shape}, dtype={template.dtype}")
                
            except Exception as e:
                print(f"Error loading template {path}: {e}")
                
    def _match_template_worker(self, args) -> Tuple[str, Optional[Tuple[int, int]], float]:
        """Worker function for parallel template matching."""
        template_name, template, screenshot, is_grayscale = args
        
        try:
            # Handle screenshot color space
            if len(screenshot.shape) == 4:  # BGRA
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            # Handle template color space
            if is_grayscale:
                if len(template.shape) == 3:  # If template is BGR
                    template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
                if len(screenshot.shape) == 3:  # If screenshot is BGR
                    screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            else:
                if len(template.shape) != len(screenshot.shape):
                    print(f"Warning: shape mismatch for {template_name}. Template: {template.shape}, Screenshot: {screenshot.shape}")
                    if len(template.shape) == 2:  # Grayscale template
                        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                    elif len(screenshot.shape) == 2:  # Grayscale screenshot
                        template = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
            
            # Ensure same data type
            screenshot = screenshot.astype(np.uint8)
            template = template.astype(np.uint8)
            
            # Do the template matching
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            
            # Find best match
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= self.confidence_threshold:
                return template_name, max_loc, max_val
            else:
                return template_name, None, max_val
                
        except Exception as e:
            print(f"Error matching template {template_name}: {e}")
            return template_name, None, 0.0
    
    def scan_screen(self, region: Optional[Dict] = None, max_workers: int = 4) -> Dict[str, Dict]:
        """
        Scan the screen for all templates using parallel processing.
        
        Args:
            region: Screen region to capture ({"top": y, "left": x, "width": w, "height": h})
            max_workers: Number of parallel workers for template matching
            
        Returns:
            Dict with template names as keys and match info as values
        """
        # Capture screenshot with MSS
        with mss.mss() as sct:
            # Required keys for a region
            required_keys = {"top", "left", "width", "height"}

            if not isinstance(region, dict) or not required_keys.issubset(region.keys()):
                # Fall back to capturing full screen if region is incomplete
                region = sct.monitors[1]

            screenshot = sct.grab(region)
        # Convert to OpenCV format
        screenshot_np = np.array(screenshot)
        screenshot_bgr = cv2.cvtColor(screenshot_np, cv2.COLOR_BGRA2BGR)
        
        # Prepare arguments for parallel processing
        match_args = []
        for name, template in self.templates.items():
            # Determine if this is a grayscale template
            is_grayscale = name.endswith('_gray') or 'gray' in name.lower()
            match_args.append((name, template, screenshot_bgr, is_grayscale))
        
        # Execute parallel template matching
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_template = {
                executor.submit(self._match_template_worker, args): args[0] 
                for args in match_args
            }
            
            for future in as_completed(future_to_template):
                template_name, location, confidence = future.result()
                
                if location is not None:
                    # Calculate bounding box
                    template_info = self.template_info.get(
                        template_name.replace('_gray', ''), 
                        {'width': 0, 'height': 0}
                    )
                    
                    results[template_name] = {
                        'location': location,
                        'confidence': confidence,
                        'center': (
                            location[0] + template_info['width'] // 2,
                            location[1] + template_info['height'] // 2
                        ),
                        'bounding_box': (
                            location[0], 
                            location[1],
                            location[0] + template_info['width'],
                            location[1] + template_info['height']
                        )
                    }
        
        return results
    
    def scan_roi_regions(self, roi_regions: List[Dict], max_workers: int = 4) -> Dict[str, Dict]:
        """
        Scan multiple ROI regions efficiently.
        
        Args:
            roi_regions: List of regions to scan
            max_workers: Number of parallel workers
            
        Returns:
            Combined results from all regions
        """
        all_results = {}
        
        for i, region in enumerate(roi_regions):
            region_results = self.scan_screen(region, max_workers)
            
            # Adjust coordinates to absolute screen coordinates
            for template_name, result in region_results.items():
                result['location'] = (
                    result['location'][0] + region['left'],
                    result['location'][1] + region['top']
                )
                result['center'] = (
                    result['center'][0] + region['left'],
                    result['center'][1] + region['top']
                )
                bbox = result['bounding_box']
                result['bounding_box'] = (
                    bbox[0] + region['left'],
                    bbox[1] + region['top'],
                    bbox[2] + region['left'],
                    bbox[3] + region['top']
                )
                
                all_results[f"{template_name}"] = result
        
        return all_results

# Example usage
if __name__ == "__main__":
    # Define your templates
    template_paths = {
        "save_button": "templates/save_button.png",
        "close_button": "templates/close_button.png",
        "gray_icon": "templates/gray_icon.png",  # This will be processed as grayscale
        "menu_item": "templates/menu_item.png"
    }
    
    # Initialize scanner
    scanner = FastTemplateScanner(template_paths, confidence_threshold=0.8)
    
    # Example 1: Scan entire screen
    print("Scanning entire screen...")
    start_time = time.time()
    results = scanner.scan_screen(max_workers=4)
    scan_time = time.time() - start_time
    
    print(f"Scan completed in {scan_time:.3f} seconds")
    for template_name, match_info in results.items():
        print(f"Found {template_name} at {match_info['location']} with confidence {match_info['confidence']:.3f}")
    
    # Example 2: Scan specific regions (faster for UI elements)
    roi_regions = [
        {"top": 0, "left": 0, "width": 1920, "height": 100},      # Top toolbar
        {"top": 0, "left": 1820, "width": 100, "height": 1080},   # Right sidebar
        {"top": 980, "left": 0, "width": 1920, "height": 100}     # Bottom status bar
    ]
    
    print("\nScanning ROI regions...")
    start_time = time.time()
    roi_results = scanner.scan_roi_regions(roi_regions, max_workers=4)
    roi_scan_time = time.time() - start_time
    
    print(f"ROI scan completed in {roi_scan_time:.3f} seconds")
    for template_name, match_info in roi_results.items():
        print(f"Found {template_name} at {match_info['location']} with confidence {match_info['confidence']:.3f}")
    
    # Example 3: Continuous monitoring
    print("\nStarting continuous monitoring (Ctrl+C to stop)...")
    try:
        while True:
            start_time = time.time()
            results = scanner.scan_screen(max_workers=4)
            
            if results:
                print(f"Found {len(results)} elements in {time.time() - start_time:.3f}s")
                for name, info in results.items():
                    print(f"  {name}: {info['center']}")
            
            time.sleep(0.1)  # Adjust scan frequency as needed
            
    except KeyboardInterrupt:
        print("Monitoring stopped")