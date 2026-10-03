from migen import Signal
def apply(soc):
    # tcl::export -net u_uart/tx -port uart_tx_o
    soc.uart_tx_o = Signal()
    soc.comb += soc.uart_tx_o.eq(soc.uart_tx)
    
    soc.crypto_status_o = Signal()
    soc.comb += soc.crypto_status_o.eq(soc.crypto_status_out)
    
    # Mark these signals to be exported to the top-level Verilog wrapper
    soc.ios.update({soc.uart_tx_o, soc.crypto_status_o})
