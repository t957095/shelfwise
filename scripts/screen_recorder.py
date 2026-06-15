"""
Screen recorder for ShelfWise demo video.
Uses mss for screen capture and opencv for video encoding.
"""
import argparse
import time
import cv2
import numpy as np
import mss


def record_screen(output_path, fps=30, duration=None, monitor=1):
    """Record the screen to a video file."""
    with mss.mss() as sct:
        monitor_info = sct.monitors[monitor]
        width = monitor_info["width"]
        height = monitor_info["height"]
        left = monitor_info["left"]
        top = monitor_info["top"]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        if not out.isOpened():
            raise RuntimeError(f"Could not open video writer for {output_path}")

        print(f"Recording {width}x{height} at {fps} fps to {output_path}")
        start = time.time()
        frame_count = 0
        try:
            while True:
                screenshot = sct.grab(monitor_info)
                frame = np.array(screenshot)
                # mss returns BGRA, convert to BGR for OpenCV
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                out.write(frame)
                frame_count += 1
                elapsed = time.time() - start
                if duration and elapsed >= duration:
                    break
                # simple frame pacing
                expected = frame_count / fps
                if expected > elapsed:
                    time.sleep(expected - elapsed)
        except KeyboardInterrupt:
            pass
        finally:
            out.release()
            elapsed = time.time() - start
            print(f"Saved {frame_count} frames over {elapsed:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="shelfwise_demo.mp4")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--duration", type=int, default=None)
    parser.add_argument("--monitor", type=int, default=1)
    args = parser.parse_args()
    record_screen(args.output, args.fps, args.duration, args.monitor)
