module apb_regs (
    input  logic        pclk,
    input  logic        presetn,
    input  logic        psel,
    input  logic        penable,
    input  logic        pwrite,
    input  logic [3:0]  paddr,
    input  logic [31:0] pwdata,
    output logic [31:0] prdata,
    output logic        pready,
    output logic        pslverr
);

    logic [31:0] ctrl, data, scratch;
    logic        access;

    assign pready = 1'b1;
    assign access = psel && penable;

    // Write side
    always_ff @(posedge pclk) begin
        if (!presetn) begin
            ctrl    <= 32'h0;
            data    <= 32'h0;
            scratch <= 32'h0;
        end else if (access && pwrite) begin
            case (paddr)
                4'h0: ctrl    <= pwdata;
                4'h4: data    <= pwdata;
                4'hC: scratch <= pwdata;
                default: ;
            endcase
        end
    end

    // Read side and error
    always_comb begin
        prdata  = 32'h0;
        pslverr = 1'b0;
        case (paddr)
            4'h0: prdata = ctrl;
            4'h4: prdata = data;
            4'h8: begin
                prdata = 32'h0000_00A5;
                if (access && pwrite) pslverr = 1'b1;
            end
            4'hC: prdata = scratch;
            default: if (access) pslverr = 1'b1;
        endcase
    end

endmodule