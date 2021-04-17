from nmigen import *
from nmigen.sim import *
from nmigen.lib.cdc import *

# A UART RX using oversampling
class UART_RX(Elaboratable):
    def __init__(self, baud_rate=9600, fclk=None):
        self.rx = Signal()
        self.tx = Signal()

        self.error  = Signal()
        self.data   = Signal(8)
        self.valid  = Signal()

        if(fclk==None):
            raise ValueError("Please specify fclk")
        else:
            self.divider = int((fclk/baud_rate)/6)
                
    def elaborate(self, platform):
        m = Module()

        rx_sync = Signal()
        m.submodules.rx_2ff = FFSynchronizer(i=self.rx, o=rx_sync, o_domain="sync")

        # Generate the sampling strobe 3 times per bit        
        baud_divide = Signal(range(self.divider))
        oversample_counter = Signal(3)
        sample_strobe = Signal()
        bit_count = Signal(4)
        m.d.sync += [
            sample_strobe.eq(0),
            baud_divide.eq(baud_divide+1),
        ]
        with m.If(baud_divide==self.divider):
            m.d.sync += [
                oversample_counter.eq(oversample_counter+1),
                baud_divide.eq(0),
            ]
            with m.If(oversample_counter==5):
                m.d.sync += oversample_counter.eq(0)
            with m.If(~oversample_counter[2] & oversample_counter[0:2].any() 
                & bit_count.any()):
                m.d.sync += sample_strobe.eq(1)
            
        # Detect start bits and changes
        rx_sync_prev = Signal()
        m.d.sync += rx_sync_prev.eq(rx_sync)
        with m.If(rx_sync_prev ^ rx_sync):
            # Detect start bits
            with m.If(~bit_count.any() & ~rx_sync):
                m.d.sync += [
                    bit_count.eq(1),
                    self.error.eq(0),
                    self.valid.eq(0),
                    baud_divide.eq(0),
                    oversample_counter.eq(0),
                ]
            # Early changes
            with m.Else():
                with m.If(oversample_counter[2]):
                    m.d.sync += [
                        baud_divide.eq(0),
                        oversample_counter.eq(0),
                    ]

        # Counting bits
        with m.If(bit_count.any() & (oversample_counter == 4) & sample_strobe):
            m.d.sync += bit_count.eq(bit_count+1)
            with m.If(bit_count==9):
                m.d.sync += bit_count.eq(0)                
        
        # Input right shift reg with vote
        voting = Signal(2)
        vote = Signal()
        with m.If(bit_count.any() & ~(bit_count==1) & sample_strobe):
            m.d.sync += voting.eq(Cat(voting[1], rx_sync))
        m.d.comb += vote.eq( voting.all() | (rx_sync & voting[0]) | (rx_sync & voting[1]))
        
        m.d.comb += self.tx.eq(rx_sync)

        return m

if __name__=="__main__":
    u = UART_RX(baud_rate=115200, fclk=50e6)   # 0.00000868055 s/bit
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
            yield Delay(interval=(random.randrange(8500, 8800)/1e9))
        yield u.rx.eq(1)    # Stop bit
        yield Delay(interval=(random.randrange(8500, 8800)/1e9))

    import random
    def tb():
        yield u.rx.eq(1)
        yield Delay(interval=(random.randrange(8000, 10000)/1e9))
        yield from tx_byte(0x56)

    sim.add_sync_process(clock)
    sim.add_process(tb)

    with sim.write_vcd("UART_waves.vcd"):
        sim.run_until(1e-3)
        