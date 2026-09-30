from migen import Instance, Signal, ClockSignal, ResetSignal

def apply(soc):
    # Signals for UART
    soc.uart_tx = Signal()
    soc.uart_rx = Signal()
    soc.uart_irq = Signal()
    
    # tcl::add_instance -type dummy_uart -name u_uart
    soc.specials.u_uart = Instance("dummy_uart",
        i_clk=ClockSignal(),
        i_rst=ResetSignal(),
        i_rx=soc.uart_rx,
        o_tx=soc.uart_tx,
        o_irq=soc.uart_irq
    )
    
    # Signals for Crypto
    soc.crypto_debug_enable = Signal()
    soc.crypto_status_out = Signal()
    
    # tcl::add_instance -type dummy_crypto -name u_crypto
    soc.specials.u_crypto = Instance("dummy_crypto",
        i_clk=ClockSignal(),
        i_rst=ResetSignal(),
        i_debug_enable=soc.crypto_debug_enable,
        o_status_out=soc.crypto_status_out
    )
