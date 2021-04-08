from nmigen import *
from nmigen.build import *
from nmigen.build.res import *
from nmigen.lib.io import Pin
from nmigen_boards.ml505 import ML505Platform

class USBSerialLoopback(Elaboratable):
    def __init__(self):
        pass

    def elaborate(self, platform):
        m = Module()

        platform.add_resources([
            Resource("usb", 0,
                Subsignal("d_p",    Pins("12", conn=("gpio", 0) )),
                Subsignal("d_n",    Pins("14", conn=("gpio", 0) )),
                Subsignal("pullup", Pins("16", conn=("gpio", 0), dir="o")),
                Attrs(IOSTANDARD="LVCMOS33"),
            ),
        ])

        return m