from ._ingenialink import lib


# Motor types

MOTOR_SQUIRREL = lib.IL_MOTOR_SQUIRREL
""" int: Motor type,  Squirrel cage induction. """
MOTOR_STEPPER = lib.IL_MOTOR_STEPPER
""" int: Motor type, Stepper with microstepping capability. """
MOTOR_ROT_BLAC = lib.IL_MOTOR_ROT_BLAC
""" int: Motor type, Rotary brushless AC. """
MOTOR_ROT_BLDC = lib.IL_MOTOR_ROT_BLDC
""" int: Motor type, Rotary brushless DC. """
MOTOR_ROT_DC = lib.IL_MOTOR_ROT_DC
""" int: Motor type, Rotary DC. """
MOTOR_ROT_VC = lib.IL_MOTOR_ROT_VC
""" int: Motor type, Rotary voice coil. """
MOTOR_LIN_BLAC = lib.IL_MOTOR_LIN_BLAC
""" int: Motor type, Linear brushless AC. """
MOTOR_LIN_BLDC = lib.IL_MOTOR_LIN_BLDC
""" int: Motor type, Linear brushless DC. """
MOTOR_LIN_VC = lib.IL_MOTOR_LIN_VC
""" int: Motor type, Linear voice coil. """
MOTOR_LIN_DC = lib.IL_MOTOR_LIN_DC
""" int: Motor type, Linear DC """

# Feedbacks

FB_DIGITAL_ENCODER = lib.IL_FB_DIGITAL_ENCODER
""" int: Feedback, Digital encoder. """
FB_DIGITAL_HALLS = lib.IL_FB_DIGITAL_HALLS
""" int: Feedback, Digital halls. """
FB_ANALOG_HALLS = lib.IL_FB_ANALOG_HALLS
""" int: Feedback, Analog halls. """
FB_ANALOG_INPUT = lib.IL_FB_ANALOG_INPUT
""" int: Feedback, Analog input. """
FB_SSI = lib.IL_FB_SSI
""" int: Feedback, SSI. """
FB_SINCOS = lib.IL_FB_SINCOS
""" int: Feedback, SinCos. """
FB_PWM = lib.IL_FB_PWM
""" int: Feedback, PWM. """
FB_RESOLVER = lib.IL_FB_RESOLVER
""" int: Feedback, Resolver. """
FB_NONE = lib.IL_FB_NONE
""" int: Feedback, None. """
FB_SIMULATED = lib.IL_FB_SIMULATED
""" int: Feedback, Simulated. """

# Velocity sensors

VEL_SENSOR_POS = lib.IL_VEL_SENSOR_POS
""" int: Velocity sensor, Position sensor. """
VEL_SENSOR_TACHOMETER = lib.IL_VEL_SENSOR_TACHOMETER
""" int: Velocity sensor, External DC tachometer. """
VEL_SENSOR_NONE = lib.IL_VEL_SENSOR_NONE
""" int: Velocity sensor, None. """
VEL_SENSOR_DIGITAL_HALLS = lib.IL_VEL_SENSOR_DIGITAL_HALLS
""" int: Velocity sensor, Digital halls. """

# Position sensors

POS_SENSOR_DIGITAL_ENCODER = lib.IL_POS_SENSOR_DIGITAL_ENCODER
""" int: Position sensor, Digital encoder. """
POS_SENSOR_DIGITAL_HALLS = lib.IL_POS_SENSOR_DIGITAL_HALLS
""" int: Position sensor, Digital halls. """
POS_SENSOR_ANALOG_HALLS = lib.IL_POS_SENSOR_ANALOG_HALLS
""" int: Position sensor, Analog halls. """
POS_SENSOR_ANALOG_INPUT = lib.IL_POS_SENSOR_ANALOG_INPUT
""" int: Position sensor, Analog input. """
POS_SENSOR_SSI = lib.IL_POS_SENSOR_SSI
""" int: Position sensor, SSI. """
POS_SENSOR_SINCOS = lib.IL_POS_SENSOR_SINCOS
""" int: Position sensor, SinCos. """
POS_SENSOR_PWM = lib.IL_POS_SENSOR_PWM
""" int: Position sensor, PWM. """
POS_SENSOR_RESOLVER = lib.IL_POS_SENSOR_RESOLVER
""" int: Position sensor, Resolver. """
POS_SENSOR_NONE = lib.IL_POS_SENSOR_NONE
""" int: Position sensor, None. """
POS_SENSOR_SIMULATED = lib.IL_POS_SENSOR_SIMULATED
""" int: Position sensor, Simulated. """
POS_SENSOR_TACHOMETER = lib.IL_POS_SENSOR_TACHOMETER
""" int: Position sensor, Digital tachometer. """

