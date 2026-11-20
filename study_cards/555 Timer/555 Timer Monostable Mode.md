# 555 Timer Monostable Mode
![Monostable Mode Circuit](</study_cards/555 Timer/images/Monostable mode.png>)

### Operation
In monostable Mode the Output (Pin 3) remains in a low state until a low pulse is observed on the Trigger (Pin 2). The 555 will remain in this “HIGH” unstable output state until the time period set up by the R1 x C1 network has elapsed. The amount of time that the output voltage remains “HIGH” or at a logic “1” level, is given by the following time constant equation.

```
T = 1.1*R*C
```

When a low pulse is sent on the trigger pin the internal transistor connected to the discharge pin turned off (the discharge pin is disconnected from ground), so the capacitor C1 starts to slowly charge trough the resistor R1 once the voltage at the threshold pin reaches 2/3Vcc the internal flip-flop resets, the discharge transistor is tuned on and the capacitor is connected to ground.  

<center><img alt="Waveforms Monostable" src="/study_cards/555 Timer/images/waveforms-monostable.png"></center>

Note that if the trigger pin is still low after the capacitor charges and discharges, it will just charge again, and the output will remain high.

To guarantee that the 555 wont re-trigger a pulse circuit can be used on the trigger pin:

![Monostable Mode Circuit](</study_cards/555 Timer/images/Monostable mode (Pulse Circuit).png>)

To avoid spikes on the trigger pin, a clamping diode may also be added:
<center><img alt="Clamping Diode" src="/study_cards/555 Timer/images/555-trigger-clamping-diode.png"></center>
   
Sources:
https://learnabout-electronics.org/Oscillators/osc45.php
https://www.electronics-tutorials.ws/waveforms/555_timer.html
https://www.555-timer-circuits.com/operating-modes.html
