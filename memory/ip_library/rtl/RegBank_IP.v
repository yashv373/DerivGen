module RegBank_IP(
    input wire clk, input wire rst,
    input wire [31:0] apb_in,
    output reg [127:0] ctrl_regs
);
    // Extremely simplified APB-like register write
    always @(posedge clk) begin
        if (rst) ctrl_regs <= 128'd0;
        else if (apb_in[31]) ctrl_regs[31:0] <= apb_in; // dummy write
    end
endmodule
