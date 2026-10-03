module Core_FSM_IP(
    input wire clk_fast, input wire rst,
    input wire [31:0] sensor_data,
    output reg [31:0] state_out,
    output reg mem_write
);
    parameter IDLE = 0, PROCESS = 1, WRITE = 2;
    reg [1:0] state;
    always @(posedge clk_fast) begin
        if (rst) begin state <= IDLE; state_out <= 0; mem_write <= 0; end
        else case(state)
            IDLE: if (sensor_data > 0) state <= PROCESS;
            PROCESS: begin state_out <= sensor_data ^ 32'hAAAA_5555; state <= WRITE; end
            WRITE: begin mem_write <= 1; state <= IDLE; end
        endcase
    end
endmodule
