// Data_Aggregator_IP -- one interrupt if any alert line is high.

module Data_Aggregator_IP (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] alert_bus,
    output reg         intr
);

    always @(posedge clk) begin
        if (!rst_n)
            intr <= 1'b0;
        else
            intr <= |alert_bus;
    end

endmodule
