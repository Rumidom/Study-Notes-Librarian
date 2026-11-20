# 555 Timer Astable Mode
![Astable Mode Circuit](</study_cards/555 Timer/images/Astable mode.png>)

In Astable Mode the 555 works as a Oscillator circuit. pin 2 and pin 6 are connected together allowing the circuit to re-trigger itself on each and every cycle. During each cycle capacitor, C charges up through both timing resistors, R1 and the potentiometer POT1 but discharges itself only through POT1, POT1 as the other side of POT1 is connected to the discharge pin.
this way POT1+R1 dictates the charging time t1 while just the POT sets the discharging time t2.

 ![Bistable Mode Circuit](</study_cards/555 Timer/images/waveforms-astable.png>)

the timing equation is given by:
```
t1 = 0.693(POT+R1)*C
t2 = 0.693(POT)*C
T = t1 + t2 = 0.693(R1+2*POT)*C
```
By making R1 very small compared to the POT value the charging and discharging times will be mostly dictated by POT and thus the duty cycle will be close to 50%.

The ability of the 555 timer to both sink and source its output load current means that both LED’s can be connected to the output terminal at the same time but only one will be switched “ON” depending whether the output state is “HIGH” or “LOW”. the maximum output current to either sink or source the load current via pin 3 is about 200mA at the maximum supply voltage.

![Bistable Mode Circuit](</study_cards/555 Timer/images/Astable mode (Aditional LED).png>)
### Operation


Sources:
https://learnabout-electronics.org/Oscillators/osc45.php
https://www.electronics-tutorials.ws/waveforms/555_oscillator.html
