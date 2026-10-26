"""Constants for the Green Mountain Grill integration."""
DOMAIN = "gmg"
PLATFORMS = ["climate", "sensor", "binary_sensor"]

# Raw warnState (status bytes 24..27) values with an observed meaning. Low
# pellet is 0x80: tripping the hopper sensor on a lit grill set byte 24 to
# 0x80 and refilling returned it to 0x00, with nothing else in the frame
# changing. GMG's cloud API encodes the same alarm as 2, so a value ported
# from a cloud client is the wrong one here.
WARN_NONE = 0
WARN_LOW_PELLET = 0x80
