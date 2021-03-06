from nmigen import *
from nmigen.sim import *
from nmigen.lib.cdc import *
from nmigen.lib.io import *
from nmigen.hdl.rec import Direction

# AC97 is a 16 bit "Tag" followed by 12 20-bit (signed) data backets,
# with the interface written to on rising edges of audio_bit_clk,
# and sampled on the falling edge

class AC97_DAC_Channels(Record):
    def __init__(self, name=None):
        layout = [
            # signed pcm inputs to dac
            ("dac_tag", 6, Direction.FANIN),                # Indicates which slots are valid
            ("dac_left_front", 20, Direction.FANIN),        # slot 3
            ("dac_right_front", 20, Direction.FANIN),       # slot 4
            ("dac_centre", 20, Direction.FANIN),            # slot 6
            ("dac_left_surround", 20, Direction.FANIN),     # slot 7
            ("dac_right_surround", 20, Direction.FANIN),    # slot 8
            ("dac_lfe", 20, Direction.FANIN),               # slot 9           
        ]
        super().__init__(layout, name=name, src_loc_at=1)

def ac97_dac_connect(domain, source, sink):
    domain += [
        sink.dac_tag.eq(source.dac_tag),
        sink.dac_left_front.eq(source.dac_left_front),
        sink.dac_right_front.eq(source.dac_right_front),
        sink.dac_centre.eq(source.dac_centre),
        sink.dac_left_surround.eq(source.dac_left_surround),
        sink.dac_right_surround.eq(source.dac_right_surround),
        sink.dac_lfe.eq(source.dac_lfe),
    ]

class AC97_ADC_Channels(Record):
    def __init__(self, name=None):
        layout = [
            ("adc_tag", 2, Direction.FANOUT),               # Indicates which slots are valid
            ("adc_left", 20, Direction.FANOUT),             # slot 3
            ("adc_right", 20, Direction.FANOUT),            # slot 4
        ]
        super().__init__(layout, name=name, src_loc_at=1)

def ac97_adc_connect(domain, source, sink):
    domain += [
        sink.adc_tag.eq(source.adc_tag),
        sink.adc_left.eq(source.adc_right),
        sink.adc_right.eq(source.adc_right),
    ]

