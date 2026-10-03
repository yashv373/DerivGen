module Complex_Parity_Flop_IP(
    input wire clk, input wire rst_n, input wire en, input wire scan_in,
    input wire [31:0] d,
    output reg [31:0] q,
    output wire parity_out
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            q <= 32'd0;
        else if (en)
            q <= d;
        // scan_in logic would go here for DFT
    end
    // Even parity generator
    assign parity_out = ^q; 
endmodule
