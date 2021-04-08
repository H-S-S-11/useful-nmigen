from nmigen import *
from nmigen.build import *
from nmigen.build.res import *
from nmigen.lib.io import Pin
from nmigen_boards.ml505 import ML505Platform
from nmigen_boards.resources import *

from ml505_luna_clocking import *

from luna.full_devices import USBSerialDevice

class USBSerialLoopback(Elaboratable):
    def __init__(self):
        pass

    def elaborate(self, platform):
        m = Module()

        # Create clocks
        m.submodules.clocks = ML505LunaClockDomains()

        # Add USB connector
        platform.add_resources([
            Resource("usb_gpio", 0,
                Subsignal("d_p",    Pins("12", conn=("gpio", 0) )),
                Subsignal("d_n",    Pins("14", conn=("gpio", 0) )),
                Subsignal("pullup", Pins("16", conn=("gpio", 0), dir="o")),
                Attrs(IOSTANDARD="LVCMOS33"),
            ),
        ])

        # Instantiate the serial converter 
        direct_usb = platform.request("usb_gpio")
        m.submodules.usb_serial = usb_serial = \
            USBSerialDevice(bus=direct_usb, idVendor=0x16d0, idProduct=0x0f3b)

        m.d.comb += [
            # Place the streams into a loopback configuration...
            usb_serial.tx.payload  .eq(usb_serial.rx.payload),
            usb_serial.tx.valid    .eq(usb_serial.rx.valid),
            usb_serial.tx.first    .eq(usb_serial.rx.first),
            usb_serial.tx.last     .eq(usb_serial.rx.last),
            usb_serial.rx.ready    .eq(usb_serial.tx.ready),

            # ... and always connect by default.
            usb_serial.connect     .eq(1)
        ]

        return m

if __name__ == "__main__":
    ML505Platform().build(USBSerialLoopback())