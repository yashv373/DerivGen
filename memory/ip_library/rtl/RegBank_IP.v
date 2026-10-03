// RegBank_IP -- one writable control register on an APB slave port.
//
// Bus interfaces: apb (slave).

module RegBank_IP (
    input  wire        clk,
    input  wire        rst_n,

    input  wire [31:0] apb_paddr,
    input  wire        apb_psel,
    input  wire        apb_penable,
    input  wire        apb_pwrite,
    input  wire [31:0] apb_pwdata,
    output wire [31:0] apb_prdata,
    output wire        apb_pready,
    output wire        apb_pslverr,

    output reg  [31:0] ctrl_reg
);

    always @(posedge clk) begin
        if (!rst_n)
            ctrl_reg <= 32'd0;
        else if (apb_psel && apb_penable && apb_pwrite)
            ctrl_reg <= apb_pwdata;
    end

    // Only one register, so every address reads it back.
    assign apb_prdata  = ctrl_reg;
    assign apb_pready  = 1'b1;
    assign apb_pslverr = 1'b0;

endmodule
