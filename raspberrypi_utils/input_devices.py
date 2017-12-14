from abc import ABCMeta, abstractmethod
from threading import Thread
from time import sleep

from LIS3DH import LIS3DH
import RPi.GPIO as GPIO
from yunomi import Meter


class ThreadedDigitalInputDevice(object):
    __metaclass__ = ABCMeta

    def __init__(self, immediate_callback=None, threshold_callback=None, threshold_seconds=0):
        self.immediate_callback = immediate_callback
        self.threshold_callback = threshold_callback
        self.threshold_seconds = threshold_seconds
        self.thread = Thread(target=self.run).start()

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def read(self):
        pass

    def notify_immediate(self, *args):
        if self.immediate_callback:
            self.immediate_callback(*args)

    def notify_threshold(self, *args):
        if self.threshold_callback:
            self.threshold_callback(*args)


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
            self.notify_immediate()
            if not GPIO.wait_for_edge(self.pin, GPIO.FALLING if self.pull_up_down == GPIO.PUD_DOWN else GPIO.RISING,
                                      timeout=self.threshold_seconds * 1000):
                self.notify_threshold()


class VibrationSensor(ThreadedDigitalInputDevice):
    def __init__(self, address=0x18, bus=1, frequency_seconds=1,
                 sensitivity=(1, 0.1, 0.1), threshold_per_minute=1,
                 vibration_callback=None, steady_vibration_callback=None):
        GPIO.setmode(GPIO.BCM)
        self.meter = Meter()
        self.frequency_seconds = frequency_seconds
        self.sensitivity = sensitivity
        self.threshold_per_minute = threshold_per_minute
        self.sensor = LIS3DH(address=address, bus=bus)
        super(VibrationSensor, self).__init__(
            vibration_callback,
            steady_vibration_callback
        )

    def read(self):
        rate = self.meter.get_one_minute_rate()
        if rate > self.threshold_per_minute:
            self.notify_threshold(rate)
        return rate

    def reset(self):
        self.meter = Meter()

    def run(self):
        while True:
            readings = (self.sensor.get_x(), self.sensor.get_y(), self.sensor.get_z())
            if any(True for i in xrange(3) if abs(readings[i]) > self.sensitivity[i]):
                self.meter.mark()
                self.notify_immediate(True)
            else:
                self.notify_immediate(False)
            self.read()
            sleep(self.frequency_seconds)
