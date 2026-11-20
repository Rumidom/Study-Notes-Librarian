# How the 555 Timer Works
![555 timer internal circuitry](</study_cards/555 Timer/images/Inside-555-timer-sketched.png>)

The 555 Timers name comes from the fact that there are three 5kΩ resistors connected together internally producing a voltage divider network between the supply voltage at pin 8 and ground at pin 1. This produces a voltage divider where 1/3Vcc and 2/3Vcc can be compared against the Trigger and Threshold pins respectively.

The two comparators produce an output voltage dependent upon the voltage difference at their inputs which is determined by the charging and discharging action of an externally connected capacitor.

Note that if the voltage at Trigger pin is lower than 1/3Vcc the internal flip  -flop is Set. and if the voltage on the Threshold pin is heigher the flip-flop is reset. the chaging and discharging of a capacitor can be acomplished using the discharge pin and the flip flop can be reset using the reset pin. 

Sources:
https://learnabout-electronics.org/Oscillators/osc45.php
https://www.electronics-tutorials.ws/waveforms/555_timer.html
https://www.555-timer-circuits.com/operating-modes.html
