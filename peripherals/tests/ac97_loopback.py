import os
import sys
from nmigen import *
from nmigen.sim import *
from nmigen.back.verilog import *
from nmigen.build import *
from nmigen.build.res import *
from nmigen.lib.io import Pin
from nmigen_boards.ml505 import ML505Platform

from peripherals.ac97 import AC97_Controller

class AC97_loopback(Elaboratable):
    def __init__(self):
        pass
            
    def elaborate(self, platform):
        m = Module()

        m.submodules.ac97 = self.ac97 = ac97 = AC97_Controller()
    
        if(platform != None):

            #Get the clock from the codec
            m.domains.audio_bit_clk = ClockDomain()
            audio_clk = platform.request("audio_bit_clk")
            m.d.comb += ClockSignal("audio_bit_clk").eq(audio_clk)
            
            #request the AC97 interface signals, with DDR for the input
            ac97_if = platform.request("audio_codec", 
                xdr={"sdata_in":2, "sdata_out":0, "audio_sync":0, "reset_o":0})
            ac97_if.sdata_in.i_clk = audio_clk
            ac97.sdata_in = ac97_if.sdata_in
            ac97.sdata_out = ac97_if.sdata_out
            ac97.sync_o = ac97_if.audio_sync
            ac97.reset_o = ac97_if.flash_audio_reset_b

        m.d.comb += [
            ac97.dac_channels_i.dac_left_front.eq(ac97.adc_channels_o.adc_left),
            ac97.dac_channels_i.dac_right_front.eq(ac97.adc_channels_o.adc_right),      
        ]

        return m

if __name__ == "__main__":
  
    tone = AC97_loopback()
 
    if sys.argv[1] == "build":
        ML505Platform().build(tone, do_build=False, do_program=False).execute_local(run_script=False)
    