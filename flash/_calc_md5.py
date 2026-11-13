import hashlib
for n in (124472, 123960, 51200, 73216):
    print(n, hashlib.md5(str(n).encode()).hexdigest().upper())
print("official API md5 v1.08: 77F76375A4C041EBE9C2D774A065EEBC")
print("official API md5 v1.06: 932C3EF2A41D7F0A26296E1B725A4ED5")
