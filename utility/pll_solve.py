def pll_solve_virtex5(input_frequency=100e6, output_frequency=50e6, max_error_allowed=0):
    # CLKIN*(M/D) must be between 400M and 1000M
    # Multiply between 1 and 64
    # Divide between 1 and 52
    # Output divide from 1 to 128
    vco_targets = []
    mults = []
    for clkout_div in range(1, 129):
        if (400e6 <= clkout_div*output_frequency <= 1000e6):
            vco_targets.append(clkout_div*output_frequency)
    print(vco_targets)
    for freq in vco_targets:
        for clkin_div in range(1, 53):
            clkout_div = freq/output_frequency
            clkin_mult = int((clkin_div*freq) / input_frequency)
            freq_out = (input_frequency*clkin_mult)/(clkin_div*clkout_div)
            error = abs(output_frequency-freq_out)
            if error <= max_error_allowed:
                if 1 <= clkin_mult <= 64:
                    combination = {                        
                        "clkin_div"  : clkin_div,
                        "clkin_mult" : clkin_mult,
                        "vco_freq"   : freq,
                        "clkout_div" : freq/output_frequency,
                        "freq_out"   : freq_out,
                        "error"      : error,
                    }
                    mults.append(combination)

    return mults

if __name__=="__main__":
    multipliers = pll_solve_virtex5(input_frequency=100e6, 
        output_frequency=106.5e6, max_error_allowed=0.25e6)
    for values in multipliers:
        print(values)