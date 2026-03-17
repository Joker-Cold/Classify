# script written by S. Pagliarini on July 2022. works well in genus 18.10

# to modify this script, look for TODO markers

# TODO change paths if needed
set RTL_PATH		"../../rtl"
set LIB_PATH 		"../../../../lib"
set LEF_PATH		"../../../../lef/scaled/"
set TLEF_PATH		"../../../../techlef"
set QRC_PATH		"../../../../qrc"


# TODO change design name if needed
set DESIGN  "des3"

#set MSGS_TO_BE_SUPRESSED {LBR-58 LBR-40 LBR-41 VLOGPT-35}

#set SYN_EFFORT		high
#set MAP_EFFORT		high
#set INC_EFFORT		high
#suppress_messages {LBR-30 LBR-31 LBR-40 LBR-41 LBR-72 LBR-77 LBR-162}
#set_attribute hdl_track_filename_row_col true /
#set_attribute lp_power_unit mW /


# Baseline Libraries
# TODO change library files if needed
set LIB_LIST {  asap7sc7p5t_AO_LVT_TT_nldm_211120.lib   asap7sc7p5t_INVBUF_LVT_TT_nldm_220122.lib   asap7sc7p5t_OA_LVT_TT_nldm_211120.lib   asap7sc7p5t_SEQ_LVT_TT_nldm_220123.lib   asap7sc7p5t_SIMPLE_LVT_TT_nldm_211120.lib \
 		asap7sc7p5t_AO_SLVT_TT_nldm_211120.lib  asap7sc7p5t_INVBUF_SLVT_TT_nldm_220122.lib  asap7sc7p5t_OA_SLVT_TT_nldm_211120.lib  asap7sc7p5t_SEQ_SLVT_TT_nldm_220123.lib  asap7sc7p5t_SIMPLE_SLVT_TT_nldm_211120.lib}

# TODO change LEF files if needed
set LEF_LIST { asap7_tech_4x_201209.lef asap7sc7p5t_28_L_4x_220121a.lef asap7sc7p5t_28_SL_4x_220121a.lef}

# TODO change RTL files if needed
set RTL_LIST {key_sel.v sbox6.v sbox5.v sbox8.v crp.v sbox3.v sbox1.v des3.v sbox2.v sbox7.v des.v sbox4.v}

# TODO change SDC file if needed
set SDC_FILE "../../sdc/des3.sdc"

set_db init_lib_search_path "$LIB_PATH $LEF_PATH $TLEF_PATH"
set_db init_hdl_search_path $RTL_PATH 
set_db / .library "$LIB_LIST"
set_db lef_library "$LEF_LIST"

read_hdl ${RTL_LIST}

# Elaborate the top level
# elaborate $DESIGN
elaborate

# Read the constraint file
#TODO change SDC file path if needed
read_sdc $SDC_FILE

# GENERIC SYNTHESIS
syn_generic

# MAPPING
syn_map

# OPT
syn_opt

#TODO change the output path if needed
write_hdl > ../../netlist/${DESIGN}_netlist.v

#TODO uncomment these lines to get reports directly on text files
# REPORTING (Timing, Area, Gates, Power)
#report timing > ./genus_timing.rep
#report area   > ./genus_area.rep
#report gates  > ./genus_cell.rep
#report power  > ./genus_power.rep


