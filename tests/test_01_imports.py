#!/usr/bin/python

def test_can_import():

    ex = None
    try:
        import swampyer
    except Exception as ex:
        pass
    assert ex == None


