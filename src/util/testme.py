#! /usr/bin/python

import logging

class TestMe:
    @staticmethod
    def testMessage(script, data, expected, actual):
        if (expected != actual):
            logging.error("Test failure in "+script+" on "+data+": got "+str(actual)+", expected "+str(expected))