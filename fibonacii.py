# ...existing code...
def fibonacci(num):
    a = 0
    b = 1
    fibonacci_list = []
    for _ in range(num):
        print(f"Value of a {a}")
        fibonacci_list.append(a)
        a, b = b, a + b
    return fibonacci_list

num = int(input("Enter number: "))
print(f"fibonacci list is {fibonacci(num)}")
# ...existing code...


