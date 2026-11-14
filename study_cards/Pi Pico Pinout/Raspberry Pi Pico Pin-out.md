# Pi Pico 1 and 2 Pinout

## Pi Pico 1
![Pi Pico 1 Pinout](</study_cards/Pi Pico Pinout/images/Pico_1_pinout.png>)

| Specs          |        |
| -------------- |:------:|
| Processor      |RP2040  |
| Clock Speed    |125 MHz |
| Flash Memory   |2 MB    |
| SRAM           |264 KB  |
| Digital I/O    |26      |
| Analog Input   |3       |
| PWM            |16      |
| ADC Resolution |4096    |
| Interrupts     |26      |

## Pi Pico 2
![Pi Pico 2 Pinout](</study_cards/Pi Pico Pinout/images/Pico_2_pinout.png>)

| Specs          |        |
| -------------- |:-------|
| Processor      |RP2350  |
| Clock Speed    |150 MHz |
| Flash Memory   |4 MB    |
| SRAM           |520 KB  |
| Digital I/O    |26      |
| Analog Input   |3       |
| PWM            |16      |
| ADC Resolution |4096    |
| Interrupts     |26      |

Both Raspberry Pi Pico models of the W variant use the Infineon CYW43439 wireless chip, connected to the microcontroller through an SPI interface operating at up to 33 MHz. the microcontroller is conected to pins that are not brought out to the headers:

**GPIO23: wireless power-on signal**
**GPIO24: SPI data and interrupt (IRQ)**
**GPIO25: SPI chip select, when high it also enables reading VSYS on GPIO29** 
**GPIO29: SPI clock, or ADC3 for measuring VSYS/3**

Sources:
https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html
https://devboards.info/boards/raspberry-pi-pico-2-w
https://devboards.info/boards/raspberry-pi-pico
https://pip-assets.raspberrypi.com/categories/686-raspberry-pi-pico-w/documents/RP-008257-DS-3-connecting-to-the-internet-with-pico-w.pdf
