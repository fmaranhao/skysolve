#pi camera to be used with web based GUI plate solver
import io
import time
from tkinter import EXCEPTION
#import picamera                                                                                             # Original PiCamera command
import picamera2                                                                                             # Compatible Picamera2 command

from fractions import Fraction
import threading
try:
    from greenlet import getcurrent as get_ident
except ImportError:
    try:
        from thread import get_ident
    except ImportError:
        from _thread import get_ident

class imageEvent(object):
    """An Event-like class that signals all active clients when a new frame is
    available.
    """
    def __init__(self):
        self.events = {}

    def wait(self, tt = 60.):
        """Invoked from each client's thread to wait for the next frame."""
        ident = get_ident()
        if ident not in self.events:
            # this is a new client
            # add an entry for it in the self.events dict
            # each entry has two elements, a threading.Event() and a timestamp
            self.events[ident] = [threading.Event(), time.time()]
        return self.events[ident][0].wait(timeout = tt)

    def set(self):
        """Invoked by the camera thread when a new frame is available."""
        now = time.time()
        remove = None
        for ident, event in self.events.items():
            if not event[0].isSet():
                # if this client's event is not set, then set it
                # also update the last set timestamp to now
                event[0].set()
                event[1] = now
            else:
                # if the client's event is already set, it means the client
                # did not process a previous frame
                # if the event stays set for more than 5 seconds, then assume
                # the client is gone and remove it
                if now - event[1] > 5:
                    remove = ident
        if remove:
            del self.events[remove]

    def clear(self):
        """Invoked from each client's thread after a frame was processed."""
        self.events[get_ident()][0].clear()

"""  my new py camera class
    does not derive from a base class
    needs init to start frame thread
    needs __del__ method to kill that thread  maybe in a close function

    Don't think any static methods are needed.

    thread camera gain init function and call in init 


"""

