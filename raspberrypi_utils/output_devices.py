from threading import Thread, Event

from arrow import now
import RPi.GPIO as GPIO


class DigitalOutputDevice(object):
    def __init__(self, pin, initial=GPIO.LOW):
        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT, initial=initial)

    def on(self):
        GPIO.output(self.pin, GPIO.HIGH)

    def off(self):
        GPIO.output(self.pin, GPIO.LOW)


class ThreadedDigitalOutputDevice(DigitalOutputDevice):
    def __init__(self, pin, initial=GPIO.LOW):
        super(ThreadedDigitalOutputDevice, self).__init__(pin, initial=initial)
        self.stop_event = Event()
        self.thread = None

    def start(self):
        self.thread = Thread(target=self._run)
        if self.stop_event.isSet():
            self.stop_event.clear()
        self.thread.start()

    def stop(self):
        if not self.stop_event.isSet():
            self.stop_event.set()
        self.thread = None

    def _run(self):
        pass


class LED(ThreadedDigitalOutputDevice):
    def __init__(self, pin, initial=GPIO.LOW):
        self.on_seconds = None
        self.off_seconds = None
        super(LED, self).__init__(pin, initial=initial)

    def flash(self, on_seconds=0.25, off_seconds=0.25):
        self.on_seconds = on_seconds
        self.off_seconds = off_seconds
        self.start()

    def stop_flash(self):
        self.stop()

    def off(self, stop_flashing=True):
        if stop_flashing:
            self.stop_flash()
        super(LED, self).off()

    def _run(self):
        GPIO.setmode(GPIO.BCM)
        while not self.stop_event.is_set():
            self.on()
            self.stop_event.wait(self.on_seconds)
            self.off(stop_flashing=False)
            self.stop_event.wait(self.off_seconds)


class Buzzer(ThreadedDigitalOutputDevice):
    def __init__(self, pin, freq, quiet_hours):
        super(Buzzer, self).__init__(pin, initial=GPIO.LOW)
        self.freq = freq
        self.quiet_hours = quiet_hours
        GPIO.output(self.pin, GPIO.LOW)
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
        self.buzzer.stop()
        self.buzzer = None
