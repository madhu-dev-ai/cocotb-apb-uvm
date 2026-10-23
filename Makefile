SIM ?= icarus
TOPLEVEL_LANG = verilog
VERILOG_SOURCES = $(CURDIR)/apb_regs.sv
COMPILE_ARGS += -g2012
COCOTB_TOPLEVEL = apb_regs
COCOTB_TEST_MODULES = test_uvm
include $(shell cocotb-config --makefiles)/Makefile.sim