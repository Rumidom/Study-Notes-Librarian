## Loops on the C Language

### For loop

The main parts of a for loop are:

**Initialization:** Sets the initial value of the loop variable.   
**Condition:** Determines whether the loop should continue executing.   
**Update:** Changes the loop variable after each iteration.   
**Body:** Contains the statements to be executed repeatedly.   

```c
for (initialization; condition; update) {
    // Body of loop
}
```

example:

```c
#include <stdio.h>
int main() {
    for (int i = 0; i < 3; i++) {
        printf("Hello world\n");
    }
    return 0;
}
```

### While Loop

A while loop is a entry-controlled loop. meaning that the condition is checked before entering the body of the loop.
```c
while (condition) {
    // Body of loop
}
```
example:
```c
#include <stdio.h>
int main() {
    
  // Initialization expression
  int i = 0; 
 
  // Test expression
  while(i <= 5) {
    printf("%d ", i + 1);   
    
    // update expression
    i++;
  } 
  
  return 0;
}
```
sources:
https://www.geeksforgeeks.org/c/c-loops/
