// Core_FSM_IP -- three-state controller over the sensor stream.

module Core_FSM_IP (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] data_in,
    output reg  [31:0] state,
    output reg         mem_write
);

    localparam [1:0] IDLE = 2'd0, PROCESS = 2'd1, WRITE = 2'd2;

    always @(posedge clk) begin
        if (!rst_n) begin
            state     <= 32'd0;
            mem_write <= 1'b0;
        end else begin
            case (state[1:0])
                IDLE:    begin
                    mem_write <= 1'b0;
                    if (data_in != 32'd0) state <= {30'd0, PROCESS};
                end
                PROCESS: begin
                    mem_write <= 1'b0;
                    state     <= {30'd0, WRITE};
                end
                default: begin
                    mem_write <= 1'b1;
                    state     <= {30'd0, IDLE};
                end
            endcase
        end
    end

endmodule
