import random

def find_largest_number_in_a_list(num_list):
    """
    Finds the largest number in a list.

    Parameters:
    num_list (list): A list of integer numbers.

    Returns:
    int: The largest integer number in the list.
    """
    if not num_list:
        return None
    largest_number = num_list[0]
    for number in num_list:
        if number > largest_number:
            largest_number = number
    return largest_number

print("Generating a list of 10 random integers between 1 and 100...")

"""for _ in range(10):
    random_list = [random.randint(1,100)]"""
random_list = [random.randint(1,100) for _ in range (10
                                                     )]
    
print(f"Generated list: {random_list}")
    
print(f"Calling the function to find the largest number in the list...")
val = find_largest_number_in_a_list(random_list)
print(f"The largest number in the list {random_list} is {val}")