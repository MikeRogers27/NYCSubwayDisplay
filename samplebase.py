import argparse
import importlib
import os
import time
import sys

if os.name == 'nt':
    RGBMatrix = getattr(importlib.import_module('RGBMatrixEmulator'), 'RGBMatrix')
    RGBMatrixOptions = getattr(importlib.import_module('RGBMatrixEmulator'), 'RGBMatrixOptions')
else:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions


class SampleBase(object):
    def __init__(self, args):
        self.args = args

    def usleep(self, value):
        time.sleep(value / 1000000.0)

    def run(self):
        print("Running")

    def process(self):
        options = RGBMatrixOptions()

        if self.args.led_gpio_mapping != None:
            options.hardware_mapping = self.args.led_gpio_mapping
        options.rows = self.args.led_rows
        options.cols = self.args.led_cols
        options.chain_length = self.args.led_chain
        options.parallel = self.args.led_parallel
        options.row_address_type = self.args.led_row_addr_type
        options.multiplexing = self.args.led_multiplexing
        options.pwm_bits = self.args.led_pwm_bits
        options.brightness = self.args.led_brightness
        options.pwm_lsb_nanoseconds = self.args.led_pwm_lsb_nanoseconds
        options.led_rgb_sequence = self.args.led_rgb_sequence
        options.pixel_mapper_config = self.args.led_pixel_mapper
        options.panel_type = self.args.led_panel_type
        if os.name != 'nt':
            options.limit_refresh_rate_hz = self.args.led_limit_refresh

        if self.args.led_show_refresh:
            options.show_refresh_rate = 1

        if self.args.led_slowdown_gpio != None:
            options.gpio_slowdown = self.args.led_slowdown_gpio
        if self.args.led_no_hardware_pulse:
            options.disable_hardware_pulsing = True
        if not self.args.drop_privileges:
            options.drop_privileges = False

        self.matrix = RGBMatrix(options=options)

        self.run()

        # try:
        #     # Start loop
        #     print("Press CTRL-C to stop sample")
        #     self.run()
        # except KeyboardInterrupt:
        #     print("Exiting\n")
        #     sys.exit(0)

        return True
