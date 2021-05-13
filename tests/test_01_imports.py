#!/usr/bin/env python

def test_can_import():

    ex = None
    try:
        import swampyer
    except Exception as ex:
        print("Error:", ex)
        pass
    assert ex == None

if __name__ == '__main__':
    test_can_import()
