// Bus_Fabric_IP -- one APB slave in, four APB masters out.
//
// Pure address decode and muxing: port N is selected when paddr[13:12] == N.
// Combinational, so no clock or reset.
//
// Four ports with only three peripherals in the parent platform is on
// purpose. The spare slot is what a scale-up derivative clones into.
//
// Bus interfaces: s_apb (slave), m0_apb, m1_apb, m2_apb, m3_apb (masters).

module Bus_Fabric_IP (
    // slave side: the host drives this
    input  wire [31:0] s_apb_paddr,
    input  wire        s_apb_psel,
    input  wire        s_apb_penable,
    input  wire        s_apb_pwrite,
    input  wire [31:0] s_apb_pwdata,
    output wire [31:0] s_apb_prdata,
    output wire        s_apb_pready,
    output wire        s_apb_pslverr,

    // master side, port 0
    output wire [31:0] m0_apb_paddr,
    output wire        m0_apb_psel,
    output wire        m0_apb_penable,
    output wire        m0_apb_pwrite,
    output wire [31:0] m0_apb_pwdata,
    input  wire [31:0] m0_apb_prdata,
    input  wire        m0_apb_pready,
    input  wire        m0_apb_pslverr,

    // master side, port 1
    output wire [31:0] m1_apb_paddr,
    output wire        m1_apb_psel,
    output wire        m1_apb_penable,
    output wire        m1_apb_pwrite,
    output wire [31:0] m1_apb_pwdata,
    input  wire [31:0] m1_apb_prdata,
    input  wire        m1_apb_pready,
    input  wire        m1_apb_pslverr,

    // master side, port 2
    output wire [31:0] m2_apb_paddr,
    output wire        m2_apb_psel,
    output wire        m2_apb_penable,
    output wire        m2_apb_pwrite,
    output wire [31:0] m2_apb_pwdata,
    input  wire [31:0] m2_apb_prdata,
    input  wire        m2_apb_pready,
    input  wire        m2_apb_pslverr,

    // master side, port 3 -- spare slot
    output wire [31:0] m3_apb_paddr,
    output wire        m3_apb_psel,
    output wire        m3_apb_penable,
    output wire        m3_apb_pwrite,
    output wire [31:0] m3_apb_pwdata,
    input  wire [31:0] m3_apb_prdata,
    input  wire        m3_apb_pready,
    input  wire        m3_apb_pslverr
);

    // Address, data and control go to every port unchanged.
    assign m0_apb_paddr   = s_apb_paddr;
    assign m1_apb_paddr   = s_apb_paddr;
    assign m2_apb_paddr   = s_apb_paddr;
    assign m3_apb_paddr   = s_apb_paddr;

    assign m0_apb_pwdata  = s_apb_pwdata;
    assign m1_apb_pwdata  = s_apb_pwdata;
    assign m2_apb_pwdata  = s_apb_pwdata;
    assign m3_apb_pwdata  = s_apb_pwdata;

    assign m0_apb_pwrite  = s_apb_pwrite;
    assign m1_apb_pwrite  = s_apb_pwrite;
    assign m2_apb_pwrite  = s_apb_pwrite;
    assign m3_apb_pwrite  = s_apb_pwrite;

    assign m0_apb_penable = s_apb_penable;
    assign m1_apb_penable = s_apb_penable;
    assign m2_apb_penable = s_apb_penable;
    assign m3_apb_penable = s_apb_penable;

    // Only the addressed port gets selected.
    assign m0_apb_psel = s_apb_psel && (s_apb_paddr[13:12] == 2'd0);
    assign m1_apb_psel = s_apb_psel && (s_apb_paddr[13:12] == 2'd1);
    assign m2_apb_psel = s_apb_psel && (s_apb_paddr[13:12] == 2'd2);
    assign m3_apb_psel = s_apb_psel && (s_apb_paddr[13:12] == 2'd3);

    // Read data and status come back from whichever port is selected.
    assign s_apb_prdata  = m0_apb_psel ? m0_apb_prdata :
                           m1_apb_psel ? m1_apb_prdata :
                           m2_apb_psel ? m2_apb_prdata :
                           m3_apb_psel ? m3_apb_prdata : 32'd0;

    assign s_apb_pready  = m0_apb_psel ? m0_apb_pready :
                           m1_apb_psel ? m1_apb_pready :
                           m2_apb_psel ? m2_apb_pready :
                           m3_apb_psel ? m3_apb_pready : 1'b1;

    assign s_apb_pslverr = m0_apb_psel ? m0_apb_pslverr :
                           m1_apb_psel ? m1_apb_pslverr :
                           m2_apb_psel ? m2_apb_pslverr :
                           m3_apb_psel ? m3_apb_pslverr : 1'b0;

endmodule
