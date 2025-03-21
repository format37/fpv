# FPV
A storage for fpv documentation

### Pricing
[pricing.md](pricing.md)

### Logging
I have to extract SD card from the flight controller to read the logs. Logs are received in the bin format. To convert them to csv I use the pymavlink library.

### 3D models
[Thingiverse](https://www.thingiverse.com/thing:6959504)

### RC Flight modes configuration
Set both mixes to the same channel. Define bias for each switch according to the Mission planner Flight modes frequencies.  
Each bias is 129/5 pwm for the first switch and 129*3/5 for the second one.
 