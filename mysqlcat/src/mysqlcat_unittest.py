#!/usr/bin/env python
# -*- coding:utf-8 -*-

import unittest

from mysqlcat import *

class MysqlCatUnittest(unittest.TestCase):

    def setUp(self):
        self.conn = Connection(
            host = '127.0.0.1',
            database = 'test',
            user = 'admin',
            password = '123456',
            autocommit = False
        )
        try:
            self.conn.write('drop table mysqlcat_unittest;')
        except:
            pass

    def tearDown(self):
        pass

    def _create_table(self):
        self.conn.write('''
            CREATE TABLE mysqlcat_unittest (
            id varchar(32)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
        ''')

    def test_create_table(self):
        self._create_table()

    def test_input_data(self):
        self._create_table()
        self.conn.begin() 
        self.assertEqual(1, self.conn.write('insert into mysqlcat_unittest values(%s);', 10))
        self.assertEqual(1, self.conn.write('insert into mysqlcat_unittest values(%s);', 20))
        self.conn.commit()

        self.conn.begin() 
        data = [
            (30),
            (40)
        ]
        self.assertEqual(2, self.conn.batchwrite('insert into mysqlcat_unittest values(%s);', data))
        self.conn.commit()

        print self.conn.read('select * from mysqlcat_unittest;')
        print self.conn.read('select * from mysqlcat_unittest;')
        for row in self.conn.iterator('select * from mysqlcat_unittest;'):
            print row

if __name__ == '__main__':
    unittest.main()
