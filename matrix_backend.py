"""Select the emulator for development and the native driver for deployment."""

import importlib
import importlib.util
import os

USE_EMULATOR = os.name == "nt" or importlib.util.find_spec("RGBMatrixEmulator") is not None
BACKEND = "RGBMatrixEmulator" if USE_EMULATOR else "rgbmatrix"

matrix_module = importlib.import_module(BACKEND)
RGBMatrix = matrix_module.RGBMatrix
RGBMatrixOptions = matrix_module.RGBMatrixOptions
graphics = importlib.import_module(f"{BACKEND}.graphics")
