from threading import Thread

import RPi.GPIO as GPIO


class Button(object):
    def __init__(self, pin, pressed_callback, hold_seconds=0, held_callback=None, pull_up_down=GPIO.PUD_DOWN):
        self.pin = pin
        self.hold_seconds = hold_seconds
        self.pressed_callback = pressed_callback
        self.held_callback = held_callback
        self.pull_up_down = pull_up_down
        GPIO.setup(pin, GPIO.IN, pull_up_down=pull_up_down)
        self.thread = Thread(target=self.detect_button).start()

    def detect_button(self):
        while True:
            GPIO.wait_for_edge(self.pin, GPIO.RISING if self.pull_up_down == GPIO.PUD_DOWN else GPIO.FALLING)
            self.pressed_callback()
            if not GPIO.wait_for_edge(self.pin, GPIO.FALLING if self.pull_up_down == GPIO.PUD_DOWN else GPIO.RISING,
                                      timeout=self.hold_seconds * 1000):
                self.held_callback()
