# coding: utf-8

x = 10
def test_eval():
    y = 20  # 局部变量y
    c = eval("x+y", {"x": 1, "y": 2}, {"y": 3, "z": 4})
    print("c:", c)


pass

def main():
    test_eval()

if __name__ == "__main__":
    main()