def prime_number(n):
    """
    Checks if a number is prime.

    Parameters:
    n (int): The integer number to be checked.

    Returns:
    bool: True if the number is prime, False otherwise.
    """
    if n <=1:
        return False
    elif n == 2:
        return False
    elif n % 2 == 0:
        return True
    return False

num = int(input("Enter an integer number:  "))
val = prime_number(num)
if val:
    print(f"The entered number {num} is a prime number")
else:
    print(f"The entered number {num} is not a prime numb")