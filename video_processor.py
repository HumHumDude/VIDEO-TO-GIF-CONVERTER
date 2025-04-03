import os
import cv2
import numpy as np
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QSize
import sys
import subprocess

# Ensure all required packages are installed
required_packages = ['moviepy', 'imageio', 'imageio-ffmpeg', 'numpy']
for package in required_packages:
    try:
        __import__(package)
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Now try to import moviepy components
try:
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from moviepy.video.fx.resize import resize  # Import specific fx modules instead of all
    from moviepy.video.fx.crop import crop
    print("Successfully imported moviepy components")
except ImportError as e:
    print(f"Error importing moviepy components: {e}")
    
    # Custom VideoFileClip implementation as fallback
    class VideoFileClip:
        def __init__(self, filename):
            print(f"Using custom VideoFileClip for: {filename}")
            self.filename = filename
            self.cap = cv2.VideoCapture(filename)
            if not self.cap.isOpened():
                raise ValueError(f"Could not open video file {filename}")
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.duration = self.frame_count / self.fps if self.fps > 0 else 0
            self.size = (
                int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            )
            self._initialize()
            
        def _initialize(self):
            """Initialize default values"""
            self.start_time = 0
            self.end_time = self.duration
            self.target_size = self.size
            self.crop_area = None
            self.output_fps = self.fps
            print(f"Initialized video: {self.size[0]}x{self.size[1]}, {self.fps} fps, {self.duration:.2f}s")
            
        def subclip(self, start_time, end_time):
            """Create a subclip by setting start and end times"""
            print(f"Creating subclip from {start_time:.2f}s to {end_time:.2f}s")
            clip = VideoFileClip(self.filename)
            clip.start_time = max(0, start_time)
            clip.end_time = min(self.duration, end_time)
            return clip
            
        def resize(self, width=None, height=None):
            """Set resize dimensions"""
            print(f"Setting resize to {width}x{height}")
            self.target_size = (width or self.size[0], height or self.size[1])
            return self
            
        def crop(self, x1=0, y1=0, x2=None, y2=None):
            """Set crop area"""
            print(f"Setting crop area: ({x1}, {y1}) to ({x2}, {y2})")
            self.crop_area = (x1, y1, x2 or self.size[0], y2 or self.size[1])
            return self
            
        def set_fps(self, fps):
            """Set the output fps"""
            print(f"Setting output FPS to {fps}")
            self.output_fps = fps
            return self
            
        def write_gif(self, output_path, fps=None, program='ffmpeg', **kwargs):
            """Create a GIF using OpenCV and imageio"""
            print(f"Creating GIF: {output_path}")
            try:
                import imageio
                
                # Calculate frame range
                start_frame = int(self.start_time * self.fps)
                end_frame = int(self.end_time * self.fps)
                total_frames = end_frame - start_frame
                
                # Calculate frame selection to maintain original speed at lower fps
                target_fps = fps or self.output_fps
                time_duration = self.end_time - self.start_time
                desired_frame_count = int(time_duration * target_fps)
                
                # Calculate frame step to maintain original speed
                frame_step = total_frames / desired_frame_count if desired_frame_count > 0 else 1
                
                frames = []
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                
                print(f"Extracting frames: duration={time_duration:.2f}s, target_fps={target_fps}, frame_step={frame_step:.2f}")
                current_frame = start_frame
                frame_count = 0
                
                while current_frame < end_frame and frame_count < desired_frame_count:
                    # Set position to the next frame we want
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(current_frame))
                    ret, frame = self.cap.read()
                    if not ret:
                        break
                        
                    # Process frame
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Apply crop if specified
                    if self.crop_area:
                        x1, y1, x2, y2 = self.crop_area
                        frame = frame[y1:y2, x1:x2]
                    
                    # Apply resize if needed
                    if self.target_size != self.size:
                        frame = cv2.resize(frame, self.target_size)
                    
                    frames.append(frame)
                    frame_count += 1
                    
                    # Move to next frame position to maintain original speed
                    current_frame += frame_step
                
                if frames:
                    print(f"Writing {len(frames)} frames to GIF at {target_fps} fps")
                    imageio.mimsave(output_path, frames, fps=target_fps)
                    print("GIF created successfully")
                    return True
                else:
                    print("No frames were extracted")
                    return False
                    
            except Exception as e:
                print(f"Error creating GIF: {str(e)}")
                return False
            finally:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        def get_frame(self, t):
            """Get a specific frame at time t"""
            frame_idx = int(t * self.fps)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return None
            
        def close(self):
            """Clean up resources"""
            if hasattr(self, 'cap'):
                self.cap.release()

