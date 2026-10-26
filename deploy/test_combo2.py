import subprocess, time
import display

path = "/home/ubuntu/audio-portal/data/audio/stretch_short.mp4"
job = display.start_video(path, 70, True, True)      # muted video, looped
time.sleep(2)
print("video path:", display.get_prop("path"), "| aid:", display.get_prop("aid"))
ff = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                       "-af", "volume=0.4", "-f", "wav", "-"], stdout=subprocess.PIPE)
ap = subprocess.run(["aplay", "-D", "plughw:CARD=vc4hdmi0,DEV=0"], stdin=ff.stdout,
                    capture_output=True, text=True)
print("aplay rc:", ap.returncode, "| stderr:", ap.stderr.strip() or "(none)")
job.terminate()
job.wait(timeout=5)
time.sleep(1)
print("after stop: path=", display.get_prop("path"), "idle-active=", display.get_prop("idle-active"))
