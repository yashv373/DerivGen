module SRAM_Macro_IP(input wire clk, input wire we, input wire [10:0] addr, input wire [31:0] din, output reg [31:0] dout);
    reg [31:0] mem [0:2047]; // 8KB RAM
    always @(posedge clk) begin if (we) mem[addr] <= din; dout <= mem[addr]; end
endmodule
