def reverse_a_number(n):
    """
    Reverses the digits of an integer number.

    Parameters:
    n (int): The integer number to be reversed.

    Returns:
    int: The reversed integer number.
    """
    # Convert the number to string, reverse it and convert back to integer
    sign = -1 if n <0 else 1
    num = abs(n)
    reversed_num =0
    while num > 0:
        digit = num %10
        reversed_num = reversed_num *10 + digit
        num = num // 10
    return sign * reversed_num
num = int(input("Enter an integer number:  "))
print(f"The reversed number is {reverse_a_number(num)}")