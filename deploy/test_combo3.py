import subprocess, time
import display

path = "/home/ubuntu/audio-portal/data/audio/stretch_short.mp4"
job = display.start_video(path, 70, True, True)      # muted video, looped
time.sleep(3)
print("video path ok:", display.get_prop("path") == path,
      "| pan during video:", display.get_prop("video-pan-x"), display.get_prop("video-pan-y"),
      "| audio track:", display.get_prop("aid"))
ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                       "-af", "volume=0.4", "-f", "wav", "-"], stdout=subprocess.PIPE)
ap = subprocess.run(["aplay", "-q", "-D", "plughw:CARD=vc4hdmi0,DEV=0"], stdin=ff.stdout,
                    capture_output=True, text=True)
print("aplay rc:", ap.returncode, "| stderr:", ap.stderr.strip() or "(none)")
job.terminate(); job.wait(timeout=5)
time.sleep(3)
print("back on floating screen:", "/screen/screen_" in str(display.get_prop("path")))
