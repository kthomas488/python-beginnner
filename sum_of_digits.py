import random
##Sum of digits of a number until it becomes a single digit

def sum_of_digits(num):
    while num >=10:
        s = 0
        while num > 0:
            s += num % 10
            num //=10
        n = s
    return n

num = int(input("Enter a number:"))

print("Calling the function sum_of_digits ")
result = sum_of_digits(num)

print(f"The single digit sum of digits of {num} is: {result}")
        