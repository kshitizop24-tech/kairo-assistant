item= input("Enter an item: ")
quantity =  float(input("enter the quantity: "))
price = float(input("enter the price: "))
price_per_item = price * quantity
print(f"the total price of {quantity}{item} is {price_per_item}")
