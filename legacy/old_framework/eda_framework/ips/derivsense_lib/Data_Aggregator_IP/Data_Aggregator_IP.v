module Data_Aggregator_IP(
    input wire clk_fast, input wire rst,
    input wire [31:0] alert_bus,
    output reg aggregated_intr
);
    // Triggers interrupt if ANY sensor alerts
    always @(posedge clk_fast) begin
        if (rst) aggregated_intr <= 1'b0;
        else aggregated_intr <= |alert_bus;
    end
endmodule
