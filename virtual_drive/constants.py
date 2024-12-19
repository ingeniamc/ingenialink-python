# Power Drive System
# Controlword common bits.
IL_MC_CW_SO = 1 << 0
IL_MC_CW_EV = 1 << 1
IL_MC_CW_QS = 1 << 2
IL_MC_CW_EO = 1 << 3
IL_MC_CW_FR = 1 << 4
# Statusword common bits.
IL_MC_SW_RTSO = 1 << 0
IL_MC_SW_SO = 1 << 1
IL_MC_SW_OE = 1 << 2
IL_MC_SW_F = 1 << 3
IL_MC_SW_QS = 1 << 5
IL_MC_SW_SOD = 1 << 6

# PDS FSA states
# Masks for PDS FSA states
IL_MC_PDS_STA_OE_MSK = (
    IL_MC_SW_RTSO | IL_MC_SW_SO | IL_MC_SW_OE | IL_MC_SW_F | IL_MC_SW_QS | IL_MC_SW_SOD
)
# Switch on disabled.
IL_MC_PDS_STA_SOD = IL_MC_SW_SOD
# Ready to switch on.
IL_MC_PDS_STA_RTSO = IL_MC_SW_RTSO | IL_MC_SW_QS
# Operation enabled.
IL_MC_PDS_STA_OE = IL_MC_SW_RTSO | IL_MC_SW_SO | IL_MC_SW_OE | IL_MC_SW_QS

# PDS FSA commands
# Shutdown.
IL_MC_PDS_CMD_SD = IL_MC_CW_EV | IL_MC_CW_QS
IL_MC_PDS_CMD_MSK = IL_MC_CW_SO | IL_MC_CW_EV | IL_MC_CW_QS | IL_MC_CW_FR
# Disable voltage.
IL_MC_PDS_CMD_DV = 0x00000
IL_MC_PDS_CMD_DV_MSK = IL_MC_CW_EV | IL_MC_CW_FR
