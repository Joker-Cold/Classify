# leon3mp_slow Makefile
# LEON3 SPARC V8 处理器核 (649K cells) - ISPD2012 基准

CIRCUIT     := leon3mp_slow
CELLS       := 649K
DOCKER      := docker exec grj-dev
APP_BASE    := /app/Classify

# 源文件路径（ISPD2012）
SRC_DIR     := $(APP_BASE)/test_circuit/ispd2012/leon3mp_slow
NETLIST     := $(SRC_DIR)/leon3mp_slow.v
SDC         := $(SRC_DIR)/leon3mp_slow.sdc
SPEF        := $(SRC_DIR)/leon3mp_slow.spef
LIB         := $(APP_BASE)/test_circuit/ispd2012/lib/contest.lib

# 工具链脚本路径
TVP_DIR     := $(APP_BASE)/Traditional_Vector_Profiling/code
RPP_DIR     := $(APP_BASE)/risk_propagation_profiling/code
WKW_DIR     := $(APP_BASE)/worst_k_windows/code
COV_DIR     := $(APP_BASE)/coverage_analysis/code

# 输出目录（容器内路径）
OUT_BASE    := $(APP_BASE)/test_sim_output/$(CIRCUIT)
VCD_DIR     := $(OUT_BASE)/vcd
ANALYSIS    := $(OUT_BASE)/analysis
COVERAGE    := $(OUT_BASE)/analysis/coverage

.PHONY: sim
sim:
	@echo "[$(CIRCUIT)] VCD 仿真 - 需先编写 testbench"
	@echo "  网表: $(NETLIST) (73MB, 仿真耗时较长)"
	@echo "  SDC:  $(SDC)"

.PHONY: voltus-full voltus-traditional voltus-risk
voltus-full:
	@echo "[$(CIRCUIT)] Voltus 全量仿真 → sim_data/full/"
voltus-traditional:
	@echo "[$(CIRCUIT)] Voltus Traditional 选窗仿真 → sim_data/traditional/"
voltus-risk:
	@echo "[$(CIRCUIT)] Voltus Risk Propagation 选窗仿真 → sim_data/risk_propagation/"

.PHONY: analyze analyze-toggle analyze-power analyze-select coverage

analyze-toggle:
	$(DOCKER) python $(TVP_DIR)/vcd_to_jsonl.py \
		--vcd $(VCD_DIR)/sim.vcd \
		--output $(ANALYSIS)/sim.jsonl
	$(DOCKER) python $(TVP_DIR)/jsonl_toggle_mark.py \
		--input $(ANALYSIS)/sim.jsonl \
		--output $(ANALYSIS)/toggles.jsonl

analyze-power:
	$(DOCKER) python $(TVP_DIR)/traditional_select.py \
		--input $(ANALYSIS)/toggles.jsonl \
		--output $(ANALYSIS)/power_matrix.json

analyze-select:
	$(DOCKER) python $(WKW_DIR)/select_worst_k.py \
		--input $(ANALYSIS)/power_matrix.json \
		--output $(ANALYSIS)/report.json

coverage:
	$(DOCKER) python $(COV_DIR)/evaluate.py \
		--full $(OUT_BASE)/sim_data/full/rail/VDD_VSS.iv \
		--compressed $(OUT_BASE)/sim_data/traditional/rail/VDD_VSS.iv \
		--output $(COVERAGE)/coverage_traditional.csv
	$(DOCKER) python $(COV_DIR)/evaluate.py \
		--full $(OUT_BASE)/sim_data/full/rail/VDD_VSS.iv \
		--compressed $(OUT_BASE)/sim_data/risk_propagation/rail/VDD_VSS.iv \
		--output $(COVERAGE)/coverage_risk.csv

analyze: analyze-toggle analyze-power analyze-select

.PHONY: all
all: analyze coverage
	@echo "[$(CIRCUIT)] 全流程完成"

.PHONY: clean
clean:
	rm -f $(ANALYSIS)/*.jsonl $(ANALYSIS)/*.json
	rm -f $(COVERAGE)/*.csv $(COVERAGE)/*.md
