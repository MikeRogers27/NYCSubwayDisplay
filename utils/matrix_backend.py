"""Select the emulator for development and the native driver for deployment."""

import importlib
import importlib.util
import os
from collections.abc import Callable
from types import ModuleType
from typing import Final, Literal, Protocol, cast

from PIL import Image


class MatrixColor(Protocol):
    """RGB channels exposed by either driver's color objects."""

    red: int
    green: int
    blue: int


class MatrixFont(Protocol):
    """Font operations used by the display."""

    def LoadFont(self, path: str, /) -> None: ...

    def CharacterWidth(self, char: int, /) -> int: ...


class FrameCanvas(Protocol):
    """Off-screen drawing surface supported by both matrix backends."""

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...

    def Clear(self) -> None: ...

    def Fill(self, red: int, green: int, blue: int, /) -> None: ...

    def SetPixel(self, x: int, y: int, red: int, green: int, blue: int, /) -> None: ...

    def SetImage(self, image: Image.Image, offset_x: int = 0, offset_y: int = 0) -> None: ...


class MatrixOptions(Protocol):
    """Driver settings configured by SampleBase before matrix construction."""

    hardware_mapping: str
    rows: int
    cols: int
    chain_length: int
    parallel: int
    row_address_type: int
    multiplexing: int
    pwm_bits: int
    brightness: int
    pwm_lsb_nanoseconds: int
    led_rgb_sequence: str
    pixel_mapper_config: str
    panel_type: str
    show_refresh_rate: int
    gpio_slowdown: int | None
    disable_hardware_pulsing: bool
    drop_privileges: bool
    # Only configured when using the native driver.
    limit_refresh_rate_hz: int


class Matrix(Protocol):
    """Matrix operations used to create and present display frames."""

    def CreateFrameCanvas(self) -> FrameCanvas: ...

    def SwapOnVSync(self, canvas: FrameCanvas, /) -> FrameCanvas: ...


class MatrixFactory(Protocol):
    """Shared constructor call supported by both driver classes."""

    def __call__(self, *, options: MatrixOptions) -> Matrix: ...


class ColorFactory(Protocol):
    """Construct a color using the drivers' shared positional arguments."""

    def __call__(self, red: int = 0, green: int = 0, blue: int = 0, /) -> MatrixColor: ...


class Graphics(Protocol):
    """Graphics constructors and drawing functions used by the application."""

    Color: ColorFactory
    Font: Callable[[], MatrixFont]

    # The emulator returns None for empty text; the native driver returns a width.
    def DrawText(
        self, canvas: FrameCanvas, font: MatrixFont, x: int, y: int, color: MatrixColor, text: str, /
    ) -> int | None: ...

    def DrawLine(self, canvas: FrameCanvas, x1: int, y1: int, x2: int, y2: int, color: MatrixColor, /) -> None: ...


USE_EMULATOR: Final[bool] = os.name == "nt" or importlib.util.find_spec("RGBMatrixEmulator") is not None
BACKEND: Final[Literal["RGBMatrixEmulator", "rgbmatrix"]] = "RGBMatrixEmulator" if USE_EMULATOR else "rgbmatrix"

# The drivers are dynamically loaded and do not provide checked shared types.
# Keep that boundary here; callers receive the application-facing interfaces.
matrix_module: ModuleType = importlib.import_module(BACKEND)
RGBMatrix: MatrixFactory = cast("MatrixFactory", matrix_module.RGBMatrix)
RGBMatrixOptions: Callable[[], MatrixOptions] = cast("Callable[[], MatrixOptions]", matrix_module.RGBMatrixOptions)
graphics: Graphics = cast("Graphics", importlib.import_module(f"{BACKEND}.graphics"))
