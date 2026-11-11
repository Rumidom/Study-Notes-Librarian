
### Pi Pico SDK - Using the Analog to Digital Converter 

the following example prints the value from a ADC on the pi pico every 500 ms.
the defaut max value of the ADC is 4095.

CMakeLists.txt:

```cmake
add_executable(hello_adc hello_adc.c)
target_link_libraries(hello_adc pico_stdlib hardware_adc)

# create map/bin/hex file etc.
pico_add_extra_outputs(hello_adc)

# add url via pico_set_program_url
example_auto_set_url(hello_adc)
```

hello_adc.c:

```c
#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/gpio.h"
#include "hardware/adc.h"

int main() {
    stdio_init_all();
    printf("ADC Example, measuring GPIO26\n");

    adc_init();

    // Make sure GPIO is high-impedance, no pullups etc
    adc_gpio_init(26);
    // Select ADC input 0 (GPIO26)
    adc_select_input(0);

    while (1) {
        uint16_t result = adc_read();
        printf("Raw value: %d \n", result);
        sleep_ms(500);
    }
}
```
[source](https://github.com/raspberrypi/pico-examples/tree/master)
