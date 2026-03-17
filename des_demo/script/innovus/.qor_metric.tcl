define_metric -name rail.ir.worstiv.net:<net> -description "The worst instance voltage in the report file" -cmp lessBetter
set_metric -name rail.worstivreport.power_domain:PD -value "../../db/rail_power/PD_25C_dynamic_1//VDD_VSS.worst.iv "
set_metric -name rail.ir.dynamic.min.net:VDD -value "0.671845 V"
set_metric -name rail.ir.dynamic.max.net:VDD -value "0.7 V"
set_metric -name rail.ir.dynamic.avg.net:VDD -value "0.68359 V"
set_metric -name rail.ir.dynamic.violations.net:VDD -value 0
set_metric -name rail.thresholdvoltage.net:VDD -value "0.651 V"
set_metric -name rail.referencevoltage.net:VDD -value "0.7 V"
set_metric -name rail.worstircycle.net:VDD -value "50.000 nS"
set_metric -name rail.rj.min.net:VDD -value NA
set_metric -name rail.rj.max.net:VDD -value NA
set_metric -name rail.rj.avg.net:VDD -value NA
set_metric -name rail.rj.violations.net:VDD -value 0
set_metric -name rail.gridcap.net:VDD -value "1.853 pF"
set_metric -name rail.intrinsiccap.net:VDD -value "0.000 F"
set_metric -name rail.loadingcap.net:VDD -value "46.978 pF"
set_metric -name rail.totalcap.net:VDD -value "48.831 pF"
set_metric -name rail.averagedemandcurrent.net:VDD -value "0.000839432 A"
set_metric -name rail.peakdemandcurrent.net:VDD -value "0.0152808 A"
set_metric -name rail.averagesupplycurrent.net:VDD -value "0.000839416 A"
set_metric -name rail.peaksupplycurrent.net:VDD -value "0.0139797 A"
set_metric -name rail.ir.worstiv.net:VDD -value "0.671845 V"
set_metric -name rail.ir.dynamic.min.net:VSS -value "0 V"
set_metric -name rail.ir.dynamic.max.net:VSS -value "0.0245852 V"
set_metric -name rail.ir.dynamic.avg.net:VSS -value "0.0156052 V"
set_metric -name rail.ir.dynamic.violations.net:VSS -value 0
set_metric -name rail.thresholdvoltage.net:VSS -value "0.1 V"
set_metric -name rail.referencevoltage.net:VSS -value "0 V"
set_metric -name rail.worstircycle.net:VSS -value "50.000 nS"
set_metric -name rail.rj.min.net:VSS -value NA
set_metric -name rail.rj.max.net:VSS -value NA
set_metric -name rail.rj.avg.net:VSS -value NA
set_metric -name rail.rj.violations.net:VSS -value 0
set_metric -name rail.gridcap.net:VSS -value "1.846 pF"
set_metric -name rail.intrinsiccap.net:VSS -value "0.000 F"
set_metric -name rail.loadingcap.net:VSS -value "46.978 pF"
set_metric -name rail.totalcap.net:VSS -value "48.824 pF"
set_metric -name rail.averagedemandcurrent.net:VSS -value "-0.000829202 A"
set_metric -name rail.peakdemandcurrent.net:VSS -value "-0.0137448 A"
set_metric -name rail.averagesupplycurrent.net:VSS -value "-0.00082923 A"
set_metric -name rail.peaksupplycurrent.net:VSS -value "-0.0125612 A"
set_metric -name rail.ir.worstiv.net:VSS -value "0.0245852 V"
