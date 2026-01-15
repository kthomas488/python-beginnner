import random
##Print all Armstrong numbers between 1 and 10000




def is_armstrong(num):
    digits = str(num)
    num_digits = len(digits)
    armstrong_num = sum(int(digit) ** num_digits for digit in digits)
    return armstrong_num == num

armstrong_numbers = []
for number in range(1,10001):
    if is_armstrong(number):
        armstrong_numbers.append(number)
print(f"Armstrong numbers between 1 and 10000 are: {armstrong_numbers}")