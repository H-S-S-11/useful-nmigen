from nmigen import *
from nmigen.build import *
from nmigen_boards.resources import *
from nmigen_boards.ml505 import *

class ML505LunaClockDomains(Elaboratable):
    def __init__(self, *, clock_frequencies=None, clock_signal_name=None):
        pass

    def elaborate(self, platform):
        m = Module()

        # Create clock domains and get source clock
        m.domains.usb       = ClockDomain()
        m.domains.usb_io    = ClockDomain()
        m.domains.sync      = ClockDomain()

        clk100 = platform.request("clk100")

        # Instantiate USB Full-speed PLL and required BUFGs
        clk12       = Signal()
        clk48       = Signal()
        clk12_buf   = Signal()
        clk48_buf   = Signal()
        usb2_lock   = Signal()
        usb2_fb     = Signal()
        m.submodules.usb_pll = Instance("PLL_ADV",
            p_BANDWIDTH             = "OPTIMIZED",
            p_COMPENSATION          = "SYSTEM_SYNCHRONOUS",
            p_DIVCLK_DIVIDE         = 5,
            p_CLKFBOUT_MULT         = 24,
            p_CLKOUT0_DIVIDE        = 40,
            p_CLKOUT0_PHASE         = 0.00,
            p_CLKOUT0_DUTY_CYCLE    = 0.500,
            p_CLKOUT1_DIVIDE        = 10,
            p_CLKOUT1_PHASE         = 0.00,
            p_CLKOUT1_DUTY_CYCLE    = 0.500,
            p_CLKIN1_PERIOD         = 10.000,
            i_CLKINSEL              = Const(1),
            i_CLKFBIN               = usb2_fb,
            o_CLKFBOUT              = usb2_fb,
            i_CLKIN1                = clk100,
            o_CLKOUT0               = clk12,
            o_CLKOUT1               = clk48,
            o_LOCKED                = usb2_lock,
        )
        m.submodules.clk12_bufg = Instance("BUFG",
            i_I = clk12,
            o_O = clk12_buf,
        )
        m.submodules.clk48_bufg = Instance("BUFG",
            i_I = clk48,
            o_O = clk48_buf,
        )

        # Connect clocks to domains
        m.d.comb += [
            ClockSignal("usb")      .eq(clk12_buf),
            ClockSignal("usb_io")   .eq(clk48_buf),
            ResetSignal("usb")      .eq(~usb2_lock),
            ResetSignal("usb_io")   .eq(~usb2_lock),
        ]

        return m