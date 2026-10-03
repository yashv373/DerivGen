// UART_TX_IP -- drives the tx pin from APB writes.
//
// Deliberately not a real UART: no baud divider, no shift register. Writing
// the register puts its low bit straight on the pin. The point is the port
// list, not the protocol.
//
// Bus interfaces: apb (slave).

module UART_TX_IP (
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

    output reg         tx
);

    always @(posedge clk) begin
        if (!rst_n)
            tx <= 1'b1;          // an idle UART line sits high
        else if (apb_psel && apb_penable && apb_pwrite)
            tx <= apb_pwdata[0];
    end

    assign apb_prdata  = {31'd0, tx};
    assign apb_pready  = 1'b1;
    assign apb_pslverr = 1'b0;

endmodule