class AC97_Controller(Elaboratable):
    # 
    def __init__(self):
        #AC97 signals
        self.sdata_in = Pin(width=1, dir="i", xdr = 2)
        self.sdata_out = Pin(width=1, dir="o")
        self.sync_o = Pin(width=1, dir="o")
        self.reset_o = Pin(width=1, dir="o")

        # signed pcm inputs to dac
        self.dac_channels_i = AC97_DAC_Channels(name="dac_channels_i")
        self.dac_sample_written_o = Signal()    # asserted for one cycle when inputs sampled
      
        # signed pcm outputs from adc
        self.adc_channels_o = AC97_ADC_Channels(name="adc_channels_o")
        self.adc_out_valid = Signal()           # indicates the window in which  the adc_ outputs can be read
        self.adc_sample_received = Signal()     # asserted for one cycle when acd_out becomes valid

        # Read or write to control register. Defaults to write
        self.reg_read = Signal()
        # Asserted if the echoed register address is the same as the written address
        self.addr_echo = Signal()

    def elaborate(self, platform):
        m = Module()

        dac_inputs_valid = Signal()
        dac_valid_ack_sync = Signal()
        
        #input buffers
        dac_channels = AC97_DAC_Channels(name="dac_channels")
             
        with m.If (~dac_inputs_valid & ~dac_valid_ack_sync):    
            m.d.sync += [
                dac_inputs_valid.eq(1),
            ]
            ac97_dac_connect(m.d.sync, self.dac_channels_i, dac_channels)

        with m.If (dac_inputs_valid & dac_valid_ack_sync):
            m.d.comb += self.dac_sample_written_o.eq(1)
            m.d.sync += dac_inputs_valid.eq(0)

        #audio_bit_clk domain
        dac_valid_ack = Signal()
        dac_inputs_valid_sync = Signal()
        m.submodules.dac_input_valid_2ff = FFSynchronizer(dac_inputs_valid,
            dac_inputs_valid_sync, o_domain="audio_bit_clk")
        m.submodules.dac_ack_2ff = FFSynchronizer(dac_valid_ack,
            dac_valid_ack_sync, o_domain="sync")

        dac_channels_sync = AC97_DAC_Channels(name="dac_channels_sync")     

        m.d.comb += [
            self.sync_o.o.eq(0),
        ]

        bit_count = Signal(5)
        shift_out = Signal(20)
        shift_in = Signal(20)
   
        m.d.audio_bit_clk += [
            bit_count.eq(bit_count-1),
            shift_out.eq(shift_out << 1),
            shift_in.eq(Cat(self.sdata_in.i1, shift_in[0:19])),
            self.sdata_out.o.eq(shift_out[19]),
        ]

        

        #adc data from deserialiser to outputs        
        adc_outputs_valid = Signal()
        adc_outputs_valid_sync = Signal()
        m.submodules.adc_output_valid_2ff = FFSynchronizer(adc_outputs_valid,
            adc_outputs_valid_sync, o_domain="sync")   
        adc_valid_ack = Signal()
        adc_valid_ack_sync = Signal()
        m.submodules.adc_valid_ack_2ff = FFSynchronizer(adc_valid_ack,
            adc_valid_ack_sync, o_domain="audio_bit_clk")

        adc_channels_bit_clk = AC97_ADC_Channels(name="adc_channels_bit_clk")
        m.d.comb += self.adc_sample_received.eq(0)
        
        with m.If(~adc_valid_ack & adc_outputs_valid_sync):
            m.d.comb += self.adc_sample_received.eq(1)
            m.d.sync += adc_valid_ack.eq(1)
            ac97_adc_connect(m.d.sync, adc_channels_bit_clk, self.adc_channels_o)
        with m.If(~adc_outputs_valid_sync):
            m.d.sync += adc_valid_ack.eq(0)

        # AC97 interface
        command_select = Signal(2)
        write_address = Signal(20)
        address_echo = Signal(20)
        m.d.comb += self.addr_echo.eq( ~((write_address ^ address_echo).any()) )
        with m.FSM(domain="audio_bit_clk") as ac97_if:
            with m.State("IO_CTRL"):
                m.d.audio_bit_clk += adc_outputs_valid.eq(1)
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += [
                        bit_count.eq(15),
                        shift_out.eq(0xf9800),  #valid command address, command data, line out, l/r surround out
                        command_select.eq(command_select + 1),
                    ]
                    m.next = "TAG"
            with m.State("TAG"):
                m.d.comb += self.sync_o.o.eq(1)
                with m.If(adc_valid_ack_sync):
                    m.d.audio_bit_clk += adc_outputs_valid.eq(0)
                with m.If(~dac_valid_ack & dac_inputs_valid_sync):
                    m.d.audio_bit_clk += [
                        dac_valid_ack.eq(1),                               
                    ]
                    ac97_dac_connect(m.d.audio_bit_clk, dac_channels, dac_channels_sync)
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += [
                        bit_count.eq(19),
                        adc_channels_bit_clk.adc_tag.eq(Cat(self.sdata_in.i1, shift_in[10])),
                    ]
                    #send a command. for the basics it will loop through master volume, line out, headphones
                    with m.Switch(command_select):
                        with m.Case(0):
                            m.d.audio_bit_clk += [
                                shift_out.eq( Cat(Const(0x02000, 19), self.reg_read)),  #master volume
                                write_address.eq(Cat(Const(0x02000, 19), self.reg_read)),
                            ]
                        with m.Case(1):
                            m.d.audio_bit_clk += [
                                shift_out.eq( Cat(Const(0x04000, 19), self.reg_read)),  #headphones volume
                                write_address.eq(Cat(Const(0x04000, 19), self.reg_read)),
                            ]
                        with m.Case(2):
                            m.d.audio_bit_clk += [
                                shift_out.eq( Cat(Const(0x18000, 19), self.reg_read)),  #line out volume
                                write_address.eq(Cat(Const(0x18000, 19), self.reg_read)),
                            ]
                        with m.Case(3):
                            m.d.audio_bit_clk += [
                                shift_out.eq( Cat(Const(0x0e000, 19), self.reg_read)), #mic in volume
                                write_address.eq(Cat(Const(0x0e000, 19), self.reg_read)),
                            ]
                    m.next = "CMD_ADDR"
            with m.State("CMD_ADDR"):
                with m.If(dac_valid_ack & ~dac_inputs_valid_sync):
                    m.d.audio_bit_clk += dac_valid_ack.eq(0)
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += bit_count.eq(19)
                    # don't need specifics since writing zeroes to these registers should unmute the channels
                    m.next = "CMD_DATA"
            with m.State("CMD_DATA"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += [
                        bit_count.eq(19),
                        shift_out.eq(dac_channels_sync.dac_left_front),
                    ]
                    m.next = "L_FRONT"
            with m.State("L_FRONT"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += [
                        bit_count.eq(19),
                        shift_out.eq(dac_channels_sync.dac_right_front),  
                        adc_channels_bit_clk.adc_left.eq(Cat(self.sdata_in.i1, shift_in[0:19])),
                    ]
                    m.next = "R_FRONT"
            with m.State("R_FRONT"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += [
                        bit_count.eq(19),
                        adc_channels_bit_clk.adc_right.eq(Cat(self.sdata_in.i1, shift_in[0:19])),
                    ]
                    m.next = "LINE_1"
            with m.State("LINE_1"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += bit_count.eq(19)
                    m.next = "CENTER_MIC"
            with m.State("CENTER_MIC"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += [
                        bit_count.eq(19),
                        shift_out.eq(dac_channels_sync.dac_left_surround),
                    ]
                    m.next = "L_SURR"
            with m.State("L_SURR"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += [
                        bit_count.eq(19),
                        shift_out.eq(dac_channels_sync.dac_right_surround),
                    ]
                    m.next = "R_SURR"
            with m.State("R_SURR"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += bit_count.eq(19)
                    m.next = "LFE"
            with m.State("LFE"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += bit_count.eq(19)
                    m.next = "LINE_2"
            with m.State("LINE_2"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += bit_count.eq(19)
                    m.next = "HSET"
            with m.State("HSET"):
                with m.If(~bit_count.any()):
                    m.d.audio_bit_clk += bit_count.eq(19)
                    m.next = "IO_CTRL"
                   
        return m


if __name__=="__main__":

    dut = AC97_Controller()
    sim = Simulator(dut)
    sim.add_clock(10e-9) #100MHz
    sim.add_clock(81e-9, domain="audio_bit_clk")
    

    def clock():
        while True:
            yield
    
    def data_input():
        yield dut.dac_channels_i.dac_left_front.eq(10)

    def adc_input():
        for n in range(0, 56):
            yield
        while True:
            yield dut.sdata_in.i1.eq(1)
            yield
            yield dut.sdata_in.i1.eq(0)
            yield

    sim.add_sync_process(clock)
    sim.add_sync_process(data_input, domain="sync")
    sim.add_sync_process(adc_input, domain="audio_bit_clk")

    with sim.write_vcd("ac97_waves.vcd"):
        sim.run_until(1e-4, run_passive=True)
