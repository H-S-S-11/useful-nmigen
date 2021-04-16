from nmigen import *
from nmigen.sim import *
from nmigen.lib.cdc import *

# A UART TX and RX using 5x oversampling
class UART(Elaboratable):
    def __init__(self, baud_rate=9600, fclk=None):
        self.rx = Signal()
        self.tx = Signal()

        if(fclk==None):
            raise ValueError("Please specify fclk")
        else:
            self.divider = int((fclk/baud_rate)/5)
                
    def elaborate(self, platform):
        m = Module()

        rx_sync = Signal()
        m.submodules.rx_2ff = FFSynchronizer(i=self.rx, o=rx_sync, o_domain="sync")

        # Generate the sampling strobe 5 times per bit        
        baud_divide = Signal(range(self.divider))
        oversample_counter = Signal(range(4))
        sample_strobe = Signal()
        m.d.sync += [
            sample_strobe.eq(0),
            baud_divide.eq(baud_divide+1),
        ]
        with m.If(baud_divide==self.divider):
            m.d.sync += [
                sample_strobe.eq(1),
                oversample_counter.eq(oversample_counter+1),
                baud_divide.eq(0),
            ]
        
        m.d.comb += self.tx.eq(rx_sync)

        return m

if __name__=="__main__":
    u = UART(baud_rate=115200, fclk=50e6)   # 0.00000868055 s/bit
    sim = Simulator(u)
    sim.add_clock(20e-9)

    def clock():
        while True:
            yield

    def tx_byte(byte):
        bits = bin(byte)[2:]
        while len(bits) < 8:
            bits = "0" + bits
        for n in range(0, 8):
            yield u.rx.eq(int(bits[n]))
            yield Delay(interval=8.68e-6)
        yield u.rx.eq(1)    # Stop bit
        yield Delay(interval=8.68e-6)

    import random
    def tb():
        yield u.rx.eq(1)
        yield Delay(interval=(random.randrange(8000, 10000)/1e9))
        yield from tx_byte(0x56)

    sim.add_sync_process(clock)
    sim.add_process(tb)

    with sim.write_vcd("UART_waves.vcd"):
        sim.run_until(1e-3)
        