class VideoProcessor:
    def __init__(self):
        self.cap = None
        self.video_path = None
        self.fps = 0
        self.frame_count = 0
        self.duration = 0
        self.width = 0
        self.height = 0
    
    def load_video(self, video_path):
        """Load a video file and extract its properties"""
        try:
            # If it's a GIF, we need to use moviepy to load it
            if video_path.lower().endswith('.gif'):
                clip = VideoFileClip(video_path)
                self.fps = clip.fps
                self.frame_count = int(clip.fps * clip.duration)
                self.duration = clip.duration
                self.width = int(clip.size[0])
                self.height = int(clip.size[1])
                clip.close()
                
                # OpenCV can still read GIFs frame by frame
                self.cap = cv2.VideoCapture(video_path)
                if not self.cap.isOpened():
                    return False
            else:
                # For other video formats, use OpenCV
                self.cap = cv2.VideoCapture(video_path)
                if not self.cap.isOpened():
                    return False
                
                self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.duration = self.frame_count / self.fps if self.fps > 0 else 0
                self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.video_path = video_path
            return True
        except Exception as e:
            print(f"Error loading video: {str(e)}")
            return False
    
    def create_gif(self, output_path, start_time, end_time, fps, dimensions, quality, crop_rect=None, loop=True, progress_callback=None, segments=None, speed_factor=1.0):
        """Create a GIF with the specified parameters
        
        Args:
            output_path: Path to save the output GIF
            start_time: Start time for the primary segment
            end_time: End time for the primary segment
            fps: Frames per second
            dimensions: (width, height) tuple
            quality: Quality factor from 0-1
            crop_rect: Optional (x, y, w, h) tuple for cropping frames
            loop: Whether the GIF should loop
            progress_callback: Optional function to receive progress updates
            segments: Optional list of (start, end) tuples for segments to include in the final GIF
                      If provided, these segments override the start_time and end_time parameters
            speed_factor: Speed multiplier for the GIF (>1 is faster, <1 is slower)
        """
        if not self.cap or not self.cap.isOpened():
            return False
            
        try:
            # Use MoviePy for GIF creation which gives better quality control
            if os.path.exists(self.video_path):
                # Ensure VideoFileClip is available
                if VideoFileClip is None:
                    print("Error: VideoFileClip is not available")
                    return False
                    
                if segments and len(segments) > 0:
                    # If we have specific segments to include
                    print(f"Creating GIF with {len(segments)} segments and speed factor {speed_factor}x")
                    
                    try:
                        import tempfile
                        import imageio
                        
                        # Create a temporary directory for segment GIFs
                        with tempfile.TemporaryDirectory() as temp_dir:
                            all_frames = []
                            target_width, target_height = dimensions
                            
                            # Process each segment
                            for i, (seg_start, seg_end) in enumerate(segments):
                                if progress_callback:
                                    segment_progress = i / len(segments) * 40  # 0-40% for segment processing
                                    progress_callback(int(segment_progress))
                                
                                # Important: create a subclip using the original segment times, not adjusted for speed
                                clip = VideoFileClip(self.video_path).subclip(seg_start, seg_end)
                                seg_duration = clip.duration
                                
                                # Apply cropping if needed
                                if crop_rect is not None:
                                    x, y, w, h = crop_rect
                                    clip = clip.crop(x1=x, y1=y, x2=x+w, y2=y+h)
                                
                                # Always apply resize to ensure consistent dimensions across segments
                                clip = clip.resize(height=target_height, width=target_width)
                                
                                # Set output fps
                                clip = clip.set_fps(fps)
                                
                                # Calculate how many frames we want in the final output
                                # Apply speed factor to determine frame count
                                # Higher speed = fewer frames
                                frame_count = int(seg_duration * fps / speed_factor)
                                
                                # Extract frames at proper intervals to achieve the desired speed
                                segment_frames = []
                                if frame_count > 0:
                                    # Calculate the time step between frames
                                    # For higher speeds, we take larger steps through the original clip
                                    time_step = seg_duration / frame_count
                                    
                                    for f in range(frame_count):
                                        # Calculate time point in the clip
                                        frame_time = f * time_step
                                        
                                        if frame_time <= seg_duration:
                                            try:
                                                frame = clip.get_frame(frame_time)
                                                
                                                # Ensure frame has correct dimensions
                                                if frame.shape[0] != target_height or frame.shape[1] != target_width:
                                                    frame = cv2.resize(frame, (target_width, target_height))
                                                    
                                                segment_frames.append(frame)
                                                
                                                # Update progress periodically
                                                if progress_callback and f % 5 == 0:
                                                    progress = 40 + (i / len(segments) + (f / frame_count) / len(segments)) * 50
                                                    progress_callback(min(89, int(progress)))
                                            except Exception as frame_error:
                                                print(f"Error processing frame at {frame_time}s: {frame_error}")
                                                continue
                                
                                # Check segment frames before adding
                                if segment_frames:
                                    # Double-check all frames in this segment have the same dimensions
                                    first_frame = segment_frames[0]
                                    segment_frames = [frame for frame in segment_frames if frame.shape == first_frame.shape]
                                    
                                    # Add shapes debug info
                                    if len(segment_frames) > 0:
                                        print(f"Segment {i+1}: Adding {len(segment_frames)} frames with shape {segment_frames[0].shape}")
                                        
                                        # Only add frames if we have a non-empty segment
                                        # If all_frames already has frames, ensure new frames match existing dimensions
                                        if all_frames and segment_frames and segment_frames[0].shape != all_frames[0].shape:
                                            print(f"Warning: Shape mismatch. Existing: {all_frames[0].shape}, New: {segment_frames[0].shape}")
                                            # Resize all new frames to match existing frames
                                            h, w = all_frames[0].shape[:2]
                                            segment_frames = [cv2.resize(frame, (w, h)) for frame in segment_frames]
                                            
                                        all_frames.extend(segment_frames)
                                clip.close()
                            
                            if all_frames:
                                # Verify all frames have the same shape
                                first_frame_shape = all_frames[0].shape
                                compatible_frames = []
                                
                                for i, frame in enumerate(all_frames):
                                    if frame.shape == first_frame_shape:
                                        compatible_frames.append(frame)
                                    else:
                                        try:
                                            # Try to resize any mismatched frames
                                            print(f"Resizing frame {i} from {frame.shape} to {first_frame_shape}")
                                            resized = cv2.resize(frame, (first_frame_shape[1], first_frame_shape[0]))
                                            compatible_frames.append(resized)
                                        except Exception as e:
                                            print(f"Could not resize frame {i}: {e}")
                                
                                # Replace frames with compatible frames
                                if compatible_frames:
                                    all_frames = compatible_frames
                                    print(f"Final frame count after compatibility check: {len(all_frames)}")
                                else:
                                    print("No compatible frames after filtering!")
                                    return False
                                
                                # Use imageio to write the gif with loop parameter
                                loop_param = 0 if loop else 1
                                
                                if progress_callback:
                                    progress_callback(90)  # Starting file write
                                
                                print(f"Writing GIF with {len(all_frames)} frames, shape: {all_frames[0].shape}")
                                imageio.mimsave(output_path, all_frames, fps=fps, 
                                                quantizer=int(100-quality*100), loop=loop_param)
                                
                                if progress_callback:
                                    progress_callback(100)  # Complete
                                    
                                print(f"Successfully created GIF with {len(all_frames)} frames from {len(segments)} segments")
                                return True
                            else:
                                print("No frames were extracted")
                                return False
                                
                    except Exception as e:
                        print(f"Error creating multi-segment GIF: {e}")
                        import traceback
                        traceback.print_exc()
                        return False
                else:
                    # Standard single-segment GIF creation
                    clip = VideoFileClip(self.video_path).subclip(start_time, end_time)
                    seg_duration = clip.duration
                    
                    # Apply cropping if needed
                    if crop_rect is not None:
                        x, y, w, h = crop_rect
                        clip = clip.crop(x1=x, y1=y, x2=x+w, y2=y+h)
                    
                    # Resize if needed
                    target_width, target_height = dimensions
                    if target_width != self.width or target_height != self.height:
                        clip = clip.resize(height=target_height, width=target_width)
                    
                    # Set output fps
                    clip = clip.set_fps(fps)
                    
                    # Apply speed factor before writing the GIF
                    if speed_factor != 1.0:
                        # Extract frames with speed factor applied
                        print(f"Applying speed factor of {speed_factor}x to segment {start_time:.2f}s-{end_time:.2f}s")
                        frames = []
                        
                        # Get a sample frame to establish the correct dimensions
                        sample_frame = clip.get_frame(0)
                        correct_shape = sample_frame.shape
                        
                        # Calculate how many frames we want in the final output
                        # Apply speed factor to determine frame count
                        # Higher speed = fewer frames
                        frame_count = int(seg_duration * fps / speed_factor)
                        
                        if frame_count > 0:
                            # Calculate the time step between frames
                            # For higher speeds, we take larger steps through the original clip
                            time_step = seg_duration / frame_count
                            
                            for f in range(frame_count):
                                # Calculate time point in the clip
                                frame_time = f * time_step
                                
                                if frame_time <= seg_duration:
                                    try:
                                        frame = clip.get_frame(frame_time)
                                        
                                        # Ensure frame has the correct dimensions
                                        if frame.shape != correct_shape:
                                            print(f"Correcting frame shape from {frame.shape} to {correct_shape}")
                                            frame = cv2.resize(frame, (correct_shape[1], correct_shape[0]))
                                            
                                        frames.append(frame)
                                        
                                        # Update progress periodically
                                        if progress_callback and f % 5 == 0:
                                            progress_percent = 30 + (f / frame_count * 60)
                                            progress_callback(min(89, int(progress_percent)))
                                    except Exception as e:
                                        print(f"Error extracting frame at time {frame_time}: {e}")
                                        continue
                        
                        # Verify all frames have the same shape before saving
                        if frames:
                            # Double-check that all frames have the same dimensions
                            first_shape = frames[0].shape
                            filtered_frames = []
                            
                            for i, frame in enumerate(frames):
                                if frame.shape == first_shape:
                                    filtered_frames.append(frame)
                                else:
                                    try:
                                        # Try to resize any mismatched frames
                                        print(f"Resizing frame {i} from {frame.shape} to {first_shape}")
                                        resized = cv2.resize(frame, (first_shape[1], first_shape[0]))
                                        filtered_frames.append(resized)
                                    except Exception as e:
                                        print(f"Could not resize frame {i}: {e}")
                            
                            frames = filtered_frames
                            
                            if frames:
                                # Use progress callback if provided
                                if progress_callback:
                                    progress_callback(80)  # Report 80% progress after frame extraction
                                    
                                # Write frames to GIF using imageio
                                import imageio
                                loop_param = 0 if loop else 1
                                print(f"Writing GIF with {len(frames)} frames, shape: {frames[0].shape}")
                                imageio.mimsave(output_path, frames, fps=fps, quantizer=int(100-quality*100), loop=loop_param)
                                
                                if progress_callback:
                                    progress_callback(100)  # Complete the progress
                                    
                                clip.close()
                                print(f"Created GIF with speed factor {speed_factor}x using {len(frames)} frames")
                                return True
                            else:
                                print("No valid frames after filtering")
                                # Fall through to standard methods
                    
                    # If no speed factor or frame extraction failed, try the standard methods
                    # Use progress callback if provided
                    if progress_callback:
                        progress_callback(30)  # Report 30% progress after setup
                    
                    # Write the GIF - try different methods
                    # Set loop parameter: 0 means loop forever, 1 means play once
                    loop_param = 0 if loop else 1
                    
                    try:
                        # First try the standard method with optimization
                        print("Attempting to write GIF with optimization...")
                        clip.write_gif(output_path, fps=fps, opt="OptimizePlus", fuzz=int((1-quality)*100), loop=loop_param)
                        if progress_callback:
                            progress_callback(90)  # Report 90% progress after main operation
                    except (TypeError, AttributeError) as e:
                        print(f"First GIF write method failed: {e}")
                        try:
                            # Try a different method with fewer parameters
                            print("Trying alternative GIF writing method...")
                            clip.write_gif(output_path, fps=fps, program='ffmpeg', loop=loop_param)
                            if progress_callback:
                                progress_callback(90)
                        except Exception as e2:
                            print(f"Second GIF write method failed: {e2}")
                            # Last resort - try to use imageio directly
                            try:
                                print("Trying direct imageio method...")
                                import imageio
                                # Get frames from the clip
                                frames = []
                                # Apply speed factor to frame extraction
                                for t in range(int(clip.duration * fps)):
                                    # Apply speed factor by adjusting the time point we sample
                                    frame_time = (t / fps) * speed_factor
                                    if frame_time <= clip.duration:
                                        frame = clip.get_frame(frame_time)
                                        frames.append(frame)
                                        if progress_callback and t % 5 == 0:  # Update progress periodically
                                            progress_percent = 30 + (t / (clip.duration * fps) * 60)
                                            progress_callback(min(89, int(progress_percent)))

                                if frames:
                                    # Use imageio to write the gif with loop parameter
                                    imageio.mimsave(output_path, frames, fps=fps, quantizer=int(100-quality*100), loop=loop_param)
                                    if progress_callback:
                                        progress_callback(90)
                                    print(f"Successfully created GIF using imageio with {len(frames)} frames")
                                else:
                                    print("No frames were extracted")
                                    return False
                            except Exception as e3:
                                print(f"All GIF writing methods failed: {e3}")
                                return False
                    
                    if progress_callback:
                        progress_callback(100)  # Complete the progress
                    
                    clip.close()
                    return True
            return False
        except Exception as e:
            print(f"Error creating GIF: {str(e)}")
            return False
    
    def get_dimensions(self):
        """Return the dimensions of the loaded video"""
        return self.width, self.height
    
    def get_frame(self, frame_number):
        """Get a specific frame by number"""
        if not self.cap or not self.cap.isOpened():
            return None
        
        # Set position to the requested frame
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        
        if not ret:
            return None
            
        # Convert from BGR to RGB
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    def get_frame_at_time(self, time_seconds):
        """Get a frame at a specific time point"""
        if not self.cap or not self.cap.isOpened():
            return None
            
        frame_number = int(time_seconds * self.fps)
        return self.get_frame(frame_number)
    
    def get_thumbnails(self, count=10):
        """Generate thumbnails across the video duration"""
        thumbnails = []
        
        if not self.cap or not self.cap.isOpened() or self.frame_count == 0:
            return thumbnails
            
        # Calculate frame intervals for evenly distributed thumbnails
        if self.frame_count <= count:
            frames_to_extract = range(self.frame_count)
        else:
            step = self.frame_count // count
            frames_to_extract = range(0, self.frame_count, step)[:count]
        
        # Extract frames
        for frame_num in frames_to_extract:
            frame = self.get_frame(frame_num)
            if frame is not None:
                # Resize for thumbnail
                thumb_height = 60
                thumb_width = int(self.width * thumb_height / self.height)
                thumbnail = cv2.resize(frame, (thumb_width, thumb_height))
                thumbnails.append(thumbnail)
        
        return thumbnails
    
    def _apply_processing(self, frame, dimensions, crop_rect=None):
        """Apply processing to a frame"""
        if frame is None:
            return None
            
        # Apply cropping if specified
        if crop_rect is not None:
            x, y, w, h = crop_rect
            frame = frame[y:y+h, x:x+w]
        
        # Resize if needed
        target_width, target_height = dimensions
        if target_width != frame.shape[1] or target_height != frame.shape[0]:
            frame = cv2.resize(frame, (target_width, target_height))
        
        return frame
    
    def generate_preview(self, start_time, end_time, fps, dimensions, quality, crop_rect=None, segments=None, speed_factor=1.0):
        """Generate a preview of the GIF with current settings
        
        Args:
            start_time: Start time for the primary segment
            end_time: End time for the primary segment
            fps: Frames per second
            dimensions: (width, height) tuple
            quality: Quality factor from 0-1
            crop_rect: Optional (x, y, w, h) tuple for cropping frames
            segments: Optional list of (start, end) tuples to include in the preview
                     If provided, these override the start_time and end_time parameters
            speed_factor: Speed multiplier for the GIF (>1 is faster, <1 is slower)
        """
        if not self.cap or not self.cap.isOpened():
            return []
            
        preview_frames = []
        
        # Adjust FPS based on speed factor
        adjusted_fps = fps * speed_factor
        
        if segments:
            # Process each segment for preview
            for seg_start, seg_end in segments:
                # Calculate frame numbers for this segment
                seg_start_frame = int(seg_start * self.fps)
                seg_end_frame = int(seg_end * self.fps)
                seg_duration = seg_end - seg_start
                
                # How many frames to capture for this segment at the target fps
                # Apply speed factor to determine how many frames to extract
                seg_desired_frames = int(seg_duration * fps)
                seg_total_frames = seg_end_frame - seg_start_frame
                
                # Adjust frame step by speed factor
                # Higher speed factor = larger step = fewer frames
                seg_frame_step = (seg_total_frames / seg_desired_frames) * speed_factor if seg_desired_frames > 0 else 1
                
                # Collect frames for this segment
                seg_current_frame = seg_start_frame
                seg_frame_count = 0
                
                while seg_current_frame < seg_end_frame and seg_frame_count < seg_desired_frames:
                    # Get frame at calculated position
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(seg_current_frame))
                    frame = self.get_frame(int(seg_current_frame))
                    
                    if frame is not None:
                        processed = self._apply_processing(frame, dimensions, crop_rect)
                        if processed is not None:
                            preview_frames.append(processed)
                            seg_frame_count += 1
                    
                    # Move to next frame position with speed factor adjustment
                    seg_current_frame += seg_frame_step
        else:
            # Standard single segment preview
            # Calculate frame numbers and timing
            start_frame = int(start_time * self.fps)
            end_frame = int(end_time * self.fps)
            duration = end_time - start_time
            
            # Calculate frame selection accounting for speed factor
            desired_frames = int(duration * fps)  # Number of frames needed for target fps
            total_frames = end_frame - start_frame
            
            # Adjust frame step by speed factor
            # Higher speed factor = larger step = fewer frames
            frame_step = (total_frames / desired_frames) * speed_factor if desired_frames > 0 else 1
            
            # Collect frames for the preview
            current_frame = start_frame
            frame_count = 0
            
            while current_frame < end_frame and frame_count < desired_frames:
                # Get frame at calculated position
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, int(current_frame))
                frame = self.get_frame(int(current_frame))
                
                if frame is not None:
                    processed = self._apply_processing(frame, dimensions, crop_rect)
                    if processed is not None:
                        preview_frames.append(processed)
                        frame_count += 1
                
                # Move to next frame position with speed factor adjustment
                current_frame += frame_step
        
        return preview_frames, adjusted_fps
    
    def is_loaded(self):
        """Check if a video is loaded"""
        return self.cap is not None and self.cap.isOpened()
    
    def __del__(self):
        """Clean up resources"""
        if self.cap is not None:
            self.cap.release()