from nmigen import *
from nmigen.build import *
from nmigen.build.res import *

import itertools

def get_xilinx_BRAM_SDP(address, data_in, data_out, write_en, clk, rst, size=16, init_data=None, pipeline_reg=True):
    # Signals:
    # address: 9/10 bit wide address bus, for 16 or 32k block respectively
    # data_in, data_out: 32 bit data ports
    # write_en: 4 bit per-byte write-enable
    # clk, rst: clock and reset
    # size: one of 16 or 32 (kilobits)
    # init_data: an optional dict packed appropriately
    # pipeline reg: enables the output registers for higher fmax
    assert ~(size==16 | size==32)
    primitive = "RAMB18SDP" if (size==16) else "RAMB36SDP"
    # 3 possible macros: SDP, TDP (simple/true dual port), SINGLE. start with single.
    bram = Instance(primitive, 
        p_DO_REG = int(pipeline_reg),
        #   each INIT_xx paramater represents a block of 8 words
        #   (BRAM is 32 bits wide without parity)
        #   MSB first in the parameter
        **init_data,
        o_DO = data_out,              
        i_WRADDR = address,
        i_RDADDR = address,
        i_WRCLK = clk,
        i_RDCLK = clk,
        i_DI = data_in,
        i_RDEN = Const(1, unsigned(1)),
        i_WREN = Const(0, unsigned(1)),
        i_REGCE = Const(1, unsigned(1)),
        i_SSR = rst,
        i_WE = write_en,
        )
    return bram

#copied direct from nco lut
def twos_complement(decimal, bits=32):
    if(decimal >= 0):
        return decimal
    else:
        inverted = 2**bits + decimal
        return twos_complement(inverted, bits)

def generate_init_data(size, input_list, signed_output = True):
    assert ~(size==16 | size==32)
    init_data = {}
    for line in range(0, 4*size):  # 64 for 18k BRAM
        init_line = 0
        for word in range(0, 8):    # each verilog parameter contains 8 32 bit words
            decimal = input_list[(line*8 + word)]
            if signed_output:
                decimal = twos_complement(decimal, 32)  # BRAM has a native width of 32
            init_line += (decimal << word*32)
        line_string = str(hex(line)).upper()[2:]
        while len(line_string) < 2:
            line_string = '0' + line_string
        init_data['p_INIT_'+ line_string] = init_line
    return init_data

# useful for making sure names don't clash and possibly confuse tool
class BROMWrapper(Elaboratable):
    def __init__(self, ROM_data, size=16, pipeline_reg = True):
        self.read_port = Signal(32)
        self.address = Signal( unsigned(int(8 + (size/16))) )
        self.ROM_data = ROM_data
        self.pipeline_reg = pipeline_reg
        self.size = size
    def elaborate(self, platform):
        m = Module()
        if (platform != None):
            bram_prim = get_xilinx_BRAM_SDP(self.address, Const(0, unsigned(32)), self.read_port, 
                Const(0, unsigned(4)), ClockSignal(), ResetSignal(), size=self.size, init_data=self.ROM_data, pipeline_reg=self.pipeline_reg)
            m.submodules.__brom_0 = bram_prim
        else:            
            with m.Switch(self.address):
                for entry in range(0, len(self.ROM_data)):
                    line_string = str(hex(entry)).upper()[2:]
                    while len(line_string) < 2:
                        line_string = '0' + line_string
                    line_string = "p_INIT_"+line_string
                    line = self.ROM_data[line_string]
                    for n in range(0, 8):
                        with m.Case(entry*4+n):
                            m.d.sync += self.read_port.eq((line >> 32*n) % 2**32)
        
        return m

class BRAMTest(Elaboratable):
    def __init__(self):
        pass

    def elaborate(self, platform):

        def get_all_resources(name):
            resources = []
            for number in itertools.count():
                try:
                    resources.append(platform.request(name, number))
                except ResourceError:
                    break
            return resources

        m=Module()

        led     = [res.o for res in get_all_resources("led")]
        switches = [res.i for res in get_all_resources("switch")]
       
        init = { 'p_INIT_00':Const(10, unsigned(256)) }
        bram = BROMWrapper(init, size=16)
        m.submodules.bram = bram

        m.d.comb += [
            bram.address.eq( Cat(switches, Const(0, unsigned(1))) ),
            Cat(led[0], led[1]).eq(bram.read_port[0:2]),
            led[2].eq(switches[0]),
        ]

        return m

if __name__=="__main__":    
    bram_test = BRAMTest()
    from nmigen_boards.ml505 import ML505Platform
    from nmigen_boards.test.blinky import *
    ML505Platform().build(bram_test, do_build=False, do_program=False).execute_local(run_script=False)