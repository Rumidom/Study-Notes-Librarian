
### For loop in c

The main parts of a for loop are:

**Initialization:** Sets the initial value of the loop variable.   
**Condition:** Determines whether the loop should continue executing.   
**Update:** Changes the loop variable after each iteration.   
**Body:** Contains the statements to be executed repeatedly.   

```
for (initialization; condition; update) {

    // Body of loop

}
```

here is example:

```c
#include <stdio.h>
int main() {
    for (int i = 0; i < 3; i++) {
        printf("Hello world\n");
    }
    return 0;
}
```

[source](https://www.geeksforgeeks.org/c/c-loops/)
