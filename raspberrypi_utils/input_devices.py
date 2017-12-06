from threading import Thread

from arrow import now
from LIS3DH import LIS3DH
import RPi.GPIO as GPIO


class ThreadedDigitalInputDevice(object):
    def __init__(self, immediate_callback, threshold_callback=None, threshold_seconds=0):
        self.immediate_callback = immediate_callback
        self.threshold_callback = threshold_callback
        self.threshold_seconds = threshold_seconds
        self.thread = Thread(target=self.run).start()

    def run(self):
        pass

    def read(self):
        pass


class Button(ThreadedDigitalInputDevice):
    def __init__(self, pin, pressed_callback, hold_seconds=0, held_callback=None, pull_up_down=GPIO.PUD_DOWN):
        self.pin = pin
        self.pull_up_down = pull_up_down
        GPIO.setup(pin, GPIO.IN, pull_up_down=pull_up_down)
        super(Button, self).__init__(pressed_callback, held_callback, hold_seconds)

    def read(self):
        return GPIO.input(self.pin)

    def run(self):
        while True:
            GPIO.wait_for_edge(self.pin, GPIO.RISING if self.pull_up_down == GPIO.PUD_DOWN else GPIO.FALLING)
            self.immediate_callback()
            if not GPIO.wait_for_edge(self.pin, GPIO.FALLING if self.pull_up_down == GPIO.PUD_DOWN else GPIO.RISING,
                                      timeout=self.threshold_seconds * 1000):
                self.threshold_callback()


class VibrationSensor(ThreadedDigitalInputDevice):
    def __init__(self, change_callback, address=0x18, bus=1, sensitivity=1, threshold_seconds=5*60,
                 steady_callback=None):
        GPIO.setmode(GPIO.BCM)
        self.sensitivity = sensitivity
        self.vibrating = False
        self.last_change_timestamp = None
        self.steady_notification_sent = False
        self.sensor = LIS3DH(address=address, bus=bus)
        super(VibrationSensor, self).__init__(
            change_callback,
            steady_callback,
            threshold_seconds
        )

    def read(self):
        return any(True for val in [self.sensor.get_x(), self.sensor.get_y(), self.sensor.get_z()]
                   if val > self.sensitivity or val < -self.sensitivity)

    def run(self):
        while True:
            reading = self.read()
            if reading != self.vibrating:
                self.vibrating = reading
                self.last_change_timestamp = now()
                self.steady_notification_sent = False
                self.immediate_callback(reading)
            elif (not self.steady_notification_sent
                  and now() > self.last_change_timestamp.shift(seconds=self.threshold_seconds)):
                self.threshold_callback(reading)
                self.steady_notification_sent = True
