from nmigen import *
from nmigen.sim import *
from nmigen.lib.cdc import *

# A UART RX using oversampling
class UART_RX(Elaboratable):
    def __init__(self, baud_rate=9600, fclk=None):
        self.rx = Signal()
        
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
            # changes
            with m.Else():
                with m.If(~oversample_counter[0:2].any() | 
                    (oversample_counter[0] & oversample_counter[2])):
                    m.d.sync += [
                        baud_divide.eq(0),
                        oversample_counter.eq(0),
                    ]

        # Counting bits
        with m.If(bit_count.any() & (oversample_counter == 4) & sample_strobe):
            m.d.sync += bit_count.eq(bit_count+1)
            with m.If(bit_count==10):
                m.d.sync += bit_count.eq(0)                
        
        # Input right shift reg with vote
        voting = Signal(2)
        vote = Signal()
        with m.If(bit_count.any() & ~(bit_count==1) & sample_strobe):
            m.d.sync += voting.eq(Cat(voting[1], rx_sync))
        m.d.comb += vote.eq( voting.all() | (rx_sync & voting[0]) | (rx_sync & voting[1]))
        
        # Shift into data output reg, check stop bit
        with m.If(sample_strobe & oversample_counter[2]):
            with m.If(bit_count==10):
                m.d.sync += [
                    self.valid.eq(vote),
                    self.error.eq(~vote),
                ]
            with m.Else():
                m.d.sync += self.data.eq(Cat(self.data[1:8], vote))


        return m

if __name__=="__main__":
    u = UART_RX(baud_rate=115200, fclk=50e6)   # 0.00000868055 s/bit
    sim = Simulator(u)
    sim.add_clock(20e-9)

    def clock():
        while True:
            yield

    def tx_byte(byte, jitter=400):
        bits = bin(byte)[2:]
        while len(bits) < 8:
            bits = "0" + bits
        yield u.rx.eq(0)    # Start bit
        yield Delay(interval=(random.randrange(8680-jitter, 8680+jitter)/1e9))
        for n in range(0, 8):
            yield u.rx.eq(int(bits[7-n]))
            yield Delay(interval=(random.randrange(8680-jitter, 8680+jitter)/1e9))
        yield u.rx.eq(1)    # Stop bit
        yield Delay(interval=(random.randrange(8680-jitter, 8680+jitter)/1e9))

    def noisy_byte(byte):
        bits = bin(byte)[2:]
        while len(bits) < 8:
            bits = "0" + bits
        yield u.rx.eq(0)    # Start bit
        yield Delay(interval=8.68e-6)

        yield u.rx.eq(int(bits[7]))
        yield Delay(interval=2.8e-6)
        yield u.rx.eq(~u.rx)
        yield Delay(interval=0.4e-6)
        yield u.rx.eq(~u.rx)
        yield Delay(interval=3e-6)

        yield u.rx.eq(int(bits[6]))
        yield Delay(interval=4.2e-6)
        yield u.rx.eq(~u.rx)
        yield Delay(interval=0.4e-6)
        yield u.rx.eq(~u.rx)
        yield Delay(interval=3e-6)

        yield u.rx.eq(int(bits[5]))
        yield Delay(interval=5.6e-6)
        yield u.rx.eq(~u.rx)
        yield Delay(interval=0.4e-6)
        yield u.rx.eq(~u.rx)
        yield Delay(interval=2.8e-6)

        for n in range(3, 8):
            yield u.rx.eq(int(bits[7-n]))
            yield Delay(interval=8.68e-6)
        yield u.rx.eq(1)    # Stop bit
        yield Delay(interval=8.68e-6)

    import random
    def tb():
        yield u.rx.eq(1)
        yield Delay(interval=50e-5)
        yield Delay(interval=(random.randrange(7000, 11000)/1e9))
        yield from tx_byte(0x56, jitter=1000)
        yield Delay(interval=4e-5)
        yield from noisy_byte(0xa5)
        for n in range(0, 10):
            yield Delay(interval=4e-5)
            yield from tx_byte(0x56, jitter=1000)

    def check_output():
        error = valid = 0
        while not (error or valid):
            error = yield u.error
            valid = yield u.valid
            yield
        yield
        # assert not (yield u.error)
        # assert (yield u.data)==0x56

    sim.add_sync_process(clock)
    sim.add_process(tb)
    sim.add_sync_process(check_output)

    with sim.write_vcd("UART_waves.vcd"):
        sim.run_until(2.5e-3)
        