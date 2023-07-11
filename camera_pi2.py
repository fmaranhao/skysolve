#pi camera to be used with web based GUI plate solver
import io
import time
from tkinter import EXCEPTION
import picamera2
from libcamera import controls
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
    previewConfig = None
    #captureConfig = None
    cameraControls = None
    frameRate = 1/6
    event = imageEvent()
    thread = None  # background thread that reads frames from camera
    gainThread = None
    frame = None  # current frame is stored here by background thread
    resolution= (2000,1500)
    runMode = True
    cameraStopped = True
    format = 'jpeg'
    def __init__(self, skystatus, shutter=1000000, ISO=800, resolution=(2000,1500), format = 'jpeg'):
        print("skystatus", skystatus)
        self.skyStatus = skystatus
        self.camera = picamera2.Picamera2()
        self.cameraControls = picamera2.Controls(self.camera)
        self.cameraControls.AeEnable = 0
        self.cameraControls.FrameDurationLimits = (shutter,shutter)
        self.cameraControls.ExposureTime = shutter
        self.cameraControls.AnalogueGain = ISO/100
        self.resolution=resolution
        self.format = format
        if type(resolution) is str: resolution = tuple(map(int, resolution.split('x')))
        self.previewConfig = self.camera.create_preview_configuration(main={"size": resolution})
        self.camera.start_preview(picamera2.Preview.NULL)
        self.camera.configure(self.previewConfig)
        self.camera.set_controls(self.cameraControls)
        self.camera.start()
        time.sleep(2)
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
        self.cameraControls.AnalogueGain = iso/100
        self.camera.set_controls(self.cameraControls)
        print ("setting ISO", iso, flush=True)

    def status(self):
        return [self.cameraControls.AnalogueGain*100, self.cameraControls.ExposureTime, self.resolution]

    def setResolution(self,  resolution):
        resolution = tuple(map(int, resolution.split('x')))
        self.resolution = resolution
        print ("setting resolution", resolution, flush=True)
        self.previewConfig = self.camera.create_preview_configuration(main={"size": resolution})
        self.runMode = False
        while not self.cameraStopped:
            time.sleep(.2)
        self.camera.stop()
        self.camera.configure(self.previewConfig)
        self.camera.set_controls(self.cameraControls)
        self.camera.start()
        time.sleep(2)
        self.runMode = True

    def setFormat(self,type):
        self.format = type

    def setShutter(self, value):
        self.cameraControls.FrameDurationLimits = (value,value)
        self.cameraControls.ExposureTime = value
        self.camera.set_controls(self.cameraControls)
        print ("new shutter speed", value, flush=True)

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
        while True:
            while not self.runMode:
                time.sleep(.5)
            try:
                self.count = 0
                print('camera thread. LOOP started', flush = True)
                frames_iterator = self.getImage()
                for frame in frames_iterator:
                    self.frame = frame
                    self.event.set()  # send signal to clients
                time.sleep(0)
            except Exception as e:
                print("camera thread caught exception", e, flush=True)
                raise e
 
        self.thread = None

    def getImage(self):
        stream = io.BytesIO()
        while True:
            try:
                # return current frame
                #self.camera.switch_mode_and_capture_file(self.captureConfig, stream, format=self.format)
                self.camera.capture_file(stream, format=self.format)
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
                time.sleep(self.cameraControls.ExposureTime/1000000)
            except Exception as e:
                print("Getimage caught exception", e, flush=True)
                raise e
