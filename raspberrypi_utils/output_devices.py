from abc import ABCMeta, abstractmethod
from threading import Thread, Event

from arrow import now
import RPi.GPIO as GPIO


class DigitalOutputDevice(object):
    __metaclass__ = ABCMeta

    def __init__(self, pin, initial_on=False, on_high_logic=True):
        self.pin = pin
        self.on_high_logic = on_high_logic
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH if initial_on and on_high_logic else GPIO.LOW)

    def on(self):
        GPIO.output(self.pin, GPIO.HIGH if self.on_high_logic else GPIO.LOW)

    def off(self):
        GPIO.output(self.pin, GPIO.LOW if self.on_high_logic else GPIO.HIGH)


class ThreadedDigitalOutputDevice(DigitalOutputDevice):
    __metaclass__ = ABCMeta

    def __init__(self, pin, initial_on=False, on_high_logic=True):
        super(ThreadedDigitalOutputDevice, self).__init__(pin, initial_on=initial_on, on_high_logic=on_high_logic)
        self.stop_event = Event()
        self.on_after_stop = False
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive:
            return
        if self.stop_event.isSet():
            self.stop_event.clear()
        self.thread = Thread(target=self._run)
        self.thread.start()

    def stop(self, on_after_stop=False):
        if self.is_running() and not self.stop_event.isSet():
            self.on_after_stop = on_after_stop
            self.stop_event.set()
            self.thread = None

    def is_running(self):
        return self.thread and self.thread.is_alive

    @abstractmethod
    def _run(self):
        pass


class LED(ThreadedDigitalOutputDevice):
    def __init__(self, pin, initial_on=False, on_high_logic=True):
        self.on_seconds = None
        self.off_seconds = None
        super(LED, self).__init__(pin, initial_on=initial_on, on_high_logic=on_high_logic)

    def is_flashing(self):
        self.is_running()

    def flash(self, on_seconds=0.25, off_seconds=0.25):
        self.on_seconds = on_seconds
        self.off_seconds = off_seconds
        self.start()

    def stop_flash(self, on_after_stop=False):
        self.stop(on_after_stop=on_after_stop)

    def on(self):
        self.stop_flash(on_after_stop=True)
        super(LED, self).on()

    def off(self):
        self.stop_flash(on_after_stop=False)
        super(LED, self).off()

    def _run(self):
        GPIO.setmode(GPIO.BCM)
        while not self.stop_event.is_set():
            super(LED, self).on()
            self.stop_event.wait(self.on_seconds)
            super(LED, self).off()
            self.stop_event.wait(self.off_seconds)
        self.stop_event.clear()
        if self.on_after_stop:
            super(LED, self).on()
        else:
            super(LED, self).off()


class Buzzer(ThreadedDigitalOutputDevice):
    def __init__(self, pin, freq, quiet_hours, initial_on=False, on_high_logic=True):
        super(Buzzer, self).__init__(pin, initial_on=initial_on, on_high_logic=on_high_logic)
        self.freq = freq
        self.quiet_hours = quiet_hours
        self.buzzer = None

    def is_quiet_hours(self):
        if self.quiet_hours is None:
            return False
        hour = now('US/Eastern').hour
        if self.quiet_hours[1] > self.quiet_hours[0]:
            return self.quiet_hours[0] < hour < self.quiet_hours[1]
        else:
            return hour > self.quiet_hours[0] or hour < self.quiet_hours[1]

    def start(self):
        if self.is_quiet_hours():
            return
        super(Buzzer, self).start()

    def _run(self):
        self.buzzer = GPIO.PWM(self.pin, self.freq)
        self.buzzer.start(50)
        while not self.stop_event.is_set():
            self.buzzer.ChangeFrequency(self.freq)
            self.stop_event.wait(1)
            self.buzzer.ChangeFrequency(1)
            self.stop_event.wait(0.2)
        self.stop_event.clear()
        self.buzzer.stop()
        self.buzzer = None
