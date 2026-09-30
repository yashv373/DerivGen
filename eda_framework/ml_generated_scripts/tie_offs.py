def apply(soc):
    # tcl::tie -net u_crypto/debug_enable -value 0
    soc.comb += soc.crypto_debug_enable.eq(0)
    
    # Tie UART RX to 1 (idle)
    soc.comb += soc.uart_rx.eq(1)
