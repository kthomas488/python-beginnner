##Print all Armstrong numbers between 1 and 10000

def is_armstrong(num):
    digits = str(num)
    num_digits = len(digits)
    armstrong_num = sum(int(digit) ** num_digits for digit in digits)
    return armstrong_num == num

print("Armstrong numbers between 1 and 10000 are:")
print("Caling the function is_armstrong")

for number in range(1,10001):
    if is_armstrong(number):
        print(f"{number} is an Armstrong number")

