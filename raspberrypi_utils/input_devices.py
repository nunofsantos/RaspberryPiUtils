from abc import ABCMeta, abstractmethod
import logging
from operator import add, div
from threading import Thread
from time import sleep

from LIS3DH import LIS3DH
import RPi.GPIO as GPIO
from yunomi import Meter


log = logging.getLogger(__name__)


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
        super(Button, self).__init__(
            immediate_callback=pressed_callback,
            threshold_callback=held_callback,
            threshold_seconds=hold_seconds
        )

    def read(self):
        return GPIO.input(self.pin)

    def run(self):
        while True:
            GPIO.wait_for_edge(self.pin, GPIO.RISING if self.pull_up_down == GPIO.PUD_DOWN else GPIO.FALLING)
            log.debug('Button pressed')
            self.notify_immediate()
            if not GPIO.wait_for_edge(self.pin, GPIO.FALLING if self.pull_up_down == GPIO.PUD_DOWN else GPIO.RISING,
                                      timeout=self.threshold_seconds * 1000):
                log.debug('Button held')
                self.notify_threshold()
            else:
                log.debug('Button released')


class VibrationSensor(ThreadedDigitalInputDevice):
    def __init__(self, address=0x18, bus=1, frequency_seconds=1,
                 sensitivity=(0.05, 0.05, 0.05), auto_calibrate=True, auto_sensitivity=1.0,
                 threshold_per_minute=1, vibration_callback=None, steady_vibration_callback=None):
        GPIO.setmode(GPIO.BCM)
        self.meter = Meter()
        self.frequency_seconds = frequency_seconds
        self.sensitivity = sensitivity
        self.auto_calibrate = auto_calibrate
        self.auto_sensitivity = auto_sensitivity
        self.threshold_per_minute = threshold_per_minute
        self.calibration = (0.0, 0.0, 0.0)
        self.sensor = LIS3DH(address=address, bus=bus)
        if self.auto_calibrate:
            self._calibrate()
        super(VibrationSensor, self).__init__(
            vibration_callback,
            steady_vibration_callback
        )

    def _calibrate(self, iterations=50):
        # figure out which axis is measuring gravity, and calibrate accordingly to ignore its effect
        totals = [0, 0, 0]
        for i in xrange(iterations):
            readings = [abs(self.sensor.get_x()), abs(self.sensor.get_y()), abs(self.sensor.get_z())]
            totals = map(add, readings, totals)
            sleep(0.2)
        self.calibration = [round(x, 3) for x in map(div, totals, [iterations]*3)]
        log.debug('VibrationSensor: self calibration (x, y, z) = {}'.format(self.calibration))
        self.sensitivity = []
        for x in self.calibration:
            if round(x, 0) == 1:
                # gravity axis, remove gravity factor before multiplying, then add back in
                x %= 1
                x *= 1.0 + self.auto_sensitivity
                x += 1.0
            else:
                x *= 1.0 + self.auto_sensitivity
            self.sensitivity.append(round(x, 3))
        log.debug('VibrationSensor: calculated sensitivity (x, y, z) = {}'.format(self.sensitivity))

    def read(self):
        rate = self.meter.get_one_minute_rate()
        if rate > self.threshold_per_minute:
            log.debug('VibrationSensor: rate {:.2f} above threshold {:.2f}, steady callback'.format(
                rate, self.threshold_per_minute)
            )
            self.notify_threshold(rate)
        return rate

    def reset(self):
        self.meter = Meter()

    def run(self):
        while True:
            readings = [abs(round(x, 3)) for x in (self.sensor.get_x(), self.sensor.get_y(), self.sensor.get_z())]
            log.debug('VibrationSensor: readings (x, y, z) = {}'.format(readings))
            if any(True for i in xrange(3) if abs(readings[i] - self.calibration[i]) > self.sensitivity[i]):
                self.meter.mark()
                log.debug('VibrationSensor meter marked')
                self.notify_immediate(True)
            else:
                self.notify_immediate(False)
            self.read()
            sleep(self.frequency_seconds)


class LightSensor(ThreadedDigitalInputDevice):
    def __init__(self, pin, light_callback, on_threshold=500, frequency=10):
        self.pin = pin
        self.on_threshold = on_threshold
        self.frequency = frequency
        self.is_on = None
        GPIO.setup(pin, GPIO.OUT)
        super(LightSensor, self).__init__(
            immediate_callback=light_callback,
        )

    def read(self):
        # based on https://learn.adafruit.com/basic-resistor-sensor-reading-on-raspberry-pi/basic-photocell-reading
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)
        sleep(0.1)
        GPIO.setup(self.pin, GPIO.IN)

        reading = 0
        while (GPIO.input(self.pin) == GPIO.LOW):
            reading += 1
        return reading

    def run(self):
        while True:
            is_on_now = self.read() <= self.on_threshold
            if self.is_on is None or is_on_now != self.is_on:
                self.is_on = is_on_now
                log.debug('Light turned {}'.format('on' if self.is_on else 'off'))
                self.notify_immediate(self.is_on)
            sleep(self.frequency)
