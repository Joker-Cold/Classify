#######################################################
#                                                     
#  Voltus IC Power Integrity Solution Command Logging File                     
#  Created on Tue Mar 17 10:42:02 2026                
#                                                     
#######################################################

#@(#)CDS: Voltus IC Power Integrity Solution v15.20-p004_1 (64bit) 11/09/2015 12:44 (Linux 2.6.18-194.el5)
#@(#)CDS: NanoRoute 15.20-p004_1 NR151028-1715/15_20-UB (database version 2.30, 298.6.1) {superthreading v1.26}
#@(#)CDS: AAE 15.20-p002 (64bit) 11/09/2015 (Linux 2.6.18-194.el5)
#@(#)CDS: CTE 15.20-p001_1 () Oct 29 2015 01:50:39 ( )
#@(#)CDS: SYNTECH 15.20-b002_1 () Oct 20 2015 02:35:29 ( )
#@(#)CDS: CPE v15.20-p002

setLayerPreference net -isVisible 0
setLayerPreference clock -isVisible 0
restoreDesign ../../db/des3.enc
win restoreDesign Browser
restoreDesign /home/IC/Desktop/des_demo/db/des3.enc.dat des3 -physical_data
read_design -physical_data
read_design -physical_data
restoreDesign /home/IC/Desktop/des_demo/db/des3.enc.dat des3 -physical_data
