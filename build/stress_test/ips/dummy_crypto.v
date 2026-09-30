module dummy_crypto(
    input wire clk,
    input wire rst,
    input wire debug_enable,
    output wire status_out
);
    assign status_out = 1'b0;
endmodule
