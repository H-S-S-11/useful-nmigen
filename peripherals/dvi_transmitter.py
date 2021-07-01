"""
Interface for a CH7301C DVI transmitter.
Has 12 bit data bus, differential clock from FPGA to transmitter,
HSYNC and VSYNC, Data Enable, and an active low reset.
Data enable will be high whenever valid video data is transmitted.
-----------------------------------------------------------------------------
To simplify the controller, we will assume the control registers have
their default values (to avoid the need to change them). This means:
-XCLK is the same as the pixel clock, and data is read by the CH7301C on both clock edges.

Data is 24 bit RGB. 
On the rising edge of XCLK, D[7:0] contains the blue value, and D[11:8] is the LSBs of Green.
On the falling edge of XCLK D[3:0] contains the MSBs of green and D[11:4] contains Red.

HSYNC and VSYNC are both low when valid data is transmitted.
The pixel clock should be below 65MHz to avoid the need to change PLL settings.
Possible that registers will need to be written to match table 10:
Reg | <65MHz | >65MHz
33h | 08h    | 06h
34h | 16h    | 26h
36h | 60h    | A0h
Device starts in full power down mode so will need to write C0h to register 49h.
"""