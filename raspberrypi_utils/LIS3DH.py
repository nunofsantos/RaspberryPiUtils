##!/usr/bin/python

# LIS3DH Python Library for Raspberry Pi
# Created by Matt Dyson (mattdyson.org)
# Version 1.0 - 10/01/16
# Version 1.1 - 19/03/16 (Mal Smalley) Adding click detection

# Requires the Adafruit GPIO Python library, Adafruit_GPIO
# https://github.com/adafruit/Adafruit_Python_GPIO

# Inspiration and assistance from:
#  - https://github.com/adafruit/Adafruit_LIS3DH
#  - https://www.adafruit.com/datasheets/LIS3DH.pdf

import logging

import Adafruit_GPIO.I2C as I2C
import RPi.GPIO as GPIO  # needed for Hardware interrupt


log = logging.getLogger(__name__)


class LIS3DH(object):
    # Ranges
    RANGE_2G = 0b00
    RANGE_4G = 0b01
    RANGE_8G = 0b10
    RANGE_16G = 0b11

    # Refresh rates
    DATARATE_400HZ = 0b0111  # 400Hz
    DATARATE_200HZ = 0b0110  # 200Hz
    DATARATE_100HZ = 0b0101  # 100Hz
    DATARATE_50HZ = 0b0100  # 50Hz
    DATARATE_25HZ = 0b0011  # 25Hz
    DATARATE_10HZ = 0b0010  # 10Hz
    DATARATE_1HZ = 0b0001  # 1Hz
    DATARATE_POWERDOWN = 0  # Power down
    DATARATE_LOWPOWER_1K6HZ = 0b1000  # Low power mode (1.6KHz)
    DATARATE_LOWPOWER_5KHZ = 0b1001  # Low power mode (5KHz) / Normal power mode (1.25KHz)

    # Registers
    REG_STATUS1 = 0x07
    REG_OUTADC1_L = 0x08
    REG_OUTADC1_H = 0x09
    REG_OUTADC2_L = 0x0A
    REG_OUTADC2_H = 0x0B
    REG_OUTADC3_L = 0x0C
    REG_OUTADC3_H = 0x0D
    REG_INTCOUNT = 0x0E
    REG_WHOAMI = 0x0F  # Device identification register
    REG_TEMPCFG = 0x1F
    REG_CTRL1 = 0x20  # Used for data rate selection, and enabling/disabling individual axis
    REG_CTRL2 = 0x21
    REG_CTRL3 = 0x22
    REG_CTRL4 = 0x23  # Used for BDU, scale selection, resolution selection and self-testing
    REG_CTRL5 = 0x24
    REG_CTRL6 = 0x25
    REG_REFERENCE = 0x26
    REG_STATUS2 = 0x27
    REG_OUT_X_L = 0x28
    REG_OUT_X_H = 0x29
    REG_OUT_Y_L = 0x2A
    REG_OUT_Y_H = 0x2B
    REG_OUT_Z_L = 0x2C
    REG_OUT_Z_H = 0x2D
    REG_FIFOCTRL = 0x2E
    REG_FIFOSRC = 0x2F
    REG_INT1CFG = 0x30
    REG_INT1SRC = 0x31
    REG_INT1THS = 0x32
    REG_INT1DUR = 0x33
    REG_CLICKCFG = 0x38
    REG_CLICKSRC = 0x39
    REG_CLICKTHS = 0x3A
    REG_TIMELIMIT = 0x3B
    REG_TIMELATENCY = 0x3C
    REG_TIMEWINDOW = 0x3D

    # Values
    DEVICE_ID = 0x33
    INT_IO = 0x04  # GPIO pin for interrupt
    CLK_NONE = 0x00
    CLK_SINGLE = 0x01
    CLK_DOUBLE = 0x02

    AXIS_X = 0x00
    AXIS_Y = 0x01
    AXIS_Z = 0x02

    def __init__(self, address=0x18, bus=-1):
        log.debug("Initialising LIS3DH")

        self.i2c = I2C.Device(address, busnum=bus)
        self.address = address

        try:
            val = self.i2c.readU8(self.REG_WHOAMI)
            if val != self.DEVICE_ID:
                raise Exception("Device ID incorrect - expected 0x%X, got 0x%X at address 0x%X" % (
                    self.DEVICE_ID, val, self.address))
            log.debug("Successfully connected to LIS3DH at address 0x%X" % self.address)
        except Exception:
            raise Exception("Error establishing connection with LIS3DH")

        # Enable all axis
        self.set_axis_status(self.AXIS_X, True)
        self.set_axis_status(self.AXIS_Y, True)
        self.set_axis_status(self.AXIS_Z, True)

        # Set 400Hz refresh rate
        self.set_data_rate(self.DATARATE_400HZ)
        self.set_high_resolution()
        self.set_bdu()
        self.set_range(self.RANGE_2G)

    # Get reading from X axis
    def get_x(self):
        return self.get_axis(self.AXIS_X)

    # Get reading from Y axis
    def get_y(self):
        return self.get_axis(self.AXIS_Y)

    # Get reading from Z axis
    def get_z(self):
        return self.get_axis(self.AXIS_Z)

    # Get a reading from the desired axis
    def get_axis(self, axis):
        base = self.REG_OUT_X_L + (2 * axis)  # Determine which register we need to read from (2 per axis)

        low = self.i2c.readU8(base)  # Read the first register (lower bits)
        high = self.i2c.readU8(base + 1)  # Read the next register (higher bits)
        res = low | (high << 8)  # Combine the two components
        res = self.twos_comp(res)  # Calculate the twos compliment of the result

        # Fetch the range we're set to, so we can accurately calculate the result
        current_range = self.get_range()
        divisor = 1
        if current_range == self.RANGE_2G:
            divisor = 16380
        elif current_range == self.RANGE_4G:
            divisor = 8190
        elif current_range == self.RANGE_8G:
            divisor = 4096
        elif current_range == self.RANGE_16G:
            divisor = 1365.33

        return float(res) / divisor

    # Get the range that the sensor is currently set to
    def get_range(self):
        val = self.i2c.readU8(self.REG_CTRL4)  # Get value from register
        val = (val >> 4)  # Remove lowest 4 bits
        val &= 0b0011  # Mask off two highest bits

        if val == self.RANGE_2G:
            return self.RANGE_2G
        elif val == self.RANGE_4G:
            return self.RANGE_4G
        elif val == self.RANGE_8G:
            return self.RANGE_8G
        else:
            return self.RANGE_16G

    # Set the range of the sensor (2G, 4G, 8G, 16G)
    def set_range(self, new_range):
        if new_range < 0 or new_range > 3:
            raise Exception("Tried to set invalid range")

        val = self.i2c.readU8(self.REG_CTRL4)  # Get value from register
        val &= ~0b110000  # Mask off lowest 4 bits
        val |= (new_range << 4)  # Write in our new range
        self.write_register(self.REG_CTRL4, val)  # Write back to register

    # Enable or disable an individual axis
    # Read status from CTRL_REG1, then write back with appropriate status bit changed
    def set_axis_status(self, axis, enable):
        if axis < 0 or axis > 2:
            raise Exception("Tried to modify invalid axis")

        current = self.i2c.readU8(self.REG_CTRL1)
        final = self.set_bit(current, axis, int(enable))
        self.write_register(self.REG_CTRL1, final)

    def set_interrupt(self, mycallback):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.INT_IO, GPIO.IN)
        GPIO.add_event_detect(self.INT_IO, GPIO.RISING, callback=mycallback)

    def set_click(self, clickmode, clickthresh=80, timelimit=10, timelatency=20, timewindow=100, mycallback=None):
        if clickmode == self.CLK_NONE:
            val = self.i2c.readU8(self.REG_CTRL3)  # Get value from register
            val &= ~0x80  # unset bit 8 to disable interrupt
            self.write_register(self.REG_CTRL3, val)  # Write back to register
            self.write_register(self.REG_CLICKCFG, 0)  # disable all interrupts
            return

        self.write_register(self.REG_CTRL3, 0x80)  # turn on int1 click
        self.write_register(self.REG_CTRL5, 0x08)  # latch interrupt on int1

        if clickmode == self.CLK_SINGLE:
            self.write_register(self.REG_CLICKCFG, 0x15)  # turn on all axes & singletap
        elif clickmode == self.CLK_DOUBLE:
            self.write_register(self.REG_CLICKCFG, 0x2A)  # turn on all axes & doubletap

        # set timing parameters
        self.write_register(self.REG_CLICKTHS, clickthresh)
        self.write_register(self.REG_TIMELIMIT, timelimit)
        self.write_register(self.REG_TIMELATENCY, timelatency)
        self.write_register(self.REG_TIMEWINDOW, timewindow)

        if mycallback is not None:
            self.set_interrupt(mycallback)

    def get_click(self):
        reg = self.i2c.readU8(self.REG_CLICKSRC)  # read click register
        self.i2c.readU8(self.REG_INT1SRC)  # reset interrupt flag
        return reg

    # Set the rate (cycles per second) at which data is gathered
    def set_data_rate(self, data_rate):
        val = self.i2c.readU8(self.REG_CTRL1)  # Get current value
        val &= 0b1111  # Mask off lowest 4 bits
        val |= (data_rate << 4)  # Write in our new data rate to highest 4 bits
        self.write_register(self.REG_CTRL1, val)  # Write back to register

    # Set whether we want to use high resolution or not
    def set_high_resolution(self, high_res=True):
        val = self.i2c.readU8(self.REG_CTRL4)  # Get current value
        final = self.set_bit(val, 3, int(high_res))  # High resolution is bit 4 of REG_CTRL4
        self.write_register(self.REG_CTRL4, final)

    # Set whether we want to use block data update or not
    # False = output registers not updated until MSB and LSB reading
    def set_bdu(self, bdu=True):
        val = self.i2c.readU8(self.REG_CTRL4)  # Get current value
        final = self.set_bit(val, 7, int(bdu))  # Block data update is bit 8 of REG_CTRL4
        self.write_register(self.REG_CTRL4, final)

    # Write the given value to the given register
    def write_register(self, register, value):
        log.debug("WRT %s to register 0x%X" % (bin(value), register))
        self.i2c.write8(register, value)

    # Set the bit at index 'bit' to 'value' on 'input_val' and return
    @staticmethod
    def set_bit(input_val, bit, value):
        mask = 1 << bit
        input_val &= ~mask
        if value:
            input_val |= mask
        return input_val

    # Return a 16-bit signed number (two's compliment)
    # Thanks to http://stackoverflow.com/questions/16124059/trying-to-read-a-twos-complement-16bit-into-a-signed-decimal
    @staticmethod
    def twos_comp(x):
        if 0x8000 & x:
            x = - (0x010000 - x)
        return x

    # Print an output of all registers
    def dump_registers(self):
        for x in range(0x0, 0x3D):
            read = self.i2c.readU8(x)
            log.info("%X: %s" % (x, bin(read)))
