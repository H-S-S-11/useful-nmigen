from nmigen import *
from nmigen.build import *
from nmigen.build.res import *
from nmigen.sim import *
from nmigen.lib.io import Pin
from nmigen_boards.ml505 import ML505Platform
from nmigen_boards.resources import *

from ml505_luna_clocking import *

from luna.full_devices import USBSerialDevice
from luna.gateware.debug.ila import *

import sys

class USBSerialLoopback(Elaboratable):
    def __init__(self):
        pass

    def elaborate(self, platform):
        m = Module()

        if (platform != None):
            # Create clocks
            m.submodules.clocks = ML505LunaClockDomains()

        # Sync counter to test ILA
        counter = Signal(29)
        count_low = Signal(8)
        m.d.comb += count_low.eq(Cat(counter[0:8]))
        trigger = Signal()
        m.d.sync += [
            counter.eq(counter+1),
            trigger.eq(0),
        ]
        with m.If(counter==0):
            m.d.sync += [
                trigger.eq(~trigger),
            ]     

        # Instantiate ILA
        uart_divisor = 10000
        m.submodules.serial_ila = self.serial_ila = serial_ila = AsyncSerialILA(
            signals=[count_low], sample_depth=100, divisor=uart_divisor, domain="sync", samples_pretrigger=50)
        m.d.comb += serial_ila.trigger.eq(trigger)
        
        if (platform != None):
            platform.add_resources([
                    Resource("uart_tx", 0,
                        Pins("4", conn=("gpio", 0), dir ="o" ), 
                        Attrs(IOSTANDARD="LVCMOS33")
                        ),
            ])
            tx = platform.request("uart_tx")
            trigger_led = platform.request("led", 1)
            serial = platform.request("led", 2)
            m.d.comb += [
                trigger_led.o.eq(counter[27]),
                tx.o.eq(serial_ila.tx),
                serial.o.eq(serial_ila.tx)
            ]
        
        return m

if __name__ == "__main__":
    usb = USBSerialLoopback()
    if sys.argv[1] == "build":
        ML505Platform().build(usb)
        #ila_frontend = AsyncSerialILAFrontend(port="COM8", ila=usb.serial_ila)
        #while True:
        #    ila_frontend.print_samples()

    if sys.argv[1] == "sim":
        sim = Simulator(usb)
        sim.add_clock(10e-9)

        def clock():
            while True:
                yield

        sim.add_sync_process(clock)

        with sim.write_vcd("ila_waves.vcd"):
            sim.run_until(3e-2)