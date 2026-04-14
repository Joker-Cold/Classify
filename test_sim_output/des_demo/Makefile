# des_demo Makefile
# DES3 加密核 (~64K cells) - 基准电路，已有完整仿真数据

CIRCUIT     := des_demo
CELLS       := 64K
DOCKER      := docker exec grj-dev
APP_BASE    := /app/Classify

# 源文件路径
NETLIST     := $(APP_BASE)/des_demo/db/des3.v
SDC         := $(APP_BASE)/des_demo/sdc/des3.sdc
SPEF        := $(APP_BASE)/des_demo/db/des3.spef
DEF         := $(APP_BASE)/des_demo/db/des3.def

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

# ============================================================
# Stage 2: VCD 仿真（远程服务器）
# ============================================================
.PHONY: sim
sim:
	@echo "[$(CIRCUIT)] VCD 仿真 - 请在远程服务器上执行"
	@echo "  参考: Classify/des_demo/vcd/vcs.sh"
	@echo "  已有 VCD: Classify/des_demo/vcd/test.vcd"

# ============================================================
# Stage 3: Voltus 仿真（远程服务器）
# ============================================================
.PHONY: voltus-full voltus-traditional voltus-risk
voltus-full:
	@echo "[$(CIRCUIT)] Voltus 全量仿真 → sim_data/full/"
	@echo "  参考: Classify/des_demo/script/innovus/power_analyze.tcl"
	@echo "  参考: Classify/des_demo/script/innovus/rail_analyze.tcl"

voltus-traditional:
	@echo "[$(CIRCUIT)] Voltus Traditional 选窗仿真 → sim_data/traditional/"

voltus-risk:
	@echo "[$(CIRCUIT)] Voltus Risk Propagation 选窗仿真 → sim_data/risk_propagation/"

# ============================================================
# Stage 4: Python 工具链分析（Docker grj-dev）
# ============================================================
.PHONY: analyze analyze-toggle analyze-power analyze-select coverage

# Step 4a: VCD → JSONL → Toggle 标记
analyze-toggle:
	$(DOCKER) python $(TVP_DIR)/vcd_to_jsonl.py \
		--vcd $(VCD_DIR)/sim.vcd \
		--output $(ANALYSIS)/sim.jsonl
	$(DOCKER) python $(TVP_DIR)/jsonl_toggle_mark.py \
		--input $(ANALYSIS)/sim.jsonl \
		--output $(ANALYSIS)/toggles.jsonl

# Step 4b: 功率矩阵生成
analyze-power:
	$(DOCKER) python $(TVP_DIR)/traditional_select.py \
		--input $(ANALYSIS)/toggles.jsonl \
		--output $(ANALYSIS)/power_matrix.json

# Step 4c: 最差窗口选择 + VCD 压缩
analyze-select:
	$(DOCKER) python $(WKW_DIR)/select_worst_k.py \
		--input $(ANALYSIS)/power_matrix.json \
		--output $(ANALYSIS)/report.json

# 覆盖率评估
coverage:
	$(DOCKER) python $(COV_DIR)/evaluate.py \
		--full $(OUT_BASE)/sim_data/full/rail/VDD_VSS.iv \
		--compressed $(OUT_BASE)/sim_data/traditional/rail/VDD_VSS.iv \
		--output $(COVERAGE)/coverage_traditional.csv
	$(DOCKER) python $(COV_DIR)/evaluate.py \
		--full $(OUT_BASE)/sim_data/full/rail/VDD_VSS.iv \
		--compressed $(OUT_BASE)/sim_data/risk_propagation/rail/VDD_VSS.iv \
		--output $(COVERAGE)/coverage_risk.csv

# 完整分析流程
analyze: analyze-toggle analyze-power analyze-select

# 全流程
.PHONY: all
all: analyze coverage
	@echo "[$(CIRCUIT)] 全流程完成"

.PHONY: clean
clean:
	rm -f $(ANALYSIS)/*.jsonl $(ANALYSIS)/*.json
	rm -f $(COVERAGE)/*.csv $(COVERAGE)/*.md