class skyCamera():
    camera = None
    previewConfig = None                                                                                     # Compatible Picamera2 command
    captureConfig = None                                                                                     # Compatible Picamera2 command
    frameRate = 1/6
    event = imageEvent()
    thread = None  # background thread that reads frames from camera
    gainThread = None
    frame = None  # current frame is stored here by background thread
    shutter = 1000000
    ISO=800
    resolution= (2000,1500)
    abortMode = False
    runMode = True
    cameraStopped = True
    format = 'jpeg'
    def __init__(self, skystatus, shutter=1000000, ISO=800, resolution=(2000,1500), format = 'jpeg'):
        print("skystatus", skystatus)
        self.skyStatus = skystatus
        #self.camera = picamera.PiCamera()                                                                   # Original PiCamera command
        self.camera = picamera2.Picamera2()                                                                  # Compatible Picamera2 command
        #self.camera.resolution = (2000,1500)                                                                # Original PiCamera command
        self.previewConfig = self.camera.create_preview_configuration({"size": (640,480)})                   # Compatible Picamera2 command
        if type(resolution) is str:                                                                          # Compatible Picamera2 command
            resolution = tuple(map(int, resolution.split('x')))                                              # Compatible Picamera2 command
        self.captureConfig = self.camera.create_still_configuration({"size": resolution})                    # Compatible Picamera2 command
        self.camera.set_controls({"FrameDurationLimits": (self.frameRate*1000000,self.frameRate*1000000)})   # Compatible Picamera2 command
        #self.camera.framerate = Fraction(1,6)                                                               # Original PiCamera command
        self.camera.start_preview(picamera2.Preview.NULL)
        self.camera.configure(self.previewConfig)
        self.camera.start()
        self.shutter=shutter
        self.ISO=ISO
        self.resolution=resolution
        self.format = format
        self.setupGain()
        self.count = 0
        self.thread = threading.Thread(target=self._thread)
        self.thread.start()



    def __del__(self):
        if self.camera:
            self.camera.close()
            
    def pause(self):
        self.runMode = False

    def resume(self):
        self.runMode = True

    def setISO(self, iso):
        self.ISO = iso
        self.setupGain()

    def status(self):
        return [self.ISO, self.camera.shutter_speed, self.resolution]

    def setResolution(self,  size):
        self.resolution = size
        self.runMode = False
        print ("waiting for camera to stop to set resolution",flush=True)
        while not self.cameraStopped:
            time.sleep(.2)
        res = tuple(map(int, size.split('x')))
        #print ("setting resolution", res, self.camera.resolution, flush=True)                               # Original PiCamera command
        #self.camera.resolution = res                                                                        # Compatible Picamera2 command
        print ("setting resolution", res, flush=True)
        self.captureConfig = self.camera.create_still_configuration({"size": res})
        self.runMode = True

    def setFormat(self,type):
        self.format = type
        self.runMode = False
        while not self.cameraStopped:
            time.sleep(.2)
        self.runMode = True

    def setShutter(self, value):
        #self.camera.shutter_speed = value                                                                   # Original PiCamera command
        self.shutter = value
        self.setupGain()
        print ("new shutter speed", value, flush=True)

    def setupGain(self):
        #make sure previous instance gain thread is not already running
        if self.gainThread:
            self.gainThread.join()
        self.gainThread = threading.Thread(target=self.setGainThread)
        self.gainThread.start()

    def setGainThread(self):
        if self.camera:
            self.runMode = False
  
        print ("cam setup called",flush=True)
        selfrunMode = False
        self.skyStatus(4," stopping camera to apply changes")
        while not self.cameraStopped:
            pass

        #self.camera.resolution = self.resolution
        self.captureConfig = self.camera.create_still_configuration({"size": self.resolution})               # Compatible Picamera2 command
        print ('camera framesize at init', self.resolution, flush=True)
        #self.camera.iso = self.ISO                                                                          # Original PiCamera command
        self.camera.set_controls({"AeEnable": True})                                                         # Compatible Picamera2 command
        self.camera.set_controls({"AnalogueGain": self.ISO/100})                                             # Compatible Picamera2 command
        #self.camera.exposure_mode = 'auto'                                                                  # Original PiCamera command
        #self.camera.framerate = Fraction(1,6)                                                               # Original PiCamera command

        #self.camera.shutter_speed = self.shutter                                                            # Original PiCamera command
        self.camera.set_controls({"ExposureTime": 1000000})                                                  # Compatible Picamera2 command
        time.sleep(10)

        #self.camera.exposure_mode = 'off'                                                                   # Original PiCamera command
        self.camera.set_controls({"AeEnable": False})                                                        # Compatible Picamera2 command
        self.runMode = True
        self.abortMOde = False

    def get_frame(self):
        """Return the current camera frame."""
        # wait for a signal from the camera thread
        if not self.event.wait(tt=40.):
            print("camera image event wait timed out", flush=True)
            return None
        self.event.clear()
        return self.frame

    # the thread that gets images
    def _thread(self):
        """Camera background thread."""
        while not self.runMode:
            time.sleep(.5)
        while True:
            try:
                self.count = 0
                print('camera thread. LOOP started', flush = True)
                frames_iterator = self.getImage()
                for frame in frames_iterator:
                    self.frame = frame
                    self.event.set()  # send signal to clients
                time.sleep(0)
            except: # picamera.PiCameraError as e:                                                           # Original PiCamera command
                print("camera thread caught exception", flush=True)
 
        self.thread = None
    # import picamera.array

    #         with picamera.PiCamera() as camera:
    #             with picamera.array.PiBayerArray(camera) as output:
    #                 camera.capture(output, 'jpeg', bayer=True)
    def getImage(self):
  
        stream = io.BytesIO()
        print ("abortMOde", self.abortMode)
        while not self.abortMode:
            while not self.runMode:
                if self.abortMode:
                    break
                pass
            if self.abortMode:
                break
            print ("picamera started", flush=True)
            self.skyStatus(0," camera started")
            try:
                #for _ in self.camera.capture_continuous(stream, self.format,                                # Original PiCamera command
                #                                        use_video_port=False):                              # Original PiCamera command

                    # return current frame
                    self.camera.switch_mode_and_capture_file(self.captureConfig, stream, format=self.format) # Compatible Picamera2 command
                    stream.seek(0)
                    yield stream.read()
                    if not self.runMode:
                        self.cameraStopped = True
                        print ("camera stopped",flush=True)
                        break
                    self.cameraStopped = False

                    # reset stream for next frame
                    stream.seek(0)
                    stream.truncate()
                    sleep(.5)
            except: # picamera.PiCameraRuntimeError as e:                                                    # Original PiCamera command
                print("Getimage caught exception", flush=True)
                #raise e
