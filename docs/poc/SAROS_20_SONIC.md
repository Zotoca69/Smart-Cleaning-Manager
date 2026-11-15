# Saros 20 Sonic — observed protocol profile
Not a general compatibility guarantee. Installed versions unknown.
HA vacuum.send_command: set_clean_motor_mode with params list containing object fan_power, water_box_mode, mop_mode. Tested transition from Custom via 102/200/300 then desired combination. app_segment_clean params list containing object segments (explicit discovered IDs), repeat:1. No private map IDs published.
Fan: 101 Quiet, 102 Balanced, 103 Turbo, 104 Max, 105 Off, 106 Custom, 108 Max+ (accepted without mop, rejected with Moderate).
Water: 200 Off, 225 Low, 235 Medium, 245 Moderate, 248 High, 250 Extreme. 210/215/220/255 rejected; 240/249 unknown. Slight and Smart not fully mapped.
Route: 300 Standard verified; 302 Custom used during transition. Others unverified. Not all combinations tested. Combined 102/248/300 used successfully in a selected-room vacuum/mop test. Legacy commands may reject or report unexpected state. Reapply profile and verify before each physical job. Unknown readback is not necessarily execution failure.
