module dummy_crypto(
    input wire clk,
    input wire rst,
    input wire debug_enable,
    output wire status_out
);
    assign status_out = ~debug_enable;
endmodule
