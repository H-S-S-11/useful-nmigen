from ac97 import *

class AC97_write_read(Elaboratable):
    def __init__(self):
        self.led = Pin(1, 'o')
    
    def elaborate(self, platform):
        m = Module()

        m.d.submodules.ac97 = ac97 = AC97_Controller()
        self.led = platform.request('led')
        m.d.comb += self.led.o.eq(ac97.addr_echo)

        return m

if __name__=="__main__":
    from nmigen_boards.ml505 import *
    ac97_test = AC97_write_read()
    ML505Platform().build(ac97_test, do_program=False)
