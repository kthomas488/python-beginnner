import random

def count_vowels_consanants_digits(input_string):
    vowels = "aeiouAEIOU"
    vowel_count = 0
    consonant_count = 0
    digit_count = 0

    for char in input_string:
        if char in vowels:
            vowel_count += 1
        elif char.isalpha():
            consonant_count += 1
        elif char.isdigit():
            digit_count += 1
    return vowel_count,consonant_count,digit_count
    

input_string = input("Enter a string:")

print(f"Calling the function to count vowels,consnants and digits")
vowels,consonants,digits = count_vowels_consanants_digits(input_string)
print(f"In the entered string '{input_string}': Vowels:{vowels} Consonants: {consonants} Digits: {digits}")






