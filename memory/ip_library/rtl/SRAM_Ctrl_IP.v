// SRAM_Ctrl_IP -- turns APB accesses into SRAM pin wiggles.
//
// Combinational glue, so no clock or reset: the SRAM macro holds the state.
//
// Bus interfaces: apb (slave).

module SRAM_Ctrl_IP (
    input  wire [31:0] apb_paddr,
    input  wire        apb_psel,
    input  wire        apb_penable,
    input  wire        apb_pwrite,
    input  wire [31:0] apb_pwdata,
    output wire [31:0] apb_prdata,
    output wire        apb_pready,
    output wire        apb_pslverr,

    // SRAM macro pins
    output wire        sram_we,
    output wire [10:0] sram_addr,
    output wire [31:0] sram_din,
    input  wire [31:0] sram_dout
);

    // Write when the bus is in its access phase and asking for a write.
    assign sram_we   = apb_psel && apb_penable && apb_pwrite;

    // Word addressing: drop the bottom two bits.
    assign sram_addr = apb_paddr[12:2];
    assign sram_din  = apb_pwdata;

    assign apb_prdata  = sram_dout;
    assign apb_pready  = 1'b1;   // no wait states
    assign apb_pslverr = 1'b0;   // never flags an error

endmodule