# Initial angle determination methods

IANGLE_METHOD_FORCED_ALIGN = lib.IL_IANGLE_METHOD_FORCED_ALIGN
""" int: Forced alignment method. """
IANGLE_METHOD_NINCR_SENSOR = lib.IL_IANGLE_METHOD_NINCR_SENSOR
""" int: Non incremental sensor used. """
IANGLE_METHOD_POS_KNOWN = lib.IL_IANGLE_METHOD_POS_KNOWN
""" int: Initial rotor position known. """

# Digital encoder / SinCos parameters

DENC_SINCOS_NSWAPPED = lib.IL_DENC_SINCOS_NSWAPPED
""" int: Digital encoder/SinCos is not swapped. """
DENC_SINCOS_SWAPPED = lib.IL_DENC_SINCOS_SWAPPED
""" int: Digital encoder/SinCis is swapped. """

DENC_SINCOS_TYPE_NONE = lib.IL_DENC_SINCOS_TYPE_NONE
""" int: No encoder. """
DENC_SINCOS_TYPE_2CH_S = lib.IL_DENC_SINCOS_TYPE_2CH_S
""" int: 2 channels encoder (single ended). """
DENC_SINCOS_TYPE_2CH_S_IDX = lib.IL_DENC_SINCOS_TYPE_2CH_S_IDX
""" int: 2 channels + index encoder (single ended). """
DENC_SINCOS_TYPE_2CH_D = lib.IL_DENC_SINCOS_TYPE_2CH_D
""" int: 2 channels encoder (differential). """
DENC_SINCOS_TYPE_2CH_D_IDX = lib.IL_DENC_SINCOS_TYPE_2CH_D_IDX
""" int: 2 channels + index encoder (differential). """

DENC_SINCOS_FILTER_30MHZ = lib.IL_DENC_SINCOS_FILTER_30MHZ
""" int: Maximum encoder frequency, 30 MHz. """
DENC_SINCOS_FILTER_10MHZ = lib.IL_DENC_SINCOS_FILTER_10MHZ
""" int: Maximum encoder frequency, 10 MHz. """
DENC_SINCOS_FILTER_5MHZ = lib.IL_DENC_SINCOS_FILTER_5MHZ
""" int: Maximum encoder frequency, 5 MHz. """
DENC_SINCOS_FILTER_2MHZ = lib.IL_DENC_SINCOS_FILTER_2MHZ
""" int: Maximum encoder frequency, 2 MHz. """
DENC_SINCOS_FILTER_1MHZ = lib.IL_DENC_SINCOS_FILTER_1MHZ
""" int: Maximum encoder frequency, 1 MHz. """
DENC_SINCOS_FILTER_625KHZ = lib.IL_DENC_SINCOS_FILTER_625KHZ
""" int: Maximum encoder frequency, 625 KHz. """
DENC_SINCOS_FILTER_312_5KHZ = lib.IL_DENC_SINCOS_FILTER_312_5KHZ
""" int: Maximum encoder frequency, 312,5 KHz. """
DENC_SINCOS_FILTER_156_25KHZ = lib.IL_DENC_SINCOS_FILTER_156_25KHZ
""" int: Maximum encoder frequency, 156,25 KHz. """
DENC_SINCOS_FILTER_39_06KHZ = lib.IL_DENC_SINCOS_FILTER_39_06KHZ
""" int: Maximum encoder frequency, 39,06 KHz. """
